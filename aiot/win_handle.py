# SPDX-License-Identifier: MIT
# Copyright 2025 (c) MediaTek, Inc.
# Author: Pablo Sun <pablo.sun@mediatek.com>
#
# Windows utility to resolve FTDI D2XX / VCP COM port conflicts.
#
# When a terminal application (e.g. TeraTerm, PuTTY) holds an FTDI
# COM port open via the VCP (Virtual COM Port) driver, the D2XX driver
# cannot access the same device.  This module detects and resolves such
# conflicts by locating the COM port handle in the remote process and
# terminating it, so that D2XX can proceed.
#
# Typical usage from ftdi_win.py:
#
#   from aiot.win_handle import find_ftdi_com_port, find_com_port_holder
#   com, nt_path = find_ftdi_com_port(serial)
#   holder = find_com_port_holder(com, nt_path)
#   if holder:
#       holder.terminate()

import ctypes
import ctypes.wintypes as wintypes
import logging
import os
import struct
import threading
import winreg

logger = logging.getLogger('aiot')

# ── Windows API constants ────────────────────────────────────────────────
PROCESS_DUP_HANDLE = 0x0040
DUPLICATE_CLOSE_SOURCE = 0x0001
DUPLICATE_SAME_ACCESS = 0x0002
STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
SystemExtendedHandleInformation = 64
ObjectNameInformation = 1

# ── DLLs ─────────────────────────────────────────────────────────────────
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
ntdll = ctypes.WinDLL('ntdll')

# ── Function prototypes (critical on 64-bit: HANDLE is pointer-sized) ────
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE

kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = wintypes.HANDLE

kernel32.DuplicateHandle.argtypes = [
    wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
    ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD, wintypes.BOOL,
    wintypes.DWORD]
kernel32.DuplicateHandle.restype = wintypes.BOOL

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.GetFileType.argtypes = [wintypes.HANDLE]
kernel32.GetFileType.restype = wintypes.DWORD

kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel32.CreateFileW.restype = wintypes.HANDLE

kernel32.QueryDosDeviceW.argtypes = [
    wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
kernel32.QueryDosDeviceW.restype = wintypes.DWORD

ntdll.NtQuerySystemInformation.argtypes = [
    ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong)]
ntdll.NtQuerySystemInformation.restype = ctypes.c_long

ntdll.NtQueryObject.argtypes = [
    wintypes.HANDLE, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong)]
ntdll.NtQueryObject.restype = ctypes.c_long


# ── Extended handle info (works correctly on 64-bit Windows) ─────────────
class SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX(ctypes.Structure):
    _fields_ = [
        ("Object", ctypes.c_void_p),
        ("UniqueProcessId", ctypes.c_size_t),
        ("HandleValue", ctypes.c_size_t),
        ("GrantedAccess", ctypes.c_ulong),
        ("CreatorBackTraceIndex", ctypes.c_ushort),
        ("ObjectTypeIndex", ctypes.c_ushort),
        ("HandleAttributes", ctypes.c_ulong),
        ("Reserved", ctypes.c_ulong),
    ]


def _get_active_serial_ports():
    """Read HKLM\\HARDWARE\\DEVICEMAP\\SERIALCOMM to get currently active
    COM ports.  This volatile key only contains ports that are plugged in
    right now.

    Returns:
        List of (nt_device_path, com_port_name) tuples, e.g.
        [("\\Device\\VCP0", "COM11"), ("\\Device\\Serial0", "COM1")].
    """
    result = []
    try:
        key_path = r"HARDWARE\DEVICEMAP\SERIALCOMM"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            idx = 0
            while True:
                try:
                    nt_path, com_name, _ = winreg.EnumValue(key, idx)
                    idx += 1
                    logger.debug(f"Active serial port: {nt_path} → {com_name}")
                    result.append((nt_path, com_name))
                except OSError:
                    break
    except OSError as e:
        logger.debug(f"Cannot read SERIALCOMM registry: {e}")
    return result


def _get_ftdibus_com_port(serial=None):
    """Look up FTDIBUS registry for the COM port assigned to an FTDI device.
    Note: this may return stale entries for devices that were previously
    connected but are no longer plugged in.

    Returns:
        COM port name (e.g. "COM11"), or None.
    """
    try:
        base = r"SYSTEM\CurrentControlSet\Enum\FTDIBUS"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as key:
            idx = 0
            while True:
                try:
                    dev_id = winreg.EnumKey(key, idx)
                    idx += 1
                    logger.debug(f"Registry FTDIBUS device: {dev_id}")
                    if serial and serial.upper() not in dev_id.upper():
                        logger.debug(f"  skipped (serial filter: {serial})")
                        continue
                    params = f"{base}\\{dev_id}\\0000\\Device Parameters"
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, params) as pk:
                            port, _ = winreg.QueryValueEx(pk, "PortName")
                            logger.debug(f"  found COM port: {port}")
                            return port
                    except OSError as e:
                        logger.debug(f"  no Device Parameters: {e}")
                        continue
                except OSError:
                    break
    except OSError as e:
        logger.debug(f"Cannot open FTDIBUS registry key: {e}")
    return None


def find_ftdi_com_port(serial=None):
    """Find the COM port and NT device path for an active FTDI VCP device.

    Uses HKLM\\HARDWARE\\DEVICEMAP\\SERIALCOMM (which only lists currently
    active ports) to avoid stale registry entries, and cross-references
    with the FTDIBUS registry when a serial number filter is provided.

    Args:
        serial: Optional FTDI device serial number to filter by.

    Returns:
        (com_port_name, nt_device_path) tuple, or (None, None).
    """
    active_ports = _get_active_serial_ports()

    # FTDI VCP devices use NT paths like \Device\VCP0, \Device\VCP1, ...
    vcp_ports = [(nt, com) for nt, com in active_ports
                 if '\\VCP' in nt.upper() or '\\FTDI' in nt.upper()]

    if not vcp_ports:
        logger.debug("No active FTDI VCP ports found in SERIALCOMM")
        return None, None

    logger.debug(f"Active FTDI VCP ports: {vcp_ports}")

    if len(vcp_ports) == 1:
        nt_path, com_name = vcp_ports[0]
        logger.debug(f"Single FTDI VCP port: {com_name} ({nt_path})")
        return com_name, nt_path

    # Multiple VCP ports — use FTDIBUS registry + serial to disambiguate.
    ftdibus_com = _get_ftdibus_com_port(serial)
    if ftdibus_com:
        for nt_path, com_name in vcp_ports:
            if com_name == ftdibus_com:
                logger.debug(f"Matched FTDIBUS {ftdibus_com} to "
                             f"active VCP {nt_path}")
                return com_name, nt_path
        logger.debug(f"FTDIBUS says {ftdibus_com} but it is not among "
                     f"active VCP ports — may be stale")

    logger.debug("Cannot determine which FTDI VCP port to use")
    return None, None


def _enum_handles():
    """Yield (pid, handle_value, object_type_index) for every open handle
    in the system."""
    size = 0x800000  # 8 MB initial buffer
    for attempt in range(10):
        buf = (ctypes.c_char * size)()
        ret = ctypes.c_ulong()
        status = ntdll.NtQuerySystemInformation(
            SystemExtendedHandleInformation, buf, size, ctypes.byref(ret))
        ustatus = status & 0xFFFFFFFF
        if ustatus == (STATUS_INFO_LENGTH_MISMATCH & 0xFFFFFFFF):
            logger.debug(f"NtQuerySystemInformation: buffer too small "
                         f"({size} bytes), doubling (attempt {attempt + 1})")
            size *= 2
            continue
        if status < 0:
            logger.debug(f"NtQuerySystemInformation failed: "
                         f"NTSTATUS=0x{ustatus:08X}")
            return
        break
    else:
        logger.debug("NtQuerySystemInformation: exceeded max resize attempts")
        return

    ptr_sz = ctypes.sizeof(ctypes.c_size_t)
    count = int.from_bytes(buf[:ptr_sz], byteorder='little')
    entry_sz = ctypes.sizeof(SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX)
    data_off = ptr_sz * 2  # skip NumberOfHandles + Reserved
    logger.debug(f"Enumerated {count} system handles "
                 f"(entry_sz={entry_sz}, data_off={data_off}, "
                 f"buf_size={size})")

    for i in range(count):
        off = data_off + i * entry_sz
        if off + entry_sz > size:
            logger.debug(f"Handle entry {i} exceeds buffer "
                         f"(off={off}, size={size}), stopping")
            break
        entry = SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX.from_buffer_copy(buf, off)
        yield entry.UniqueProcessId, entry.HandleValue, entry.ObjectTypeIndex


def _query_object_name_sync(handle):
    """Query the NT object name of a handle (synchronous, no thread).
    Returns the name string or None."""
    sz = 1024
    qbuf = (ctypes.c_char * sz)()
    ret = ctypes.c_ulong()
    st = ntdll.NtQueryObject(
        handle, ObjectNameInformation, qbuf, sz, ctypes.byref(ret))
    if st < 0:
        return None
    length = struct.unpack_from('=H', qbuf, 0)[0]
    if length == 0:
        return None
    str_off = 2 * ctypes.sizeof(ctypes.c_void_p)
    return qbuf[str_off:str_off + length].decode('utf-16-le', errors='ignore')


def _get_file_type_index():
    """Determine the ObjectTypeIndex for 'File' objects by opening a known
    file (NUL) and finding its type index in the system handle list."""
    GENERIC_READ = 0x80000000
    OPEN_EXISTING = 3
    nul = kernel32.CreateFileW("NUL", GENERIC_READ, 0, None,
                               OPEN_EXISTING, 0, wintypes.HANDLE(0))
    if nul == wintypes.HANDLE(-1).value or nul is None:
        logger.debug("Cannot open NUL device to determine File type index")
        return None

    my_pid = os.getpid()
    nul_val = nul & ((1 << (ctypes.sizeof(ctypes.c_size_t) * 8)) - 1)
    file_type_idx = None

    for pid, hval, type_idx in _enum_handles():
        if pid == my_pid and hval == nul_val:
            file_type_idx = type_idx
            break

    kernel32.CloseHandle(nul)
    logger.debug(f"File ObjectTypeIndex = {file_type_idx}")
    return file_type_idx


def _scan_process_handles(proc_handle, handles, device_path):
    """Check a process's file handles for a matching device path.

    Called inside a worker thread so that if NtQueryObject hangs on a
    pipe handle, we can time out the entire process rather than being
    stuck forever.

    Returns (handle_value, name) on match, or None.
    """
    device_path_lower = device_path.lower()
    for hval in handles:
        src = wintypes.HANDLE(hval)
        dup = wintypes.HANDLE()
        if not kernel32.DuplicateHandle(
                proc_handle, src,
                kernel32.GetCurrentProcess(), ctypes.byref(dup),
                0, False, DUPLICATE_SAME_ACCESS):
            continue
        name = _query_object_name_sync(dup)
        kernel32.CloseHandle(dup)
        if name and device_path_lower in name.lower():
            return hval, name
    return None


class ComPortHolder:
    """Information about a process holding a COM port open."""

    def __init__(self, pid, exe_path, com_port_name):
        self.pid = pid
        self.exe_path = exe_path
        self.com_port_name = com_port_name

    def terminate(self):
        """Terminate the process holding the COM port."""
        import psutil
        try:
            proc = psutil.Process(self.pid)
            proc.terminate()
            proc.wait(timeout=5)
            logger.info(f"Terminated {self.exe_path} (PID {self.pid})")
            return True
        except psutil.NoSuchProcess:
            # Already gone
            return True
        except Exception as e:
            logger.error(f"Failed to terminate PID {self.pid}: {e}")
            return False


def find_com_port_holder(com_port_name, device_path):
    """Find which process holds a COM port open.

    Args:
        com_port_name: COM port name, e.g. "COM45".
        device_path: NT device path, e.g. "\\\\Device\\\\VCP0".

    Returns:
        A ComPortHolder instance, or None if no holder was found.
    """
    import psutil

    logger.debug(f"Searching for process holding {com_port_name} "
                 f"(NT path {device_path})")

    file_type_idx = _get_file_type_index()
    if file_type_idx is None:
        logger.debug("Could not determine File type index, aborting")
        return None

    my_pid = os.getpid()

    # Collect only File-type handles from other processes.
    pid_handles = {}
    for pid, hval, type_idx in _enum_handles():
        if pid in (0, 4, my_pid):
            continue
        if type_idx != file_type_idx:
            continue
        pid_handles.setdefault(pid, []).append(hval)

    logger.debug(f"File-type handles across "
                 f"{len(pid_handles)} processes")

    # Prioritize: check likely terminal applications first, then the rest.
    priority_pids = []
    remaining_pids = []
    for pid in pid_handles:
        try:
            name = psutil.Process(pid).name().lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            remaining_pids.append(pid)
            continue
        if any(t in name for t in [
            'ttermpro', 'teraterm', 'putty', 'minicom', 'screen',
            'realterm', 'hercules', 'coolterm', 'securecrt', 'mobaxterm',
            'serial', 'terminal', 'hyper',
        ]):
            logger.debug(f"Priority candidate: {name} (PID {pid})")
            priority_pids.append(pid)
        else:
            remaining_pids.append(pid)

    for pid in priority_pids + remaining_pids:
        handles = pid_handles[pid]
        proc = kernel32.OpenProcess(PROCESS_DUP_HANDLE, False, pid)
        if not proc:
            continue
        try:
            result = [None]

            def worker(p=proc, h=handles):
                result[0] = _scan_process_handles(p, h, device_path)

            t = threading.Thread(target=worker, daemon=True)
            t.start()
            t.join(timeout=3.0)
            if t.is_alive():
                logger.debug(f"Timed out scanning PID {pid}, skipping")
                continue

            if result[0] is None:
                continue

            try:
                exe_path = psutil.Process(pid).exe()
            except Exception:
                exe_path = f"(PID {pid})"
            return ComPortHolder(pid, exe_path, com_port_name)
        finally:
            kernel32.CloseHandle(proc)

    logger.debug(f"No process found holding {device_path}")
    return None

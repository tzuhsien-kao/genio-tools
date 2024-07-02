# SPDX-License-Identifier: MIT
# Copyright 2024 (c) MediaTek Inc.
# Author: Macpaul Lin <macpaul.lin@mediatek.com>

import argparse
import json
import platform
import psutil
import socket
import subprocess
import sys
import time
import curses

menu_str = "== Menu == [q]uit =="

def create_socket(host, port):
    """Create and return a new socket connection."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        return s
    except (socket.error, socket.timeout):
        return None

def get_daemon_status(sock):
    """Send a status request to the daemon and return the response data."""
    try:
        sock.sendall(b'GET /status HTTP/1.1\r\nHost: localhost\r\n\r\n')
        return sock.recv(4096 * 32)
    except (socket.error, socket.timeout):
        return None

def status_json_to_info(status_info_json_str):
    """Convert status JSON string to a human-readable status info string."""
    status_info_json = json.loads(status_info_json_str)
    status_info = status_info_json["action"]

    if "error" in status_info_json and status_info_json['error']:
        status_info += f": {status_info_json['error']}"

    if status_info_json["action"] not in ['Starting']:
        for key in ["com_port", "fastboot_sn", "progress", "duration"]:
            if key in status_info_json:
                if key in ["fastboot_sn"]:
                    status_info += f" (SN: {status_info_json[key]})"
                    continue
                if key in ["com_port"]:
                    status_info += f" (COM Port: {status_info_json[key]})"
                    continue
                status_info += f" ({key.replace('_', ' ').title()}: {status_info_json[key]})"

    return status_info

def update_status_display(json_data):
    """Print the status information to the console."""
    print(menu_str)
    for id, status_info_json_str in json_data:
        print(f"Worker {id} status: {status_json_to_info(status_info_json_str)}")

def update_status_display_gui(stdscr, json_data):
    """Update the status display in the GUI."""
    stdscr.clear()
    stdscr.addstr(0, 0, menu_str)
    for row, (id, status_info_json_str) in enumerate(json_data, start=1):
        stdscr.addstr(row, 0, f"Worker {id} status: {status_json_to_info(status_info_json_str)}")
    stdscr.refresh()

def cleanup(daemon_process):
    if daemon_process:
        if platform.system() == 'Windows':
            try:
                parent = psutil.Process(daemon_process.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
                gone, still_alive = psutil.wait_procs([parent], timeout=5)
                for p in still_alive:
                    p.kill()
            except psutil.NoSuchProcess:
                pass
        else:
            daemon_process.terminate()
            daemon_process.wait()

def gui_main(stdscr, args):
    curses.curs_set(0)  # Hide cursor
    stdscr.nodelay(True)  # Non-blocking mode
    sock = None
    try:
        while True:
            if sock is None:
                sock = create_socket(args.host, args.port)
                if sock is None:
                    stdscr.addstr(1, 0, "Waiting for daemon to start...")
                    stdscr.refresh()
                    time.sleep(1)
                    continue

            try:
                response = get_daemon_status(sock)
                if response is None:
                    sock = None
                    continue
                response_body = response.split(b'\r\n\r\n', 1)[1]
                json_data = json.loads(response_body.decode('utf-8'))
                update_status_display_gui(stdscr, json_data)
            except json.JSONDecodeError as e:
                stdscr.addstr(1, 0, f"Error: {e}")
            except Exception as e:
                stdscr.addstr(1, 0, f"Error: {e}")
            stdscr.refresh()
            time.sleep(1)
            
            # Check keystroke
            key = stdscr.getch()
            if key == 3:  # Ctrl-C
                raise KeyboardInterrupt
            if key == ord('q'):
                break
    except KeyboardInterrupt:
        pass  # Ctrl-C to quit
    finally:
        if sock:
            sock.close()
        cleanup(args.daemon_process)

def main():
    parser = argparse.ArgumentParser(description='Client to query daemon status.')
    parser.add_argument('--host', type=str, default='localhost', help='Daemon host address')
    parser.add_argument('--port', type=int, required=True, help='Daemon port number')
    parser.add_argument('--gui', action='store_true', help='Enable GUI mode')
    parser.add_argument('--run-daemon', action='store_true', help='Run genio-flash daemon locally')
    parser.add_argument('--worker', type=int, help='Number of workers for the daemon')
    args = parser.parse_args()

    if args.run_daemon:
        daemon_command = ['genio-flash', '--daemon', '--port', str(args.port)]
        if args.worker:
            daemon_command.extend(['--worker', str(args.worker)])
        args.daemon_process = subprocess.Popen(daemon_command)
        time.sleep(2)  # Give the daemon some time to start
    else:
        args.daemon_process = None

    if args.gui:
        curses.wrapper(gui_main, args)
    else:
        if platform.system() == 'Windows':
            import msvcrt  # Import msvcrt for Windows

            def check_key():
                return msvcrt.kbhit() and msvcrt.getch() == b'q'
        else:
            import select  # Import select for Linux

            def check_key():
                return sys.stdin in select.select([sys.stdin], [], [], 0)[0] and sys.stdin.read(1) == 'q'

        sock = None
        try:
            while True:
                if check_key():
                    break

                if sock is None:
                    sock = create_socket(args.host, args.port)
                    if sock is None:
                        print("Waiting for daemon to start...")
                        time.sleep(1)
                        continue

                try:
                    response = get_daemon_status(sock)
                    if response is None:
                        sock = None
                        continue
                    response_body = response.split(b'\r\n\r\n', 1)[1]
                    json_data = json.loads(response_body.decode('utf-8'))
                    update_status_display(json_data)
                except json.JSONDecodeError as e:
                    print(f"Error: {e}")
                except Exception as e:
                    print(f"Error: {e}")
                time.sleep(1)
        except KeyboardInterrupt:
            pass  # Ctrl-C to quit
        finally:
            if sock:
                sock.close()
            cleanup(args.daemon_process)

if __name__ == "__main__":
    main()
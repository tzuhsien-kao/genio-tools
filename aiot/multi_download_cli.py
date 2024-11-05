# SPDX-License-Identifier: MIT
# Copyright 2024 (c) MediaTek Inc.
# Author: Macpaul Lin <macpaul.lin@mediatek.com>

import argparse
import curses
import json
import keyboard
import psutil
import platform
import socket
import subprocess
import time
import threading

if platform.system() != 'Windows':
    import sys, select

MENU_STR = "== Menu == [q]uit =="

# Global variable to control the main loop
exit_program = False

def create_socket(host, port):
    # Create and return a new socket connection.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        return s
    except (socket.error, socket.timeout):
        return None

def get_daemon_status(sock):
    # Send a status request to the daemon and return the response data.
    try:
        sock.sendall(b'GET /status HTTP/1.1\r\nHost: localhost\r\n\r\n')
        return sock.recv(4096 * 32)
    except (socket.error, socket.timeout):
        return None

def status_json_to_info(status_info_json_str):
    # Convert status JSON string to a human-readable status info string.
    status_info_json = json.loads(status_info_json_str)
    status_info = status_info_json.get("action", "Unknown")

    if "error" in status_info_json and status_info_json['error']:
        status_info += f": {status_info_json['error']}"

    if status_info_json["action"] != 'Starting':
        for key in ["com_port", "fastboot_sn", "progress", "duration"]:
            if key in status_info_json:
                if key == "fastboot_sn":
                    status_info += f" (SN: {status_info_json[key]})"
                elif key == "com_port":
                    status_info += f" (COM Port: {status_info_json[key]})"
                else:
                    status_info += f" ({key.replace('_', ' ').title()}: {status_info_json[key]})"

    return status_info

def update_status_display(json_data):
    # Print the status information to the console.
    print(MENU_STR)
    for id, status_info_json_str in json_data:
        print(f"Worker {id} status: {status_json_to_info(status_info_json_str)}")

def update_status_display_gui(stdscr, json_data):
    # Update the status display in the GUI.
    stdscr.clear()
    stdscr.addstr(0, 0, MENU_STR)
    for row, (id, status_info_json_str) in enumerate(json_data, start=1):
        stdscr.addstr(row, 0, f"Worker {id} status: {status_json_to_info(status_info_json_str)}")
    stdscr.refresh()

def cleanup(daemon_process):
    # Terminate the daemon process and its children.
    if daemon_process:
        if platform.system() == 'Windows':
            try:
                parent = psutil.Process(daemon_process.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
                psutil.wait_procs([parent], timeout=5)
            except psutil.NoSuchProcess:
                pass
        else:
            daemon_process.terminate()
            daemon_process.wait()

def gui_main(stdscr, args):
    # Main loop for the GUI mode.
    curses.curs_set(0)  # Hide cursor
    stdscr.nodelay(True)  # Non-blocking mode
    sock = None
    try:
        while not exit_program:
            if sock is None:
                sock = create_socket(args.host, args.port)
                if sock is None:
                    stdscr.addstr(1, 0, "Waiting for daemon to start...")
                    stdscr.refresh()
                    time.sleep(1)
                    continue

            response = get_daemon_status(sock)
            if response is None:
                sock = None
                continue

            response_body = response.split(b'\r\n\r\n', 1)[1]
            try:
                json_data = json.loads(response_body.decode('utf-8'))
            except json.JSONDecodeError:
                continue  # Skip this iteration if JSON is invalid

            update_status_display_gui(stdscr, json_data)

            stdscr.refresh()
            time.sleep(1)
    except KeyboardInterrupt:
        pass  # Ctrl-C to quit
    finally:
        if sock:
            sock.close()
        cleanup(args.daemon_process)

def key_listener():
    global exit_program
    while not exit_program:
        if platform.system() == 'Windows':
            if keyboard.is_pressed('q'):
                exit_program = True
        else:
            # Linux
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0] and sys.stdin.read(1) == 'q':
                exit_program = True
        time.sleep(0.1)  # Sleep briefly to avoid high CPU usage

def main():
    # Main entry point of the script.
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

    # Start the key listener thread
    listener_thread = threading.Thread(target=key_listener)
    listener_thread.start()

    if args.gui:
        curses.wrapper(gui_main, args)
    else:
        sock = None
        try:
            while not exit_program:
                if sock is None:
                    sock = create_socket(args.host, args.port)
                    if sock is None:
                        print("Waiting for daemon to start...")
                        time.sleep(1)
                        continue

                response = get_daemon_status(sock)
                if response is None:
                    sock = None
                    continue

                response_body = response.split(b'\r\n\r\n', 1)[1]
                try:
                    json_data = json.loads(response_body.decode('utf-8'))
                except json.JSONDecodeError:
                    continue  # Skip this iteration if JSON is invalid

                update_status_display(json_data)

                time.sleep(1)
        except KeyboardInterrupt:
            pass  # Ctrl-C to quit
        finally:
            if sock:
                sock.close()
            cleanup(args.daemon_process)

    # Wait for the listener thread to finish
    listener_thread.join()

if __name__ == "__main__":
    main()
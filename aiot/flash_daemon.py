# SPDX-License-Identifier: MIT
# Copyright 2024 (c) MediaTek Inc.
# Author: Macpaul Lin <macpaul.lin@mediatek.com>

import json
import os
import platform
import psutil
import time
import threading
import socket

from .flash_worker import GenioFlashWorker

class GenioFlashDaemon:
    def __init__(self, args=None, image=None):
        # Initialize the GenioFlashDaemon with provided arguments and image, set up workers and status tracking.
        self.pid = os.getpid()
        self.max_processes = args.workers
        self.args = args
        self.image = image
        self.status_lock = threading.Lock()
        self.statuses = [{"id": i, "action": "Stopped", "error": ""} for i in range(self.max_processes)]
        self.last_start_time = time.time() - 5
        self.workers = [GenioFlashWorker(i, image=image, args=args, daemon=self) for i in range(self.max_processes)]
        self.action_update_thread = threading.Thread(target=self.update_status_all)
        self.action_update_thread.start()
        self.assigned_sn = set()

    def status_json_to_info(self, status_info_json_str):
        # Convert a JSON string containing status information into a human-readable format.
        status_info_json = json.loads(status_info_json_str)

        status_info = status_info_json["action"]

        if "error" in status_info_json and status_info_json['error']:
            status_info += f": {status_info_json['error']}"

        if status_info_json["action"] not in ['Starting']:
            if "com_port" in status_info_json:
                status_info += f" (COM port: {status_info_json['com_port']})"
            if "fastboot_sn" in status_info_json:
                status_info += f" (SN: {status_info_json['fastboot_sn']})"
            if "progress" in status_info_json:
                status_info += f" (Progress: {status_info_json['progress']})"
            if "duration" in status_info_json:
                status_info += f" (Duration: {status_info_json['duration']})"

        return status_info

    def assign_sn(self, worker):
        # Assign a serial number (SN) to the specified worker if it is not already assigned.
        if isinstance(worker.shared_properties["fastboot_sn"], list):
            new_fastboot_sn = [sn for sn in worker.shared_properties["fastboot_sn"] if sn not in self.assigned_sn]

            if len(new_fastboot_sn) > 1:
                print("Error: More than one new fastboot device connected. Please connect only one at a time.")
                print(f"Error: New fastboot devices: {new_fastboot_sn}")
                return

            self.assigned_sn.update(new_fastboot_sn)

            for sn in new_fastboot_sn:
                worker.flasher.fastboot_sn = sn
                worker.shared_properties["fastboot_sn"] = sn  # Update the dictionary

            if isinstance(worker.flasher.fastboot_sn, str) and worker.flasher.fastboot_sn is not None:
                print("Error: worker.flasher.fastboot_sn should be a string.")
                print(f"Error: worker.fastboot_sn: {worker.shared_properties['fastboot_sn']}")
                print(f"Error: worker.flasher.fastboot_sn: {worker.flasher.fastboot_sn}")

    def assign_sn_flasher(self, fastboot_sn):
        # Assign a serial number (SN) to the flasher based on the provided list of fastboot SNs.
        if isinstance(fastboot_sn, list):
            new_fastboot_sn = [sn for sn in fastboot_sn if sn not in self.assigned_sn]
            if len(new_fastboot_sn) > 1:
                print("Error: Please do not connect more than one new fastboot device at the same time.")
                print(f"Error: New fastboot devices: {new_fastboot_sn}")
            self.assigned_sn.update(new_fastboot_sn)
            return "".join(new_fastboot_sn) if new_fastboot_sn else None
        return None

    def update_status_all(self):
        # Continuously update the status of all workers and store the information in a JSON format.
        while True:
            for worker in self.workers:
                if worker.update_event.is_set():
                    status_info_json_str = worker.get_status_json()
                    # Assign updated status information to the corresponding worker
                    self.statuses[worker.id] = json.loads(status_info_json_str)

                worker.update_event.clear()  # Clear the event after processing

            time.sleep(1)

    def start_workers(self):
        # Monitor and start workers when there are no previous workers in beginning states.
        while True:
            time.sleep(1)
            if not any(worker.action in ["Starting", "Opening", "Jumping DA"] for worker in self.workers):
                self.start_next_worker()

    def start_next_worker(self):
        # Start the next available worker if the time since the last start exceeds a threshold.
        current_time = time.time()
        if current_time - self.last_start_time >= 5:
            for worker in self.workers:
                if worker.action == "Stopped" and not worker.is_alive():
                    worker.start()
                    self.last_start_time = current_time
                    return True
        return False

    def handle_client_connection(self, client_socket):
        # Handle incoming client connections and send the current status as a JSON response.
        try:
            while True:
                with self.status_lock:
                    status_json = json.dumps(self.statuses, indent=4)
                response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(status_json)}\r\n\r\n{status_json}"
                client_socket.sendall(response.encode('utf-8'))
                time.sleep(1)
        except (ConnectionAbortedError, ConnectionResetError):
            print("Client connection closed.")
        finally:
            client_socket.close()

    def start_socket_server(self, host, port):
        # Start a socket server to listen for client connections on the specified host and port.
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((host, port))
        server_socket.listen(5)
        print(f"Daemon is running on {host}:{port}")

        while True:
            client_socket, addr = server_socket.accept()
            print(f"Accepted connection from {addr}")
            client_handler = threading.Thread(target=self.handle_client_connection, args=(client_socket,))
            client_handler.start()

    def terminate_processes(self, processes):
        # Terminate specified processes that are currently running.
        print(f"Trying to kill legacy processes: {processes}...")
        for _ in range(2):
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] in processes:
                        proc.terminate()
                        print(f"Successfully terminated {proc.info['name']} (PID: {proc.info['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
                    print(f"Failed to terminate {proc.info['name']}: {e}")
            time.sleep(1)

    def cleanup_aiot_tools(self):
        # Clean up legacy executables based on the operating system.
        if platform.system() == 'Windows':
            self.terminate_processes(["aiot-bootrom.exe", "fastboot.exe"])
        elif platform.system() == 'Linux':
            self.terminate_processes(["aiot-bootrom", "fastboot"])

    def run(self):
        # Run the main loop of the daemon, handling socket connections and worker management.
        # Do not call cleanup_aiot_tools() here. Leave this work to flash.py for avoiding incorrect kill.
        self.assigned_sn = set()

        if self.args.verbose:
            print(f"Daemon PID {self.pid}")

        if self.args.port and self.args.host:
            self.start_socket_server(self.args.host, self.args.port)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Daemon shutting down...")
            for event in self.events:
                event.set()
            for worker in self.workers:
                worker.join()

if __name__ == "__main__":
    main()
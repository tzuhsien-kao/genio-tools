# SPDX-License-Identifier: MIT
# Copyright 2024 (c) MediaTek Inc.
# Author: Macpaul Lin <macpaul.lin@mediatek.com>

import json
import multiprocessing
import os
import platform
import psutil
import time
import threading
import socket

from .flash_worker import GenioFlashWorker

class GenioFlashDaemon:
    def __init__(self, args=None, image=None):
        self.pid = os.getpid()
        self.max_processes = args.workers
        self.args = args
        self.image = image
        self.status_lock = threading.Lock()
        self.statuses = []
        self.last_start_time = time.time() - 5
        self.workers = [GenioFlashWorker(i, image=image, args=args) for i in range(self.max_processes)]
        self.action_update_thread = threading.Thread(target=self.update_status_all)
        self.action_update_thread.start()

    def status_json_to_info(self, status_info_json_str):
        status_info_json = json.loads(status_info_json_str)

        status_info = ""
        status_info += status_info_json["action"]

        if "error" in status_info_json and status_info_json['error'] != "":
                status_info += f": {status_info_json['error']}"

        if status_info_json["action"] not in ['Starting']:
            if "com_port" in status_info_json:
                status_info += f" (COM port: {status_info_json['com_port']})"
            if "fastboot_sn" in status_info_json:
                status_info += f" (SN: {status_info_json['fastboot_sn']})"
            if "progress" in status_info_json:
                status_info += f" (Progress: {status_info_json['progress']})"
            if status_info_json["action"] not in ["rebooting"]:
                if "duration" in status_info_json:
                    status_info += f" (Duration: {status_info_json['duration']})"
            else:
                status_info += f" (Duration: {status_info_json['duration']})"
    
        return status_info

    def get_worker_status_json(self, worker):
        status_info = {
            "action": worker.action,
            "id": worker.id,
            "pid": worker.pid,
            "error": "",
            "com_port": worker.com_port if worker.action not in ["Starting"] else None,
            "fastboot_sn": worker.fastboot_sn if worker.action not in ["Starting"] else None,
            "progress": worker.progress if worker.action not in ["Starting"] else None,
            "duration": None
        }

        if worker.action == "Jumping DA":
            worker.start_time = time.time()

        if worker.action == "Starting" and worker.error:
            status_info["error"] = worker.error
            worker.error = ""

        if worker.action not in ["Starting", "rebooting"] and worker.start_time is not None:
            worker.total_duration = round(time.time() - worker.start_time, 2)
            status_info["duration"] = f"{worker.total_duration}s"
        elif worker.action == "rebooting":
            status_info["duration"] = f"{worker.total_duration}s"

        # Remove keys with None values
        status_info = {k: v for k, v in status_info.items() if v is not None}

        return json.dumps(status_info, indent=4)

    def update_status_all(self):
        while True:
            statuses = []
            for worker in self.workers:
                status_info_json_str = self.get_worker_status_json(worker)
                statuses.append((worker.id, status_info_json_str))
                if self.args.port and self.args.host:
                    with self.status_lock:
                        self.current_status_json = status_info_json_str
            self.statuses = json.dumps(statuses, indent=4)
            time.sleep(1)

    def start_workers(self):
        while True:
            time.sleep(1)
            starting = [p for p in self.workers if p.action in ["Starting", "Opening", "Jumping DA"]]
            if len(starting) < 1:
                self.start_next_worker()

    def start_next_worker(self):
        current_time = time.time()
        if current_time - self.last_start_time >= 5:
            for worker in self.workers:
                if worker.action in ["Stopped"]:
                    worker.process = multiprocessing.Process(target=worker.start)
                    worker.process.start()
                    worker.monitor()
                    self.last_start_time = current_time
                    return True
        return False

    def handle_client_connection(self, client_socket):
        try:
            while True:
                with self.status_lock:
                    status_json = self.statuses
                response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(status_json)}\r\n\r\n{status_json}"
                client_socket.sendall(response.encode('utf-8'))
                time.sleep(1)
        except (ConnectionAbortedError, ConnectionResetError):
            print("Client connection closed.")
        finally:
            client_socket.close()

    def start_socket_server(self, host, port):
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
        """Terminate specified processes."""
        print(f"Trying to kill legacy {processes}...")
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
        # Kill all legacy executables based on the platform
        if platform.system() == 'Windows':
            self.terminate_processes(["aiot-bootrom.exe", "fastboot.exe"])
        elif platform.system() == 'Linux':
            self.terminate_processes(["aiot-bootrom", "fastboot"])

    def run(self):
        # Do not call cleanup_aiot_tools() here. Leave this work to flash.py for avoiding incorrect kill.

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
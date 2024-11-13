# SPDX-License-Identifier: MIT
# Copyright 2024 (c) MediaTek Inc.
# Author: Macpaul Lin <macpaul.lin@mediatek.com>

import json
import re

# Pre-compile regular expressions for log parsing
patterns = {
    "com_port": re.compile(r"Opening (\/dev\/ttyACM\d+|COM\d+) using baudrate=(\d+)"),
    "hw_code": re.compile(r"Connected to MediaTek SoC: hw_code\[(0x[0-9a-fA-F]+)\]"),
    "address": re.compile(r"Sending bootstrap to address: (0x[0-9a-fA-F]+)"),
    "jumping": re.compile(r"Jumping to bootstrap at address (0x[0-9a-fA-F]+) in (AArch64) mode")
}

action_messages = {
    "Opening": "Opening",
    "Sending bootstrap": "Sending DA",
    "Jumping to bootstrap": "Jumping DA"
}

def parse_log_line(line, result):
    # Parse a single line of the log and update the result dictionary.
    if "Opening" in line:
        result["action"] = action_messages["Opening"]
        match = patterns["com_port"].search(line)
        if match:
            result["com_port"], result["baudrate"] = match.groups()
    elif "Connected to MediaTek SoC" in line:
        match = patterns["hw_code"].search(line)
        if match:
            result["hw_code"] = match.group(1)
    elif "Sending bootstrap to address" in line:
        result["action"] = action_messages["Sending bootstrap"]
        match = patterns["address"].search(line)
        if match:
            result["address"] = match.group(1)
    elif "Jumping to bootstrap" in line:
        result["action"] = action_messages["Jumping to bootstrap"]
        match = patterns["jumping"].search(line)
        if match:
            result["address"], result["mode"] = match.groups()

def bootrom_log_parser(log):
    # Parse the bootrom log and convert it to JSON.
    if log is None:
        return json.dumps({"error": "No log output"}, indent=4)

    result = {
        "action": "",
        "com_port": "",
        "baudrate": "",
        "hw_code": "",
        "address": "",
        "mode": ""
    }

    # Parse the log line by line
    for line in log.splitlines():
        parse_log_line(line, result)

    return json.dumps(result, indent=4)

    # Parse the log line by line
    for line in log.splitlines():
        parse_log_line(line, result)

    return json.dumps(result, indent=4)
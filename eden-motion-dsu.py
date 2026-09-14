#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Point Eden's Player 1 motion at the DSU relay (127.0.0.1:26761). Close Eden before running.

Only these keys in [Controls] are touched; a backup is written next to the file first:
  player_0_motionleft, player_0_motionright, udp_input_servers (and their \\default flags)
"""
import pathlib
import shutil
import sys
import time

MOTION = '"motion:0,pad:0,port:26761,guid:0000000000000000000000007f000001,engine:cemuhookudp"'
WANTED = {
    "player_0_motionleft": MOTION,
    "player_0_motionright": "[empty]",
    "udp_input_servers": "127.0.0.1:26761",
}


def update(text):
    lines = text.splitlines()
    try:
        start = lines.index("[Controls]")
    except ValueError:
        raise SystemExit("No [Controls] section found: start Eden once, close it, then run this again.")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("[")), len(lines))
    section = lines[start + 1:end]
    wanted = {}
    for key, value in WANTED.items():
        wanted[key + "\\default"] = "false"
        wanted[key] = value
    seen = set()
    for i, line in enumerate(section):
        key = line.split("=", 1)[0]
        if key in wanted:
            section[i] = f"{key}={wanted[key]}"
            seen.add(key)
    section += [f"{key}={value}" for key, value in wanted.items() if key not in seen]
    return "\n".join(lines[:start + 1] + section + lines[end:]) + "\n"


def main():
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path.home() / ".config/eden/qt-config.ini"
    if not path.exists():
        raise SystemExit(f"{path} not found: start Eden once, close it, then run this again.")
    backup = path.with_name(f"{path.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, backup)
    path.write_text(update(path.read_text()))
    print(f"Updated {path}\nBackup  {backup}")


if __name__ == "__main__":
    main()

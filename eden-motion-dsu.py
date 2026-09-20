#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Point Eden's motion inputs at the DSU relay (127.0.0.1:26761). Close Eden before running.

Player 1 uses slot 2 of the relay, player 2 slot 3, player 3 slot 4 (slot 1 is Cemu's, with the
unscaled gyro). Only these keys in [Controls] are touched, and a backup is written first:

  player_<n>_motionleft, player_<n>_motionright, udp_input_servers (and their \\default flags)

Usage:
  eden-motion-dsu.py                 player 1 only
  eden-motion-dsu.py --players 2     players 1 and 2 (two DualSense pads)
  eden-motion-dsu.py --players 2 /path/to/qt-config.ini
"""
import pathlib
import shutil
import sys
import time

FIRST_SLOT = 1  # slot 1 (index 0) carries the unscaled gyro for Cemu


def motion_value(slot):
    return (f'"motion:0,pad:{slot},port:26761,'
            f'guid:0000000000000000000000007f000001,engine:cemuhookudp"')


def wanted_keys(players):
    wanted = {"udp_input_servers": "127.0.0.1:26761"}
    for player in range(players):
        wanted[f"player_{player}_motionleft"] = motion_value(FIRST_SLOT + player)
        wanted[f"player_{player}_motionright"] = "[empty]"
    for key in list(wanted):
        wanted[key + "\\default"] = "false"
    return wanted


def update(text, players):
    lines = text.splitlines()
    try:
        start = lines.index("[Controls]")
    except ValueError:
        raise SystemExit("No [Controls] section found: start Eden once, close it, then run this again.")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("[")), len(lines))
    section = lines[start + 1:end]
    wanted = wanted_keys(players)
    seen = set()
    for i, line in enumerate(section):
        key = line.split("=", 1)[0]
        if key in wanted:
            section[i] = f"{key}={wanted[key]}"
            seen.add(key)
    section += [f"{key}={value}" for key, value in wanted.items() if key not in seen]
    return "\n".join(lines[:start + 1] + section + lines[end:]) + "\n"


def main():
    args = [a for a in sys.argv[1:]]
    players = 1
    if "--players" in args:
        index = args.index("--players")
        players = int(args[index + 1])
        del args[index:index + 2]
    if not 1 <= players <= 3:
        raise SystemExit("--players must be 1, 2 or 3")
    path = pathlib.Path(args[0]) if args else pathlib.Path.home() / ".config/eden/qt-config.ini"
    if not path.exists():
        raise SystemExit(f"{path} not found: start Eden once, close it, then run this again.")
    backup = path.with_name(f"{path.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, backup)
    path.write_text(update(path.read_text(), players))
    slots = ", ".join(f"player {p + 1} -> slot {FIRST_SLOT + p + 1}" for p in range(players))
    print(f"Updated {path} ({slots})\nBackup  {backup}")


if __name__ == "__main__":
    main()

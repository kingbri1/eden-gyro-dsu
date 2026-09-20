# Gyro in Eden and Cemu on ROG Ally X (Bazzite 44+): no DualSense emulation, Steam Input stays on

Working motion controls in **Eden** (Mario Kart 8 Deluxe steering) and **Cemu** (BOTW bow aiming and the
Myahm Agana tilt maze), both handheld and docked with real DualSense pads, keeping Xbox-style glyphs,
Steam Input and the default InputPlumber target.

- **Tested on:** ROG Ally X (BMI323 IMU), Bazzite 44, InputPlumber 0.81 (Steam Deck `deck-uhid` target, the
  default), Steam Input on, Eden v0.2.1 AppImage, Cemu 2.x, a DualSense over Bluetooth, games launched from
  Gaming Mode.
- **Other devices** (Ally, Legion Go S, ...) need their own bridge matrices: see [Other devices](#other-devices).

## Why this setup

- Through InputPlumber's virtual controllers, emulators get broken motion data: the Steam Deck target has an
  unscaled, rotated accelerometer and the DualSense target has a fake sensor timestamp and a bad calibration
  report ([InputPlumber #715](https://github.com/ShadowBlip/InputPlumber/issues/715); fixes are in progress in
  [PR #612](https://github.com/ShadowBlip/InputPlumber/pull/612)). With Steam Input on, emulators only see
  Steam's virtual pad, which has no sensors — and that stays true for a real DualSense too.
- [iio-dsu-bridge](https://github.com/Sebalvarez97/iio-dsu-bridge) reads the handheld IMU and serves it over
  cemuhook/DSU, but the default `rog-ally.yaml` frame reads a sideways tilt as a horizontal rotation: tilt
  puzzles rotate instead of tilting and steering gets stuck. The matrices from
  [issue #15](https://github.com/Sebalvarez97/iio-dsu-bridge/issues/15) fix it for both emulators.
- Eden needs two more things: its DSU gyro is divided by 312 instead of 360, and it samples motion at a fixed
  200 Hz, so a slower or irregular stream makes the steering stick.
- **Fix:** the bridge with the issue #15 matrices, plus a small relay that publishes one DSU server with four
  slots at exactly 200 Hz and picks the motion source automatically — a connected DualSense if there is one,
  the handheld IMU otherwise. Nothing changes in the emulators when you dock or undock.

```
handheld IMU --> iio-dsu-bridge :26760 --\
                                          >--> dsu-relay :26761
DualSense pads (Bluetooth) --------------/         |
                                                   +--> slot 1: main pad, real deg/s   --> Cemu
                                                   +--> slot 2: main pad, x 312/360    --> Eden player 1
                                                   +--> slot 3: second pad             --> Eden player 2
                                                   +--> slot 4: third pad              --> Eden player 3
```

## 1. iio-dsu-bridge (the handheld IMU)

Install it following its README:

```bash
bash <(curl -fsSL https://github.com/Sebalvarez97/iio-dsu-bridge/releases/latest/download/install.sh)
```

Then replace its config with the matrices from issue #15 and restart it:

```bash
cat > ~/.config/iio-dsu-bridge.yaml <<'EOF'
accel_matrix:
  x: [-1, 0, 0]
  y: [0, 0, 1]
  z: [0, -1, 0]

gyro_matrix:
  x: [1, 0, 0]
  y: [0, 0, 1]
  z: [0, -1, 0]
EOF
systemctl --user restart iio-dsu-bridge
```

Nothing else reads this port: the relay is the only client.

## 2. The relay

Needs only Python 3, which Bazzite already ships.

```bash
mkdir -p ~/.local/bin ~/.config/systemd/user
curl -fL https://gist.githubusercontent.com/SimpleMatt7/64b5b9d68045338f9cfa754a8f4f2a3d/raw/dsu-relay -o ~/.local/bin/dsu-relay && chmod +x ~/.local/bin/dsu-relay
curl -fL https://gist.githubusercontent.com/SimpleMatt7/64b5b9d68045338f9cfa754a8f4f2a3d/raw/dsu-relay-eden.service -o ~/.config/systemd/user/dsu-relay-eden.service
systemctl --user daemon-reload && systemctl --user enable --now dsu-relay-eden.service
```

Check that both ports are open:

```bash
ss -uln | grep -E ':2676[01]'
```

## 3. Cemu

In *Options > Input settings*, for the **Wii U GamePad** (the Pro Controller has no gyro on Wii U, so motion
aiming needs the GamePad):

- add a controller with API **DSUController**, **Controller 1** (that is slot 1), and tick **Use motion**;
- in its server settings use **127.0.0.1** and port **26761**;
- add your normal pad (the Steam Virtual Gamepad) for the buttons, with motion **off**.

Keep it as a profile, so it survives experiments.

## 4. Eden

1. Launch Eden **from Gaming Mode** (in Desktop Mode it does not see the controller). In
   *Emulation > Configure > Controls*, set Player 1 to Pro Controller and map the buttons to
   **Steam Virtual Gamepad**. Close Eden.
2. Point the motion inputs at the relay (a backup of `qt-config.ini` is written first):

```bash
curl -fL https://gist.githubusercontent.com/SimpleMatt7/64b5b9d68045338f9cfa754a8f4f2a3d/raw/eden-motion-dsu.py -o /tmp/eden-motion-dsu.py && python3 /tmp/eden-motion-dsu.py
```

It sets, in `~/.config/eden/qt-config.ini`:

```ini
player_0_motionleft="motion:0,pad:1,port:26761,guid:0000000000000000000000007f000001,engine:cemuhookudp"
player_0_motionright=[empty]
udp_input_servers=127.0.0.1:26761
```

For a non-AppImage install, pass the path to your `qt-config.ini` as an argument.

Leave Steam Input **on** (default) and keep the default InputPlumber target.

## 5. Check it

```bash
journalctl --user -u dsu-relay-eden -n 5 --no-pager
```

You should see a line like `motion sources -> slot 1: handheld IMU (bridge), slot 2: handheld IMU (bridge)`,
and after a minute of play a line with the rates and the number of subscribers.

To see the sources and their slots live, with the values they report:

```bash
dsu-relay --sources 20
```

Lying flat, screen (or buttons) up, every source should read about `0.00 -1.00 0.00` on the accelerometer.

## 6. Docked, with one or more DualSense pads

Nothing to configure: turn a pad on and the relay uses its sensors; turn it off and it goes back to the
handheld IMU. Steam Input keeps feeding the buttons to the emulators as usual.

For local multiplayer with motion, connect the pads **in player order** (the first one to connect is player 1)
and give Eden's player 2 the third slot:

```bash
python3 /tmp/eden-motion-dsu.py --players 2
```

`dsu-relay --sources` shows which pad (by Bluetooth address) is on which slot.

## Troubleshooting

- **No motion in a game:** check `journalctl --user -u dsu-relay-eden -n 5`. `no source` means neither the
  bridge nor a pad is sending; `subscribers 0` means the emulator is not connecting to port 26761.
- **`from bridge 0/s`:** the bridge is not running: `systemctl --user status iio-dsu-bridge`.
- **Cemu says the DSU controller is disconnected:** restart Cemu after changing the port.
- **Do not add `threshold:`** to Eden's motion binding: in testing it disabled the gyro completely.
- **Slow tilts are ignored:** both emulators zero the gyro below about 0.9 °/s (Cemu) and 2.5 °/s (Eden). That
  is their own dead zone, not this setup.

## Other devices

The bridge matrices above were verified on the Ally X. Another handheld needs its own `accel_matrix` and
`gyro_matrix` in the bridge config; the relay does not touch the axes, it only rescales the gyro for Eden's
slots. The DualSense conversion is device-independent. If you work out the matrices for another handheld,
please share them.

## Uninstall

```bash
systemctl --user disable --now dsu-relay-eden.service
rm -f ~/.local/bin/dsu-relay ~/.config/systemd/user/dsu-relay-eden.service
systemctl --user daemon-reload
```

To restore Eden, copy back the `qt-config.ini.bak-*` file created next to `qt-config.ini`, and in Cemu set the
DSU port back to 26760 (or remove the DSU controller).

## Upstream reports

- InputPlumber (Deck/DualSense target IMU): https://github.com/ShadowBlip/InputPlumber/issues/715
- iio-dsu-bridge (`-addr` ignored, second instance halves the rate): https://github.com/Sebalvarez97/iio-dsu-bridge/issues/14
- iio-dsu-bridge (the axis matrices used here): https://github.com/Sebalvarez97/iio-dsu-bridge/issues/15

## Disclosure

The investigation, the relay, the Eden setup script and this guide were written with the help of Claude
(Anthropic), and tested by me on a ROG Ally X.

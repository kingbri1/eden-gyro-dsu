# Gyro in Eden and Cemu on ROG Ally X (Bazzite 44+), Steam Input stays on

Working motion controls in **Eden** (Mario Kart 8 Deluxe steering) and **Cemu** (BOTW bow aiming and the
Myahm Agana tilt maze), both handheld and docked with real DualSense pads, with Steam Input on.

- **Tested on:** ROG Ally X (BMI323 IMU), Bazzite 44 with InputPlumber 0.83 (and earlier with 0.81), Steam
  Input on, Eden v0.2.1 AppImage, Cemu 2.x, a DualSense over Bluetooth, games launched from Gaming Mode.
- **Other devices** (Ally, Legion Go S, ...): see [Other devices](#other-devices).

## Why this setup

- With Steam Input on, emulators only see Steam's virtual pad, which has no sensors — and that stays true for a
  real DualSense too. So motion has to reach the emulators another way: cemuhook/DSU.
- Eden divides DSU gyro values by 312 instead of 360, and it samples motion at a fixed 200 Hz, so a slower or
  irregular stream makes the steering stick.
- **Fix:** a small relay that publishes one DSU server with four slots at exactly 200 Hz and picks the motion
  source automatically: a real DualSense if one is connected, the handheld IMU otherwise. Nothing changes in the
  emulators when you dock or undock.
- Where the handheld IMU comes from depends on your InputPlumber version:
  - **InputPlumber 0.82 or later** (Bazzite 44.20261026 and later): InputPlumber reads the IMU itself, and its
    targets now report it with correct scale
    ([InputPlumber #715](https://github.com/ShadowBlip/InputPlumber/issues/715)). The relay reads it from the
    default **Steam Deck** target (or from the DualSense Edge target, if you use that one). On the Ally X both
    report a frame rotated 180° about X compared with a real pad; the relay corrects it.
  - **InputPlumber 0.81 or earlier:** its targets have broken motion data, so the IMU is read by
    [iio-dsu-bridge](https://github.com/Sebalvarez97/iio-dsu-bridge) with the matrices from
    [issue #15](https://github.com/Sebalvarez97/iio-dsu-bridge/issues/15). With 0.82 or later the bridge stops
    receiving data, because InputPlumber holds the IMU.

```
InputPlumber 0.82+: virtual Steam Deck pad --\
InputPlumber 0.81:  iio-dsu-bridge :26760 ----+--> dsu-relay :26761
real DualSense pads (Bluetooth) -------------/         |
                                                       +--> slot 1: main pad, real deg/s   --> Cemu
                                                       +--> slot 2: main pad, x 312/360    --> Eden player 1
                                                       +--> slot 3: second pad             --> Eden player 2
                                                       +--> slot 4: third pad              --> Eden player 3
```

Check your version with `rpm -q inputplumber`.

## 1a. InputPlumber 0.82 or later: nothing to install

Keep the default **Steam Deck** target in OpenGamepadUI, so Xbox-style glyphs and Steam Input's own gyro keep
working everywhere. The relay reads the motion from that virtual pad's hidraw node, alongside Steam. If you had
iio-dsu-bridge installed, disable it: `systemctl --user disable --now iio-dsu-bridge`.

Skip section 1b.

## 1b. InputPlumber 0.81 or earlier: iio-dsu-bridge

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

Leave Steam Input **on** (default) and keep the default Steam Deck target.

## 5. Check it

```bash
journalctl --user -u dsu-relay-eden -n 5 --no-pager
```

You should see a line like `motion sources -> slot 1: handheld IMU (InputPlumber Deck), slot 2: handheld IMU
(InputPlumber Deck)` (or `handheld IMU (bridge)` with InputPlumber 0.81), and after a minute of play a line with the
rates and the number of subscribers.

To see the sources and their slots live, with the values they report:

```bash
dsu-relay --sources 20
```

Every source should read about `0 -1 0` lying flat (screen or buttons up), `0 0 +1` upright with the screen
facing you, and `-1 0 0` with the right edge up.

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

- **No motion in a game:** check `journalctl --user -u dsu-relay-eden -n 5`. `no source` means nothing is
  sending: with InputPlumber 0.82 or later, run `dsu-relay --sources 5` (a `permission denied` note means your user cannot
  read the virtual Steam Deck hidraw node); with 0.81, check that
  the bridge runs (`systemctl --user status iio-dsu-bridge`). `subscribers 0` means the emulator is not
  connecting to port 26761.
- **Buttons swapped (A/B, X/Y):** Steam Input is off for that game, so the emulator reads the DualSense layout
  directly. Turn Steam Input back on.
- **Cemu says the DSU controller is disconnected:** restart Cemu after changing the port.
- **Do not add `threshold:`** to Eden's motion binding: in testing it disabled the gyro completely.
- **Slow tilts are ignored:** both emulators zero the gyro below about 0.9 °/s (Cemu) and 2.5 °/s (Eden). That
  is their own dead zone, not this setup.

## Other devices

Everything here was verified on the Ally X. The conversion of a real DualSense is device-independent. For the
handheld IMU, other devices may differ: with InputPlumber 0.82 or later, check the three poses with
`dsu-relay --sources` (the 180° correction in the relay was measured on the Ally X and may not apply elsewhere);
with 0.81 or earlier, the bridge needs that device's own `accel_matrix`/`gyro_matrix`. If you work out the values
for another handheld, please share them.

## Uninstall

```bash
systemctl --user disable --now dsu-relay-eden.service
rm -f ~/.local/bin/dsu-relay ~/.config/systemd/user/dsu-relay-eden.service
systemctl --user daemon-reload
```

To restore Eden, copy back the `qt-config.ini.bak-*` file created next to `qt-config.ini`; in Cemu remove the
DSU controller.

## Upstream reports

- InputPlumber (Deck/DualSense target IMU): https://github.com/ShadowBlip/InputPlumber/issues/715
- iio-dsu-bridge (`-addr` ignored, second instance halves the rate): https://github.com/Sebalvarez97/iio-dsu-bridge/issues/14
- iio-dsu-bridge (the axis matrices used here): https://github.com/Sebalvarez97/iio-dsu-bridge/issues/15

## Disclosure

The investigation, the relay, the Eden setup script and this guide were written with the help of Claude
(Anthropic), and tested by me on a ROG Ally X.

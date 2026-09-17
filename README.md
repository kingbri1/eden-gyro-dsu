# Gyro in Eden and Cemu on ROG Ally X (Bazzite 44+): no DualSense emulation, Steam Input stays on

Working motion controls in **Eden** (Mario Kart 8 Deluxe motion steering) and **Cemu** (BOTW bow aiming)
at the same time, keeping Xbox-style glyphs, Steam Input and the default InputPlumber target.

- **Tested on:** ROG Ally X (BMI323 IMU), Bazzite 44, InputPlumber 0.79.0 (Steam Deck `deck-uhid` target,
  the default), Steam Input on, Eden v0.2.1 AppImage, Cemu, games launched from Gaming Mode.
- **Other devices** (Ally, Legion Go S, ...) need a different axis conversion: see [Other devices](#other-devices).

## Why this setup

- Through InputPlumber's virtual controllers, Eden gets broken motion data: the Steam Deck target has an unscaled,
  rotated accelerometer and the DualSense target has a fake sensor timestamp and a bad calibration report
  (InputPlumber issue: https://github.com/ShadowBlip/InputPlumber/issues/715). With Steam Input on, Eden only sees Steam's virtual pad, which has no sensors.
- [iio-dsu-bridge](https://github.com/Sebalvarez97/iio-dsu-bridge) reads the IMU directly and serves it over
  cemuhook/DSU. Cemu and Eden need different axis conventions, but running a second bridge halves the sample rate
  (both poll the same sensor), and at ~120 Hz Eden's motion steering gets stuck on one side.
- **Fix:** one bridge for Cemu on port 26760, plus a tiny relay that converts the axes for Eden and republishes on
  port 26761 at a fixed 200 Hz, the rate Eden samples motion for the game.

```
BMI323 --> iio-dsu-bridge :26760 --> Cemu
                   |
                   +--> dsu-relay :26761 (axes for Eden, 200 Hz) --> Eden
```

## 1. iio-dsu-bridge (Cemu)

Install it with the official ROG Ally config, following its README:

```bash
bash <(curl -fsSL https://github.com/Sebalvarez97/iio-dsu-bridge/releases/latest/download/install.sh)
```

The relay expects exactly this config in `~/.config/iio-dsu-bridge.yaml`:

```yaml
mount_matrix:
  x: [1, 0, 0]
  y: [0, -1, 0]
  z: [0, 0, -1]
```

In Cemu's input settings, add the motion source as a DSU (cemuhook) controller at `127.0.0.1:26760`.

## 2. The relay (Eden)

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

## 3. Eden

1. Launch Eden **from Gaming Mode** (in Desktop Mode it does not see the controller). In
   *Emulation → Configure → Controls*, set Player 1 to Pro Controller and map the buttons to
   **Steam Virtual Gamepad**. Close Eden.
2. Point Motion 1 at the relay (a backup of `qt-config.ini` is written first):

```bash
curl -fL https://gist.githubusercontent.com/SimpleMatt7/64b5b9d68045338f9cfa754a8f4f2a3d/raw/eden-motion-dsu.py -o /tmp/eden-motion-dsu.py && python3 /tmp/eden-motion-dsu.py
```

It sets, in `~/.config/eden/qt-config.ini`:

```ini
player_0_motionleft="motion:0,pad:0,port:26761,guid:0000000000000000000000007f000001,engine:cemuhookudp"
player_0_motionright=[empty]
udp_input_servers=127.0.0.1:26761
```

For a non-AppImage install, pass the path to your `qt-config.ini` as an argument.

Leave Steam Input **on** (default) for the Eden shortcut and keep the default InputPlumber target.

## 4. Check it while playing

After a minute with a game running:

```bash
journalctl --user -u dsu-relay-eden -n 3
```

You should see about `from bridge 180/s, sent 200/s, subscribers 1`.

## Troubleshooting

- **`subscribers 0`:** Eden is not connecting. Check that `udp_input_servers=127.0.0.1:26761` is in the ini and
  restart Eden.
- **`from bridge 0/s`:** the bridge is not running: `systemctl --user status iio-dsu-bridge`.
- **Do not add `threshold:`** to the motion binding: in testing it disabled the gyro completely.
- **Motion is 15% fast or slow:** the relay already undoes Eden's hardcoded 1/312 gyro scale; don't compensate twice.

## Other devices

The relay converts from the iio-dsu-bridge `rog-ally.yaml` frame to the frame verified for Eden on the Ally X:
`accel_eden = -accel`, `gyro_eden = 0.866667 * (pitch, -yaw, -roll)`. Another device or config needs another
conversion (`ACCEL_MATRIX`/`GYRO_MATRIX` at the top of `dsu-relay`). If you work one out, please share it.

## Uninstall

```bash
systemctl --user disable --now dsu-relay-eden.service
rm -f ~/.local/bin/dsu-relay ~/.config/systemd/user/dsu-relay-eden.service
systemctl --user daemon-reload
```

To restore Eden, copy back the `qt-config.ini.bak-*` file created next to `qt-config.ini`.

## Upstream reports

- InputPlumber (Deck/DualSense target IMU): https://github.com/ShadowBlip/InputPlumber/issues/715
- iio-dsu-bridge (`-addr` ignored, second instance halves the rate): https://github.com/Sebalvarez97/iio-dsu-bridge/issues/14

## Disclosure

The investigation, the relay, the Eden setup script and this guide were written with the help of Claude (Anthropic),
and tested by me on a ROG Ally X.

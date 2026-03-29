# Spirit Tube TV — Developer Notes

Quick reference for anyone tweaking the code directly (e.g., on the Pi). Covers architecture decisions, known gotchas, and the fixes made during the initial build.

---

## Running the test suite

```bash
python -m pytest tests/ -v        # full suite (55 tests)
python -m pytest tests/test_demodulator.py -v   # just demod
```

Tests run without RTL-SDR hardware. `conftest.py` pre-mocks the `rtlsdr` module before collection.

---

## Architecture quick-map

```
main.py
  └─ BandSelectScreen           → returns 'fm' / 'am' / 'tv' / None from handle_touch()
  └─ FmAmScreen(band)           → .start(sdr, audio) / .stop() / .render(surface)
  └─ TvScreen()                 → .start(sdr, audio) / .stop() / .render(surface)

SdrManager (background thread)
  ├─ _frame_buffer  (H×W uint8 numpy)  ← TV static pixels
  └─ _audio_buffer  (deque maxlen=30)  ← audio chunks for FM/AM

AudioOutput (sounddevice OutputStream)
  └─ queue.Queue(maxsize=10)  ← SDR thread pushes, audio callback drains
```

`SdrManager` and `AudioOutput` are created once in `main.py` and **reused** across mode switches. Each screen's `.start()` wires them up; `.stop()` unhooks them and halts the SDR thread + audio stream completely.

---

## Back button — how clean shutdown works

The spec requires the back tap to fully stop all activity before returning to Band Select. The chain:

1. `main.py` calls `current_screen.stop()`
2. `FmAmScreen.stop()` / `TvScreen.stop()` call both `self._sdr.stop()` AND `self._audio.stop()`
3. `SdrManager.stop()`: sets `_stop_event`, **closes the SDR device first** (so `read_samples()` unblocks), then joins the thread with a 2 s timeout
4. `AudioOutput.stop()`: stops + closes the sounddevice stream, drains the queue, clears the leftover carry buffer

Order matters in step 3: closing the device before joining is intentional. If you join first, the thread blocks forever on `read_samples()`.

---

## SDR signal pipeline

### TV mode
```
RtlSdr.read_samples(N) → complex64 array
  np.abs(iq)           → amplitudes (float)
  tile to H×W pixels   → reshape to (H, W)
  normalize → uint8    → _frame_buffer
```
Frame is retrieved by `TvScreen._update_static()` each render tick and blitted via `pygame.surfarray.blit_array`. surfarray expects `(W, H, 3)`, so the frame is stacked into RGB then transposed: `rgb.transpose(1, 0, 2)`.

The static surface must be created with `.convert()` (display pixel format) for reliable blitting on Pi hardware.

### FM mode
```
sample_rate = 960_000 Hz  (960k ÷ 20 = 48k audio, exact integer)
phase = np.angle(iq[1:] * np.conj(iq[:-1]))
audio = phase[::20] / np.pi    → float32 in [-1, 1]
```
Dividing by π normalizes the discriminator output. Without it audio clips badly.

### AM mode
```
sample_rate = 240_000 Hz  (240k ÷ 5 = 48k audio, exact integer)
envelope = np.abs(iq)
peak = np.max(np.abs(envelope))   ← measured BEFORE decimation
audio = (envelope[::5] - mean) / peak  → float32 in [-1, 1]
```
Peak is measured before decimation so the true signal peak is used for normalization, not the decimated version.

---

## config.py gotchas

- `FM_FREQS` has **206** entries (87.5–108.0 MHz inclusive). Using `range(205)` only gets to 107.9.
- All sample rates are chosen so `sample_rate // AUDIO_RATE` is an exact integer (no fractional resampling).
- `TV_FRAME_WIDTH` and `TV_FRAME_HEIGHT` are derived from screen dims minus header and button row — these are what `iq_to_frame` uses to size the pixel array.

---

## AudioOutput ring buffer

- `queue.Queue(maxsize=10)` — bounded to prevent runaway RAM on slow Pi
- `push()` uses `put_nowait` and silently drops the **newest** chunk (not oldest) on full — keeps the audio stream flowing with older buffered audio rather than stalling the SDR thread
- `_callback` carries over leftover samples between calls to avoid clicks at chunk boundaries
- `start()` is idempotent — safe to call multiple times

---

## SdrManager threading

- Uses `threading.Event` (`_stop_event`) for the stop signal — bare booleans are not reliably visible across threads in CPython
- `_audio_buffer` is a `deque(maxlen=30)` — hard cap prevents RAM exhaustion if audio isn't being drained
- Double-start guard: `if self._thread is not None and self._thread.is_alive(): return`
- All buffer access is under `threading.Lock`

---

## UI components

`ui/components.py` draws everything with geometric shapes — no font dependency for buttons, so it works at any resolution without font loading.

Transport button layout (`make_transport_rects`): 5 buttons centered in the button row. The loop adds margin **between** buttons only (not after the last), so the group stays properly centered.

Signal bars threshold uses `<=` (not `<`) so the meter reaches full at magnitude 1.0.

---

## Tuning / tweaking

| What to change | Where |
|----------------|-------|
| Scan dwell time | `config.SCAN_DWELL_MS` (default 1500 ms) |
| FM sample rate / decimation | `config.FM_SAMPLE_RATE`, `config.FM_DECIMATE` |
| AM sample rate / decimation | `config.AM_SAMPLE_RATE`, `config.AM_DECIMATE` |
| TV sample rate | `config.TV_SAMPLE_RATE` |
| Audio output rate | `config.AUDIO_RATE` (must keep sample_rate / decimate = AUDIO_RATE) |
| Colors | `config.BG_COLOR`, `config.ACCENT_COLOR`, `config.DIM_ACCENT`, `config.HEADER_BG` |
| Screen dimensions | `config.SCREEN_WIDTH`, `config.SCREEN_HEIGHT` |
| Button row height | `config.BUTTON_ROW_HEIGHT` |
| Header height | `config.HEADER_HEIGHT` |
| Target FPS | `config.TARGET_FPS` |

---

## Hardware notes (RTL-SDR V3)

- Chipset: R820T2 + RTL2832U — supported by stock `librtlsdr` via `apt install rtl-sdr`
- USB IDs: `0bda:2838` (most dongles) and `0bda:2832`
- The `dvb_usb_rtl28xxu` kernel module conflicts and must be blacklisted (`/etc/modprobe.d/rtlsdr.conf`) — takes effect after reboot
- User must be in the `plugdev` group to access the USB device without sudo — `install.sh` handles this, but the group membership only activates after reboot/re-login

---

## Autostart

`install.sh` deploys `autostart/spirit-tube-tv.desktop` to `~/.config/autostart/` with the `__INSTALL_DIR__` placeholder replaced by the actual install path. Edit the source file in `autostart/` and re-run `./install.sh` if you move the project folder.

To disable autostart without uninstalling:
```bash
rm ~/.config/autostart/spirit-tube-tv.desktop
```

---

## Related docs

- `docs/superpowers/specs/2026-03-29-spirit-tube-tv-design.md` — full design spec
- `docs/superpowers/plans/2026-03-29-spirit-tube-tv.md` — original implementation plan with all task code

# screens/fm_am_screen.py
import collections
import numpy as np
import pygame
import config
from ui.components import (draw_button, draw_waveform, draw_signal_bars,
                            make_transport_rects, make_slider_rect,
                            draw_scan_slider, handle_slider_touch,
                            make_volume_rect, draw_volume_slider,
                            handle_volume_touch)
from ui.number_pad import NumberPad
from sdr.recorder import AudioRecorder

_BACK_RECT   = pygame.Rect(8, 6, 60, 32)
_REC_RECT    = pygame.Rect(config.SCREEN_WIDTH - 68, 6, 60, 32)
_FREQ_RECT   = pygame.Rect(200, 2, 400, 40)   # tap target for frequency display
_FREQ_FONT   = None
_LABEL_FONT  = None

def _init_fonts():
    global _FREQ_FONT, _LABEL_FONT
    if _FREQ_FONT is None:
        _FREQ_FONT  = pygame.font.SysFont('freesans', 30, bold=True)
        _LABEL_FONT = pygame.font.SysFont('freesans', 14)


class FmAmScreen:
    SCAN_NONE     = 'none'
    SCAN_FORWARD  = 'forward'
    SCAN_BACKWARD = 'backward'

    def __init__(self, band: str):
        self.band       = band
        self._freqs     = config.FM_FREQS if band == 'fm' else config.AM_FREQS
        self._freq_idx  = 0
        self._scan_state = self.SCAN_NONE
        self._last_scan_ms = 0
        self._waveform  = collections.deque(
            np.zeros(config.WAVEFORM_SAMPLES, dtype=np.float32),
            maxlen=config.WAVEFORM_SAMPLES,
        )
        self._signal_mag = 0.0
        self._scan_dwell_s = config.SCAN_DWELL_DEFAULT_S
        self._sdr   = None
        self._audio = None
        self._recorder = AudioRecorder(band)
        self._numpad: NumberPad | None = None
        self._btn_rects: dict[str, pygame.Rect] = make_transport_rects(
            config.SCREEN_WIDTH, config.SCREEN_HEIGHT
        )
        self._slider_rect: pygame.Rect = make_slider_rect(
            config.SCREEN_WIDTH, config.SCREEN_HEIGHT
        )
        self._vol_rect: pygame.Rect = make_volume_rect(
            config.SCREEN_WIDTH, config.SCREEN_HEIGHT
        )

    # ------------------------------------------------------------------

    def start(self, sdr, audio) -> bool:
        self._sdr   = sdr
        self._audio = audio
        self._audio.start()
        if not self._sdr.start(self.band, self._freqs[self._freq_idx]):
            self._audio.stop()
            self._sdr = None
            self._audio = None
            return False
        return True

    def stop(self) -> None:
        self._scan_state = self.SCAN_NONE
        if self._recorder.recording:
            self._recorder.stop()
        if self._sdr:
            self._sdr.stop()
        if self._audio:
            self._audio.stop()

    # ------------------------------------------------------------------

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        # If numpad is open, route all touches to it
        if self._numpad is not None and self._numpad.active:
            result = self._numpad.handle_touch(pos)
            if result == 'go':
                self._apply_numpad_value(self._numpad.value)
                self._numpad = None
            elif result == 'cancel':
                self._numpad = None
            return None

        if _BACK_RECT.collidepoint(pos):
            return 'back'

        # Record button
        if _REC_RECT.collidepoint(pos):
            if self._recorder.recording:
                self._recorder.stop()
            else:
                self._recorder.start()
            return None

        # Tap frequency display to open numpad
        if _FREQ_RECT.collidepoint(pos):
            self._scan_state = self.SCAN_NONE
            self._numpad = NumberPad(self.band)
            return None

        # Volume slider
        vol = handle_volume_touch(pos, self._vol_rect)
        if vol is not None:
            if self._audio:
                self._audio.volume = vol
            return None

        # Scan speed slider
        slider_val = handle_slider_touch(pos, self._slider_rect)
        if slider_val is not None:
            self._scan_dwell_s = slider_val
            return None

        for name, rect in self._btn_rects.items():
            if rect.collidepoint(pos):
                self._on_button(name)
                return None
        return None

    def _apply_numpad_value(self, text: str) -> None:
        """Find nearest valid frequency from user input and tune to it."""
        if not text:
            return
        try:
            val = float(text)
        except ValueError:
            return
        if self.band == 'fm':
            target_hz = int(val * 1_000_000)
        else:
            target_hz = int(val * 1_000)
        # Find nearest frequency in the list
        best_idx = min(range(len(self._freqs)),
                       key=lambda i: abs(self._freqs[i] - target_hz))
        self._freq_idx = best_idx
        if self._sdr:
            self._sdr.tune(self._freqs[self._freq_idx])

    def _on_button(self, name: str) -> None:
        if name == 'scan_fwd':
            self._scan_state = self.SCAN_FORWARD
            self._last_scan_ms = pygame.time.get_ticks()
        elif name == 'scan_back':
            self._scan_state = self.SCAN_BACKWARD
            self._last_scan_ms = pygame.time.get_ticks()
        elif name == 'pause':
            self._scan_state = self.SCAN_NONE
        elif name == 'next':
            self._step(+1)
        elif name == 'prev':
            self._step(-1)

    def _step(self, direction: int) -> None:
        self._freq_idx = (self._freq_idx + direction) % len(self._freqs)
        if self._sdr:
            self._sdr.tune(self._freqs[self._freq_idx])

    # ------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        _init_fonts()
        self._update_scan()
        self._pull_audio()
        surface.fill(config.BG_COLOR)
        self._draw_header(surface)
        self._draw_signal_area(surface)
        self._draw_buttons(surface)
        # Volume slider
        vol = self._audio.volume if self._audio else 0.25
        draw_volume_slider(surface, self._vol_rect, vol)
        # Number pad overlay (drawn last, on top of everything)
        if self._numpad is not None and self._numpad.active:
            self._numpad.render(surface)

    # ------------------------------------------------------------------

    def _update_scan(self) -> None:
        if self._scan_state == self.SCAN_NONE:
            return
        now = pygame.time.get_ticks()
        if now - self._last_scan_ms >= self._scan_dwell_s * 1000:
            self._last_scan_ms = now
            self._step(+1 if self._scan_state == self.SCAN_FORWARD else -1)

    def _pull_audio(self) -> None:
        if self._sdr is None or self._audio is None:
            return
        chunk = self._sdr.get_audio_chunk()
        if chunk is not None and len(chunk) > 0:
            self._audio.push(chunk)
            self._waveform.extend(chunk[-config.WAVEFORM_SAMPLES:])
            self._signal_mag = float(np.clip(np.abs(chunk).mean() * 4, 0.0, 1.0))
            # Record if active
            if self._recorder.recording:
                self._recorder.write(chunk)

    def _draw_header(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, config.HEADER_BG,
                         (0, 0, config.SCREEN_WIDTH, config.HEADER_HEIGHT))
        # Back button
        draw_button(surface, _BACK_RECT, 'back')
        # Record button
        icon = 'recording' if self._recorder.recording else 'record'
        draw_button(surface, _REC_RECT, icon, active=self._recorder.recording)
        # Frequency
        freq = self._freqs[self._freq_idx]
        if self.band == 'fm':
            label = f'{freq / 1_000_000:.1f} MHz'
        else:
            label = f'{freq / 1_000:.0f} kHz'
        txt = _FREQ_FONT.render(label, True, config.ACCENT_COLOR)
        surface.blit(txt, txt.get_rect(centerx=config.SCREEN_WIDTH // 2, centery=config.HEADER_HEIGHT // 2))
        # Mode label
        mode_txt = _LABEL_FONT.render(self.band.upper(), True, config.DIM_ACCENT)
        surface.blit(mode_txt, mode_txt.get_rect(right=_REC_RECT.left - 10,
                                                  centery=config.HEADER_HEIGHT // 2))

    def _draw_signal_area(self, surface: pygame.Surface) -> None:
        signal_area_h = config.SCREEN_HEIGHT - config.HEADER_HEIGHT - config.BUTTON_ROW_HEIGHT
        # Waveform: upper 70% of signal area
        waveform_h = int(signal_area_h * 0.70)
        waveform_rect = pygame.Rect(10, config.HEADER_HEIGHT + 8,
                                    config.SCREEN_WIDTH - 20, waveform_h - 16)
        draw_waveform(surface, waveform_rect, np.array(self._waveform))
        # Signal bars: lower 30% of signal area
        bars_y = config.HEADER_HEIGHT + waveform_h
        bars_rect = pygame.Rect(20, bars_y + 4,
                                config.SCREEN_WIDTH - 40,
                                signal_area_h - waveform_h - 8)
        draw_signal_bars(surface, bars_rect, self._signal_mag)

    def _draw_buttons(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, config.HEADER_BG,
                         (0, config.SCREEN_HEIGHT - config.BUTTON_ROW_HEIGHT,
                          config.SCREEN_WIDTH, config.BUTTON_ROW_HEIGHT))
        # Scan speed slider
        draw_scan_slider(surface, self._slider_rect, self._scan_dwell_s)
        # Transport buttons
        icon_map = {
            'prev': 'prev', 'scan_back': 'scan_back',
            'pause': 'play' if self._scan_state == self.SCAN_NONE else 'pause',
            'scan_fwd': 'scan_fwd', 'next': 'next',
        }
        for name, rect in self._btn_rects.items():
            active = (name == 'scan_fwd'  and self._scan_state == self.SCAN_FORWARD) or \
                     (name == 'scan_back' and self._scan_state == self.SCAN_BACKWARD)
            draw_button(surface, rect, icon_map[name], active=active)

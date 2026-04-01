# screens/tv_screen.py
import numpy as np
import pygame
import config
from ui.components import (draw_button, draw_scanline_overlay, make_transport_rects,
                            make_slider_rect, draw_scan_slider, handle_slider_touch,
                            make_volume_rect, draw_volume_slider,
                            handle_volume_touch)
from ui.number_pad import NumberPad
from sdr.recorder import VideoRecorder

_BACK_RECT  = pygame.Rect(8, 6, 60, 32)
_REC_RECT   = pygame.Rect(config.SCREEN_WIDTH - 68, 6, 60, 32)
_CH_RECT    = pygame.Rect(200, 2, 400, 40)   # tap target for channel display
_LABEL_FONT = None
_CH_FONT    = None


def _init_fonts():
    global _LABEL_FONT, _CH_FONT
    if _CH_FONT is None:
        _CH_FONT    = pygame.font.SysFont('freesans', 22, bold=True)
        _LABEL_FONT = pygame.font.SysFont('freesans', 14)


class TvScreen:
    SCAN_NONE     = 'none'
    SCAN_FORWARD  = 'forward'
    SCAN_BACKWARD = 'backward'

    def __init__(self):
        self._ch_idx     = 0
        self._scan_state = self.SCAN_NONE
        self._last_scan_ms = 0
        self._scan_dwell_s = config.SCAN_DWELL_DEFAULT_S
        self._sdr        = None
        self._audio      = None
        self._recorder   = VideoRecorder()
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
        # Pre-allocated surface for static — avoids per-frame allocation
        self._static_surface = pygame.Surface(
            (config.TV_FRAME_WIDTH, config.TV_FRAME_HEIGHT)
        ).convert()

    # ------------------------------------------------------------------

    def start(self, sdr, audio) -> bool:
        self._sdr   = sdr
        self._audio = audio
        ch_num, freq, _band = config.TV_CHANNELS[self._ch_idx]
        self._audio.start()
        if not self._sdr.start('tv', freq):
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

        # Tap channel display to open numpad
        if _CH_RECT.collidepoint(pos):
            self._scan_state = self.SCAN_NONE
            self._numpad = NumberPad('tv')
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
        """Find nearest valid TV channel from user input and tune to it."""
        if not text:
            return
        try:
            target_ch = int(text)
        except ValueError:
            return
        # Find nearest channel number in the list
        best_idx = min(range(len(config.TV_CHANNELS)),
                       key=lambda i: abs(config.TV_CHANNELS[i][0] - target_ch))
        self._ch_idx = best_idx
        if self._sdr:
            _ch_num, freq, _band = config.TV_CHANNELS[self._ch_idx]
            self._sdr.tune(freq)

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
        self._ch_idx = (self._ch_idx + direction) % len(config.TV_CHANNELS)
        if self._sdr:
            _ch_num, freq, _band = config.TV_CHANNELS[self._ch_idx]
            self._sdr.tune(freq)

    # ------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        _init_fonts()
        self._update_scan()
        self._update_static()
        surface.fill(config.BG_COLOR)
        self._draw_header(surface)
        self._draw_static(surface)
        self._draw_buttons(surface)
        # Volume slider (drawn over static, right edge)
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

    def _update_static(self) -> None:
        """Pull latest IQ frame from SDR and blit to static surface."""
        if self._sdr is None:
            return
        try:
            frame = self._sdr.get_frame()
            if frame is not None:
                # frame: (H, W) uint8 grayscale
                # pygame.surfarray.blit_array expects (W, H, 3)
                rgb = np.stack([frame, frame, frame], axis=2)           # (H, W, 3)
                rgb_t = np.ascontiguousarray(rgb.transpose(1, 0, 2))    # (W, H, 3)
                pygame.surfarray.blit_array(self._static_surface, rgb_t)
                # Record frame if active
                if self._recorder.recording:
                    self._recorder.write_frame(frame)

            # Also push audio
            if self._audio is not None:
                chunk = self._sdr.get_audio_chunk()
                if chunk is not None:
                    self._audio.push(chunk)
                    # Record audio if active
                    if self._recorder.recording:
                        self._recorder.write_audio(chunk)
        except Exception:
            pass  # skip bad frame rather than crash

    def _draw_header(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, config.HEADER_BG,
                         (0, 0, config.SCREEN_WIDTH, config.HEADER_HEIGHT))
        draw_button(surface, _BACK_RECT, 'back')
        # Record button
        icon = 'recording' if self._recorder.recording else 'record'
        draw_button(surface, _REC_RECT, icon, active=self._recorder.recording)

        ch_num, freq, band = config.TV_CHANNELS[self._ch_idx]
        ch_label = f'CH {ch_num:02d}  ·  {freq / 1_000_000:.2f} MHz'
        txt = _CH_FONT.render(ch_label, True, config.ACCENT_COLOR)
        surface.blit(txt, txt.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                        centery=config.HEADER_HEIGHT // 2))

        band_txt = _LABEL_FONT.render(band, True, config.DIM_ACCENT)
        surface.blit(band_txt, band_txt.get_rect(right=_REC_RECT.left - 10,
                                                   centery=config.HEADER_HEIGHT // 2))

    def _draw_static(self, surface: pygame.Surface) -> None:
        static_rect = pygame.Rect(
            0, config.HEADER_HEIGHT,
            config.TV_FRAME_WIDTH, config.TV_FRAME_HEIGHT
        )
        surface.blit(self._static_surface, static_rect.topleft)
        draw_scanline_overlay(surface, static_rect)

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

# screens/tv_screen.py
import numpy as np
import pygame
import config
from ui.components import draw_button, draw_scanline_overlay, make_transport_rects

_BACK_RECT  = pygame.Rect(8, 6, 60, 32)
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
        self._sdr        = None
        self._audio      = None
        self._btn_rects: dict[str, pygame.Rect] = make_transport_rects(
            config.SCREEN_WIDTH, config.SCREEN_HEIGHT
        )
        # Pre-allocated surface for static — avoids per-frame allocation
        self._static_surface = pygame.Surface(
            (config.TV_FRAME_WIDTH, config.TV_FRAME_HEIGHT)
        ).convert()

    # ------------------------------------------------------------------

    def start(self, sdr, audio) -> None:
        self._sdr   = sdr
        self._audio = audio
        ch_num, freq, _band = config.TV_CHANNELS[self._ch_idx]
        self._audio.start()
        self._sdr.start('tv', freq)

    def stop(self) -> None:
        self._scan_state = self.SCAN_NONE
        if self._sdr:
            self._sdr.stop()
        if self._audio:
            self._audio.stop()

    # ------------------------------------------------------------------

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        if _BACK_RECT.collidepoint(pos):
            return 'back'
        for name, rect in self._btn_rects.items():
            if rect.collidepoint(pos):
                self._on_button(name)
                return None
        return None

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

    # ------------------------------------------------------------------

    def _update_scan(self) -> None:
        if self._scan_state == self.SCAN_NONE:
            return
        now = pygame.time.get_ticks()
        if now - self._last_scan_ms >= config.SCAN_DWELL_MS:
            self._last_scan_ms = now
            self._step(+1 if self._scan_state == self.SCAN_FORWARD else -1)

    def _update_static(self) -> None:
        """Pull latest IQ frame from SDR and blit to static surface."""
        if self._sdr is None:
            return
        frame = self._sdr.get_frame()
        if frame is not None:
            # frame: (H, W) uint8 grayscale
            # pygame.surfarray.blit_array expects (W, H, 3)
            rgb = np.stack([frame, frame, frame], axis=2)           # (H, W, 3)
            rgb_t = np.ascontiguousarray(rgb.transpose(1, 0, 2))    # (W, H, 3)
            pygame.surfarray.blit_array(self._static_surface, rgb_t)

        # Also push audio
        if self._audio is not None:
            chunk = self._sdr.get_audio_chunk()
            if chunk is not None:
                self._audio.push(chunk)

    def _draw_header(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, config.HEADER_BG,
                         (0, 0, config.SCREEN_WIDTH, config.HEADER_HEIGHT))
        draw_button(surface, _BACK_RECT, 'back')

        ch_num, freq, band = config.TV_CHANNELS[self._ch_idx]
        ch_label = f'CH {ch_num:02d}  ·  {freq / 1_000_000:.2f} MHz'
        txt = _CH_FONT.render(ch_label, True, config.ACCENT_COLOR)
        surface.blit(txt, txt.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                        centery=config.HEADER_HEIGHT // 2))

        band_txt = _LABEL_FONT.render(band, True, config.DIM_ACCENT)
        surface.blit(band_txt, band_txt.get_rect(right=config.SCREEN_WIDTH - 10,
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
        icon_map = {
            'prev': 'prev', 'scan_back': 'scan_back',
            'pause': 'play' if self._scan_state == self.SCAN_NONE else 'pause',
            'scan_fwd': 'scan_fwd', 'next': 'next',
        }
        for name, rect in self._btn_rects.items():
            active = (name == 'scan_fwd'  and self._scan_state == self.SCAN_FORWARD) or \
                     (name == 'scan_back' and self._scan_state == self.SCAN_BACKWARD)
            draw_button(surface, rect, icon_map[name], active=active)

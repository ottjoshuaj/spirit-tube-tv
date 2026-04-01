# screens/spiritbox_screen.py
"""Spirit Box — rapid FM frequency sweep with audio output."""
import collections
import numpy as np
import pygame
import config
from ui.components import draw_button, draw_waveform
from sdr.recorder import AudioRecorder

_BACK_RECT = pygame.Rect(8, 6, 60, 32)
_REC_RECT  = pygame.Rect(config.SCREEN_WIDTH - 68, 6, 60, 32)

_FREQ_FONT  = None
_LABEL_FONT = None
_BIG_FONT   = None


def _init_fonts():
    global _FREQ_FONT, _LABEL_FONT, _BIG_FONT
    if _FREQ_FONT is None:
        _FREQ_FONT  = pygame.font.SysFont('freesans', 30, bold=True)
        _LABEL_FONT = pygame.font.SysFont('freesans', 14)
        _BIG_FONT   = pygame.font.SysFont('freesans', 18, bold=True)


# Slider for sweep speed
_SLIDER_RECT = pygame.Rect(20, config.SCREEN_HEIGHT - 50, config.SCREEN_WIDTH - 40, 30)

# Direction buttons
_DIR_FWD_RECT  = pygame.Rect(config.SCREEN_WIDTH // 2 + 60,
                              config.SCREEN_HEIGHT - 88, 100, 32)
_DIR_REV_RECT  = pygame.Rect(config.SCREEN_WIDTH // 2 - 160,
                              config.SCREEN_HEIGHT - 88, 100, 32)
_DIR_STOP_RECT = pygame.Rect(config.SCREEN_WIDTH // 2 - 40,
                              config.SCREEN_HEIGHT - 88, 80, 32)


class SpiritBoxScreen:
    def __init__(self):
        self._freqs = config.SPIRITBOX_FREQS
        self._freq_idx = 0
        self._dwell_ms = config.SPIRITBOX_DWELL_DEFAULT_MS
        self._direction = 1       # +1 forward, -1 reverse, 0 paused
        self._last_step_ms = 0
        self._sdr = None
        self._audio = None
        self._recorder = AudioRecorder('spiritbox')
        self._waveform = collections.deque(
            np.zeros(config.WAVEFORM_SAMPLES, dtype=np.float32),
            maxlen=config.WAVEFORM_SAMPLES,
        )
        self._audio_energy = 0.0
        self._energy_history = collections.deque(
            [0.0] * 60, maxlen=60
        )

    def start(self, sdr, audio) -> bool:
        self._sdr = sdr
        self._audio = audio
        self._audio.start()
        if not self._sdr.start('fm', self._freqs[self._freq_idx]):
            self._audio.stop()
            self._sdr = None
            self._audio = None
            return False
        self._last_step_ms = pygame.time.get_ticks()
        return True

    def stop(self) -> None:
        if self._recorder.recording:
            self._recorder.stop()
        if self._sdr:
            self._sdr.stop()
        if self._audio:
            self._audio.stop()

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        if _BACK_RECT.collidepoint(pos):
            return 'back'

        if _REC_RECT.collidepoint(pos):
            if self._recorder.recording:
                self._recorder.stop()
            else:
                self._recorder.start()
            return None

        if _DIR_FWD_RECT.collidepoint(pos):
            self._direction = 1
            return None
        if _DIR_REV_RECT.collidepoint(pos):
            self._direction = -1
            return None
        if _DIR_STOP_RECT.collidepoint(pos):
            self._direction = 0
            return None

        # Slider touch
        if _SLIDER_RECT.collidepoint(pos):
            frac = (pos[0] - _SLIDER_RECT.x) / _SLIDER_RECT.width
            frac = max(0.0, min(1.0, frac))
            rng = config.SPIRITBOX_DWELL_MAX_MS - config.SPIRITBOX_DWELL_MIN_MS
            self._dwell_ms = config.SPIRITBOX_DWELL_MIN_MS + frac * rng
            return None

        return None

    def render(self, surface: pygame.Surface) -> None:
        _init_fonts()
        self._sweep()
        self._pull_audio()
        surface.fill(config.BG_COLOR)
        self._draw_header(surface)
        self._draw_main(surface)
        self._draw_controls(surface)

    # ------------------------------------------------------------------

    def _sweep(self) -> None:
        if self._direction == 0:
            return
        now = pygame.time.get_ticks()
        if now - self._last_step_ms >= self._dwell_ms:
            self._last_step_ms = now
            self._freq_idx = (self._freq_idx + self._direction) % len(self._freqs)
            if self._sdr:
                self._sdr.tune(self._freqs[self._freq_idx])

    def _pull_audio(self) -> None:
        if self._sdr is None or self._audio is None:
            return
        chunk = self._sdr.get_audio_chunk()
        if chunk is not None and len(chunk) > 0:
            self._audio.push(chunk)
            self._waveform.extend(chunk[-config.WAVEFORM_SAMPLES:])
            energy = float(np.abs(chunk).mean())
            self._audio_energy = energy
            self._energy_history.append(energy)
            if self._recorder.recording:
                self._recorder.write(chunk)

    def _draw_header(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, config.HEADER_BG,
                         (0, 0, config.SCREEN_WIDTH, config.HEADER_HEIGHT))
        draw_button(surface, _BACK_RECT, 'back')

        icon = 'recording' if self._recorder.recording else 'record'
        draw_button(surface, _REC_RECT, icon, active=self._recorder.recording)

        title = _LABEL_FONT.render('SPIRIT BOX', True, config.ACCENT_COLOR)
        surface.blit(title, title.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                            centery=14))

        freq = self._freqs[self._freq_idx]
        freq_txt = _FREQ_FONT.render(f'{freq / 1_000_000:.1f}', True, config.ACCENT_COLOR)
        surface.blit(freq_txt, freq_txt.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                                   centery=34))

    def _draw_main(self, surface: pygame.Surface) -> None:
        # Waveform — large, central
        wave_rect = pygame.Rect(20, config.HEADER_HEIGHT + 10,
                                config.SCREEN_WIDTH - 40, 140)
        draw_waveform(surface, wave_rect, np.array(self._waveform))

        # Audio energy flash — background tint when audio is loud
        energy = min(self._audio_energy * 8, 1.0)
        if energy > 0.15:
            flash_rect = pygame.Rect(0, config.HEADER_HEIGHT,
                                     config.SCREEN_WIDTH, 160)
            flash_surf = pygame.Surface(flash_rect.size, pygame.SRCALPHA)
            alpha = int(energy * 60)
            flash_surf.fill((*config.ACCENT_COLOR, alpha))
            surface.blit(flash_surf, flash_rect.topleft)

        # Frequency sweep bar — shows position in frequency range
        bar_y = config.HEADER_HEIGHT + 158
        bar_rect = pygame.Rect(20, bar_y, config.SCREEN_WIDTH - 40, 12)
        pygame.draw.rect(surface, config.BUTTON_BG, bar_rect)
        frac = self._freq_idx / max(1, len(self._freqs) - 1)
        marker_x = bar_rect.x + int(frac * bar_rect.width)
        pygame.draw.rect(surface, config.ACCENT_COLOR,
                         (marker_x - 3, bar_y - 2, 6, 16))
        # Range labels
        lo = _LABEL_FONT.render('87.5', True, config.DIM_ACCENT)
        hi = _LABEL_FONT.render('108', True, config.DIM_ACCENT)
        surface.blit(lo, (bar_rect.x, bar_y + 14))
        surface.blit(hi, hi.get_rect(right=bar_rect.right, y=bar_y + 14))

        # Energy history bar graph
        hist_y = bar_y + 36
        hist_h = 60
        hist = list(self._energy_history)
        max_e = max(max(hist), 0.01)
        bar_w = (config.SCREEN_WIDTH - 40) / len(hist)
        for i, e in enumerate(hist):
            h = int((e / max_e) * hist_h)
            if h > 0:
                x = 20 + int(i * bar_w)
                bcolor = config.ACCENT_COLOR if e / max_e > 0.5 else config.DIM_ACCENT
                pygame.draw.rect(surface, bcolor,
                                 (x, hist_y + hist_h - h, max(int(bar_w) - 1, 1), h))

        label = _LABEL_FONT.render('AUDIO ENERGY', True, config.DIM_ACCENT)
        surface.blit(label, (20, hist_y - 16))

    def _draw_controls(self, surface: pygame.Surface) -> None:
        # Direction buttons
        for rect, label, d in [(_DIR_REV_RECT, 'REV', -1),
                                (_DIR_STOP_RECT, 'STOP', 0),
                                (_DIR_FWD_RECT, 'FWD', 1)]:
            active = self._direction == d
            bg = config.BUTTON_ACTIVE_BG if active else config.BUTTON_BG
            border = config.ACCENT_COLOR if active else config.BORDER_COLOR
            pygame.draw.rect(surface, bg, rect, border_radius=6)
            pygame.draw.rect(surface, border, rect, width=2, border_radius=6)
            txt = _BIG_FONT.render(label, True,
                                   config.ACCENT_COLOR if active else config.DIM_ACCENT)
            surface.blit(txt, txt.get_rect(center=rect.center))

        # Speed slider
        pygame.draw.rect(surface, config.BUTTON_BG, _SLIDER_RECT, border_radius=4)
        pygame.draw.rect(surface, config.BORDER_COLOR, _SLIDER_RECT, width=1, border_radius=4)
        rng = config.SPIRITBOX_DWELL_MAX_MS - config.SPIRITBOX_DWELL_MIN_MS
        frac = (self._dwell_ms - config.SPIRITBOX_DWELL_MIN_MS) / rng
        knob_x = _SLIDER_RECT.x + int(frac * _SLIDER_RECT.width)
        pygame.draw.circle(surface, config.ACCENT_COLOR, (knob_x, _SLIDER_RECT.centery), 10)

        speed_label = _LABEL_FONT.render(f'SWEEP: {int(self._dwell_ms)} ms/ch', True,
                                          config.DIM_ACCENT)
        surface.blit(speed_label, speed_label.get_rect(
            centerx=config.SCREEN_WIDTH // 2, y=_SLIDER_RECT.y - 16))

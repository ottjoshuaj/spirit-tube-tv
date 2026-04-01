# screens/disturbance_screen.py
"""RF Disturbance Detector — REM-pod-style proximity alerts via RF energy shifts."""
import math
import multiprocessing as mp
import queue
import subprocess
import sys
import threading
import time

import numpy as np
import pygame

import config
from ui.components import draw_button

_BACK_RECT = pygame.Rect(8, 6, 60, 32)

_TITLE_FONT = None
_LEVEL_FONT = None
_INFO_FONT  = None


def _init_fonts():
    global _TITLE_FONT, _LEVEL_FONT, _INFO_FONT
    if _TITLE_FONT is None:
        _TITLE_FONT = pygame.font.SysFont('freesans', 20, bold=True)
        _LEVEL_FONT = pygame.font.SysFont('freesans', 48, bold=True)
        _INFO_FONT  = pygame.font.SysFont('freesans', 14)


# Sensitivity slider
_SENS_RECT = pygame.Rect(20, config.SCREEN_HEIGHT - 50, config.SCREEN_WIDTH - 40, 30)


# ======================================================================
# SDR worker — reports running energy level
# ======================================================================

def _disturbance_worker(result_q: mp.Queue, cmd_q: mp.Queue) -> None:
    from rtlsdr import RtlSdr

    try:
        sdr = RtlSdr()
        sdr.sample_rate = config.DISTURBANCE_BANDWIDTH
        sdr.center_freq = config.DISTURBANCE_FREQ
        sdr.gain = 'auto'
    except Exception as e:
        print(f'[Disturbance worker] SDR open failed: {e}', file=sys.stderr)
        return

    while True:
        try:
            cmd = cmd_q.get_nowait()
            if cmd == 'stop':
                try:
                    sdr.close()
                except Exception:
                    pass
                return
        except queue.Empty:
            pass

        try:
            iq = np.asarray(sdr.read_samples(config.DISTURBANCE_READ_SIZE), dtype=np.complex64)
        except Exception:
            time.sleep(0.1)
            continue

        energy = float(np.mean(np.abs(iq) ** 2))
        try:
            try:
                result_q.get_nowait()
            except queue.Empty:
                pass
            result_q.put_nowait(energy)
        except Exception:
            pass


# ======================================================================
# Beep generator — plays tones through pygame mixer
# ======================================================================

_beep_cache: dict[int, pygame.mixer.Sound] = {}


def _get_beep(freq_hz: int, duration_ms: int = 120) -> pygame.mixer.Sound:
    key = (freq_hz, duration_ms)
    if key not in _beep_cache:
        sample_rate = 22050
        n_samples = int(sample_rate * duration_ms / 1000)
        t = np.linspace(0, duration_ms / 1000, n_samples, endpoint=False, dtype=np.float32)
        # Fade envelope to avoid clicks
        wave = np.sin(2 * np.pi * freq_hz * t) * 0.4
        fade = min(n_samples, 200)
        wave[:fade] *= np.linspace(0, 1, fade)
        wave[-fade:] *= np.linspace(1, 0, fade)
        # Convert to 16-bit stereo
        pcm = (wave * 32767).astype(np.int16)
        stereo = np.column_stack([pcm, pcm]).flatten()
        snd = pygame.mixer.Sound(buffer=stereo.tobytes())
        _beep_cache[key] = snd
    return _beep_cache[key]


# ======================================================================
# Screen
# ======================================================================

# Ring colors from calm to alarmed
_RING_COLORS = [
    (0, 80, 0),      # 1 — green
    (0, 180, 0),     # 2 — bright green
    (200, 200, 0),   # 3 — yellow
    (220, 120, 0),   # 4 — orange
    (220, 0, 0),     # 5 — red
]

# Beep frequencies per level
_BEEP_FREQS = [440, 660, 880, 1100, 1400]


class DisturbanceScreen:
    def __init__(self):
        self._proc: mp.Process | None = None
        self._result_q: mp.Queue | None = None
        self._cmd_q: mp.Queue | None = None

        self._current_energy = 0.0
        self._baseline = 0.0
        self._baseline_samples: list[float] = []
        self._baseline_ready = False
        self._start_ms = 0

        self._sensitivity = config.DISTURBANCE_SENSITIVITY
        self._level = 0         # 0 = calm, 1–5 = alert levels
        self._last_beep_ms = 0
        self._energy_history = [0.0] * 120

    def start(self) -> bool:
        self._result_q = mp.Queue(maxsize=2)
        self._cmd_q = mp.Queue(maxsize=10)
        self._proc = mp.Process(
            target=_disturbance_worker,
            args=(self._result_q, self._cmd_q),
            daemon=True,
        )
        self._proc.start()
        self._start_ms = pygame.time.get_ticks()
        self._baseline_ready = False
        self._baseline_samples = []
        return True

    def stop(self) -> None:
        if self._cmd_q:
            try:
                self._cmd_q.put_nowait('stop')
            except Exception:
                pass
        if self._proc:
            self._proc.join(timeout=3.0)
            if self._proc.is_alive():
                self._proc.kill()
                self._proc.join(timeout=1.0)
            self._proc = None
        self._result_q = None
        self._cmd_q = None

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        if _BACK_RECT.collidepoint(pos):
            return 'back'
        if _SENS_RECT.collidepoint(pos):
            frac = (pos[0] - _SENS_RECT.x) / _SENS_RECT.width
            frac = max(0.0, min(1.0, frac))
            # Sensitivity 1.1 (very sensitive) to 4.0 (very tolerant)
            self._sensitivity = 1.1 + frac * 2.9
            return None
        return None

    def render(self, surface: pygame.Surface) -> None:
        _init_fonts()
        self._pull_data()
        self._compute_level()
        self._play_beep()
        surface.fill(config.BG_COLOR)
        self._draw_header(surface)
        self._draw_rings(surface)
        self._draw_energy_graph(surface)
        self._draw_controls(surface)

    # ------------------------------------------------------------------

    def _pull_data(self) -> None:
        if self._result_q is None:
            return
        try:
            while True:
                self._current_energy = self._result_q.get_nowait()
                self._energy_history.append(self._current_energy)
                if len(self._energy_history) > 120:
                    self._energy_history.pop(0)
        except (queue.Empty, EOFError, OSError):
            pass

        # Build baseline during the first N seconds
        if not self._baseline_ready:
            elapsed = (pygame.time.get_ticks() - self._start_ms) / 1000
            if self._current_energy > 0:
                self._baseline_samples.append(self._current_energy)
            if elapsed >= config.DISTURBANCE_BASELINE_S and len(self._baseline_samples) > 10:
                self._baseline = float(np.mean(self._baseline_samples))
                self._baseline_ready = True

    def _compute_level(self) -> None:
        if not self._baseline_ready or self._baseline <= 0:
            self._level = 0
            return
        ratio = self._current_energy / self._baseline
        # Map ratio to 0–5 levels
        n_levels = config.DISTURBANCE_LEVELS
        level = 0
        for i in range(1, n_levels + 1):
            threshold = 1.0 + (self._sensitivity - 1.0) * (i / n_levels)
            if ratio >= threshold:
                level = i
        self._level = level

    def _play_beep(self) -> None:
        if self._level == 0:
            return
        now = pygame.time.get_ticks()
        # Beep interval decreases with level (faster = more disturbance)
        intervals = [800, 500, 300, 180, 100]
        interval = intervals[min(self._level - 1, len(intervals) - 1)]
        if now - self._last_beep_ms >= interval:
            self._last_beep_ms = now
            freq = _BEEP_FREQS[min(self._level - 1, len(_BEEP_FREQS) - 1)]
            try:
                _get_beep(freq).play()
            except Exception:
                pass

    # ------------------------------------------------------------------

    def _draw_header(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, config.HEADER_BG,
                         (0, 0, config.SCREEN_WIDTH, config.HEADER_HEIGHT))
        draw_button(surface, _BACK_RECT, 'back')
        title = _TITLE_FONT.render('RF DISTURBANCE DETECTOR', True, config.ACCENT_COLOR)
        surface.blit(title, title.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                            centery=config.HEADER_HEIGHT // 2))
        freq_mhz = config.DISTURBANCE_FREQ / 1_000_000
        info = _INFO_FONT.render(f'{freq_mhz:.1f} MHz', True, config.DIM_ACCENT)
        surface.blit(info, info.get_rect(right=config.SCREEN_WIDTH - 10,
                                          centery=config.HEADER_HEIGHT // 2))

    def _draw_rings(self, surface: pygame.Surface) -> None:
        cx = config.SCREEN_WIDTH // 2
        cy = config.HEADER_HEIGHT + 140
        max_r = 120
        n_rings = config.DISTURBANCE_LEVELS

        if not self._baseline_ready:
            # Calibrating animation
            elapsed = (pygame.time.get_ticks() - self._start_ms) / 1000
            progress = min(elapsed / config.DISTURBANCE_BASELINE_S, 1.0)
            # Pulsing circle
            pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 200)
            r = int(30 + pulse * 20)
            pygame.draw.circle(surface, config.DIM_ACCENT, (cx, cy), r, 2)
            cal_txt = _TITLE_FONT.render('CALIBRATING...', True, config.DIM_ACCENT)
            surface.blit(cal_txt, cal_txt.get_rect(centerx=cx, centery=cy))
            # Progress bar
            bar_w = 200
            bar_rect = pygame.Rect(cx - bar_w // 2, cy + 40, bar_w, 10)
            pygame.draw.rect(surface, config.BUTTON_BG, bar_rect)
            fill_w = int(progress * bar_w)
            if fill_w > 0:
                pygame.draw.rect(surface, config.ACCENT_COLOR,
                                 (bar_rect.x, bar_rect.y, fill_w, 10))
            return

        # Draw concentric rings
        for i in range(n_rings, 0, -1):
            r = int(max_r * i / n_rings)
            color = _RING_COLORS[i - 1]
            if i <= self._level:
                # Filled ring — active
                pygame.draw.circle(surface, color, (cx, cy), r)
            else:
                # Outline only — inactive
                dim = tuple(c // 4 for c in color)
                pygame.draw.circle(surface, dim, (cx, cy), r, 2)

        # Level text in center
        if self._level > 0:
            txt = _LEVEL_FONT.render(str(self._level), True, (255, 255, 255))
        else:
            txt = _LEVEL_FONT.render('—', True, config.DIM_ACCENT)
        surface.blit(txt, txt.get_rect(centerx=cx, centery=cy))

        # Status label
        if self._level == 0:
            status = 'QUIET'
            scolor = config.DIM_ACCENT
        elif self._level <= 2:
            status = 'MINOR DISTURBANCE'
            scolor = _RING_COLORS[self._level - 1]
        elif self._level <= 4:
            status = 'STRONG DISTURBANCE'
            scolor = _RING_COLORS[self._level - 1]
        else:
            status = 'EXTREME DISTURBANCE'
            scolor = _RING_COLORS[4]
        stxt = _TITLE_FONT.render(status, True, scolor)
        surface.blit(stxt, stxt.get_rect(centerx=cx, y=cy + max_r + 10))

    def _draw_energy_graph(self, surface: pygame.Surface) -> None:
        graph_rect = pygame.Rect(20, config.SCREEN_HEIGHT - 110,
                                 config.SCREEN_WIDTH - 40, 45)
        pygame.draw.rect(surface, config.BUTTON_BG, graph_rect)
        pygame.draw.rect(surface, config.BORDER_COLOR, graph_rect, 1)

        hist = self._energy_history
        if not hist or max(hist) == 0:
            return
        max_e = max(hist)
        bar_w = graph_rect.width / len(hist)
        for i, e in enumerate(hist):
            h = int((e / max_e) * (graph_rect.height - 4))
            if h > 0:
                x = graph_rect.x + int(i * bar_w)
                # Color by level
                ratio = e / max(self._baseline, 0.001) if self._baseline_ready else 0
                if ratio > self._sensitivity:
                    c = (220, 0, 0)
                elif ratio > 1.0 + (self._sensitivity - 1.0) * 0.5:
                    c = (200, 200, 0)
                else:
                    c = config.DIM_ACCENT
                pygame.draw.rect(surface, c,
                                 (x, graph_rect.bottom - 2 - h,
                                  max(int(bar_w) - 1, 1), h))

        # Baseline line
        if self._baseline_ready and max_e > 0:
            bl_y = graph_rect.bottom - 2 - int((self._baseline / max_e) * (graph_rect.height - 4))
            bl_y = max(graph_rect.y, min(graph_rect.bottom - 2, bl_y))
            pygame.draw.line(surface, (0, 180, 0),
                             (graph_rect.x, bl_y), (graph_rect.right, bl_y), 1)

        label = _INFO_FONT.render('RF ENERGY', True, config.DIM_ACCENT)
        surface.blit(label, (graph_rect.x, graph_rect.y - 15))

    def _draw_controls(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, config.BUTTON_BG, _SENS_RECT, border_radius=4)
        pygame.draw.rect(surface, config.BORDER_COLOR, _SENS_RECT, width=1, border_radius=4)
        frac = (self._sensitivity - 1.1) / 2.9
        knob_x = _SENS_RECT.x + int(frac * _SENS_RECT.width)
        pygame.draw.circle(surface, config.ACCENT_COLOR, (knob_x, _SENS_RECT.centery), 10)
        label = _INFO_FONT.render(f'SENSITIVITY: {self._sensitivity:.1f}x', True,
                                   config.DIM_ACCENT)
        surface.blit(label, label.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                            y=_SENS_RECT.y - 16))

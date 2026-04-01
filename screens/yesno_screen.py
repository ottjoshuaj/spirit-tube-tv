# screens/yesno_screen.py
"""Yes / No RF Detector — monitors two frequency bands for energy spikes."""
import multiprocessing as mp
import os
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
_BIG_FONT   = None
_INFO_FONT  = None
_HIST_FONT  = None


def _init_fonts():
    global _TITLE_FONT, _BIG_FONT, _INFO_FONT, _HIST_FONT
    if _TITLE_FONT is None:
        _TITLE_FONT = pygame.font.SysFont('freesans', 20, bold=True)
        _BIG_FONT   = pygame.font.SysFont('freesans', 120, bold=True)
        _INFO_FONT  = pygame.font.SysFont('freesans', 16)
        _HIST_FONT  = pygame.font.SysFont('freesans', 18)


# ======================================================================
# SDR worker — runs in subprocess, reports energy levels via queue
# ======================================================================

def _yesno_worker(result_q: mp.Queue, cmd_q: mp.Queue) -> None:
    """Capture IQ, FFT, measure energy in YES and NO bands."""
    from rtlsdr import RtlSdr

    try:
        sdr = RtlSdr()
        sdr.sample_rate = config.YESNO_BANDWIDTH
        sdr.center_freq = config.YESNO_CENTER_FREQ
        sdr.gain = 'auto'
    except Exception as e:
        print(f'[YesNo worker] SDR open failed: {e}', file=sys.stderr)
        return

    fft_size = config.YESNO_FFT_SIZE
    freq_res = config.YESNO_BANDWIDTH / fft_size  # Hz per FFT bin

    # Precompute bin ranges for YES and NO bands
    def _offset_to_bins(offset_hz):
        center_bin = fft_size // 2
        lo = int(center_bin + (offset_hz - config.YESNO_BIN_WIDTH / 2) / freq_res)
        hi = int(center_bin + (offset_hz + config.YESNO_BIN_WIDTH / 2) / freq_res)
        return max(0, lo), min(fft_size, hi)

    yes_lo, yes_hi = _offset_to_bins(config.YESNO_YES_OFFSET)
    no_lo, no_hi   = _offset_to_bins(config.YESNO_NO_OFFSET)

    while True:
        # Check for stop command
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
            iq = np.asarray(sdr.read_samples(config.YESNO_READ_SIZE), dtype=np.complex64)
        except Exception:
            time.sleep(0.1)
            continue

        # FFT — average magnitude over all complete windows in this block
        n_windows = max(1, len(iq) // fft_size)
        mag_acc = np.zeros(fft_size, dtype=np.float64)
        for i in range(n_windows):
            chunk = iq[i * fft_size:(i + 1) * fft_size]
            if len(chunk) < fft_size:
                break
            spectrum = np.fft.fftshift(np.fft.fft(chunk, fft_size))
            mag_acc += np.abs(spectrum)
        mag = (mag_acc / n_windows).astype(np.float32)

        # Measure energy in each band
        yes_energy = float(np.mean(mag[yes_lo:yes_hi])) if yes_hi > yes_lo else 0.0
        no_energy  = float(np.mean(mag[no_lo:no_hi]))   if no_hi > no_lo else 0.0
        # Noise floor — median of entire spectrum (robust to spikes)
        noise_floor = float(np.median(mag))

        try:
            # Drop stale result
            try:
                result_q.get_nowait()
            except queue.Empty:
                pass
            result_q.put_nowait((yes_energy, no_energy, noise_floor, mag))
        except Exception:
            pass


# ======================================================================
# TTS — fire-and-forget in a thread
# ======================================================================

def _speak(word: str) -> None:
    def _run():
        try:
            subprocess.run(
                ['espeak-ng', '-v', 'en', '-s', '130', '-p', '30', word],
                timeout=5, capture_output=True,
            )
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


# ======================================================================
# Screen
# ======================================================================

class YesNoScreen:
    def __init__(self):
        self._proc: mp.Process | None = None
        self._result_q: mp.Queue | None = None
        self._cmd_q: mp.Queue | None = None

        # State
        self._yes_energy = 0.0
        self._no_energy  = 0.0
        self._noise_floor = 1.0
        self._spectrum: np.ndarray | None = None

        # Trigger state
        self._last_trigger_ms = 0
        self._current_word: str | None = None  # 'YES' or 'NO'
        self._trigger_ms = 0                    # when it was triggered
        self._flash_duration_ms = 2000

        # History log
        self._history: list[tuple[str, int]] = []  # (word, ticks)
        self._max_history = 8

    def start(self) -> bool:
        self._result_q = mp.Queue(maxsize=2)
        self._cmd_q = mp.Queue(maxsize=10)
        self._proc = mp.Process(
            target=_yesno_worker,
            args=(self._result_q, self._cmd_q),
            daemon=True,
        )
        self._proc.start()
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
        return None

    def render(self, surface: pygame.Surface) -> None:
        _init_fonts()
        self._pull_data()
        self._check_trigger()

        surface.fill(config.BG_COLOR)
        self._draw_header(surface)
        self._draw_detector(surface)
        self._draw_spectrum(surface)
        self._draw_history(surface)

    # ------------------------------------------------------------------

    def _pull_data(self) -> None:
        if self._result_q is None:
            return
        try:
            while True:
                self._yes_energy, self._no_energy, self._noise_floor, self._spectrum = \
                    self._result_q.get_nowait()
        except (queue.Empty, EOFError, OSError):
            pass

    def _check_trigger(self) -> None:
        now = pygame.time.get_ticks()
        if now - self._last_trigger_ms < config.YESNO_COOLDOWN_MS:
            return
        nf = max(self._noise_floor, 0.001)
        yes_ratio = self._yes_energy / nf
        no_ratio  = self._no_energy / nf
        threshold = config.YESNO_THRESHOLD

        triggered = None
        if yes_ratio >= threshold and no_ratio >= threshold:
            # Both spiked — pick the stronger one
            triggered = 'YES' if yes_ratio > no_ratio else 'NO'
        elif yes_ratio >= threshold:
            triggered = 'YES'
        elif no_ratio >= threshold:
            triggered = 'NO'

        if triggered:
            self._current_word = triggered
            self._trigger_ms = now
            self._last_trigger_ms = now
            self._history.append((triggered, now))
            if len(self._history) > self._max_history:
                self._history.pop(0)
            _speak(triggered)

    # ------------------------------------------------------------------

    def _draw_header(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, config.HEADER_BG,
                         (0, 0, config.SCREEN_WIDTH, config.HEADER_HEIGHT))
        draw_button(surface, _BACK_RECT, 'back')
        title = _TITLE_FONT.render('YES / NO DETECTOR', True, config.ACCENT_COLOR)
        surface.blit(title, title.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                            centery=config.HEADER_HEIGHT // 2))
        # Frequency info
        freq_mhz = config.YESNO_CENTER_FREQ / 1_000_000
        info = _INFO_FONT.render(f'{freq_mhz:.3f} MHz', True, config.DIM_ACCENT)
        surface.blit(info, info.get_rect(right=config.SCREEN_WIDTH - 10,
                                          centery=config.HEADER_HEIGHT // 2))

    def _draw_detector(self, surface: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        center_y = config.HEADER_HEIGHT + 130

        # Flash background when triggered
        if self._current_word and (now - self._trigger_ms) < self._flash_duration_ms:
            age = (now - self._trigger_ms) / self._flash_duration_ms
            alpha = max(0, 1.0 - age)

            if self._current_word == 'YES':
                flash_color = (0, int(80 * alpha), 0)
                text_color = (0, int(255 * (0.4 + 0.6 * alpha)), 0)
            else:
                flash_color = (int(80 * alpha), 0, 0)
                text_color = (int(255 * (0.4 + 0.6 * alpha)), 0, 0)

            # Flash rect behind the word
            flash_rect = pygame.Rect(100, center_y - 80, config.SCREEN_WIDTH - 200, 160)
            flash_surf = pygame.Surface(flash_rect.size)
            flash_surf.fill(flash_color)
            surface.blit(flash_surf, flash_rect.topleft)

            word_surf = _BIG_FONT.render(self._current_word, True, text_color)
            surface.blit(word_surf, word_surf.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                                        centery=center_y))
        else:
            # Idle — show waiting indicator
            dots = '.' * ((now // 500) % 4)
            wait = _TITLE_FONT.render(f'MONITORING{dots}', True, config.DIM_ACCENT)
            surface.blit(wait, wait.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                              centery=center_y))

        # Energy bars — YES on left, NO on right
        bar_y = center_y + 90
        bar_h = 20
        bar_max_w = 200
        nf = max(self._noise_floor, 0.001)

        # YES bar (left side)
        yes_ratio = min(self._yes_energy / nf / config.YESNO_THRESHOLD, 2.0)
        yes_w = int(yes_ratio * bar_max_w / 2.0)
        yes_label = _INFO_FONT.render('YES', True, (0, 180, 0))
        surface.blit(yes_label, (config.SCREEN_WIDTH // 2 - bar_max_w - 50, bar_y))
        bar_rect = pygame.Rect(config.SCREEN_WIDTH // 2 - bar_max_w, bar_y, bar_max_w, bar_h)
        pygame.draw.rect(surface, config.BUTTON_BG, bar_rect)
        if yes_w > 0:
            fill = pygame.Rect(bar_rect.x, bar_rect.y, min(yes_w, bar_max_w), bar_h)
            color = (0, 200, 0) if yes_ratio >= 1.0 else (0, 100, 0)
            pygame.draw.rect(surface, color, fill)
        pygame.draw.rect(surface, config.BORDER_COLOR, bar_rect, 1)
        # Threshold line
        thresh_x = bar_rect.x + bar_max_w // 2
        pygame.draw.line(surface, config.ACCENT_COLOR, (thresh_x, bar_y), (thresh_x, bar_y + bar_h), 1)

        # NO bar (right side)
        no_ratio = min(self._no_energy / nf / config.YESNO_THRESHOLD, 2.0)
        no_w = int(no_ratio * bar_max_w / 2.0)
        bar_rect = pygame.Rect(config.SCREEN_WIDTH // 2 + 20, bar_y, bar_max_w, bar_h)
        pygame.draw.rect(surface, config.BUTTON_BG, bar_rect)
        if no_w > 0:
            fill = pygame.Rect(bar_rect.x, bar_rect.y, min(no_w, bar_max_w), bar_h)
            color = (200, 0, 0) if no_ratio >= 1.0 else (100, 0, 0)
            pygame.draw.rect(surface, color, fill)
        pygame.draw.rect(surface, config.BORDER_COLOR, bar_rect, 1)
        thresh_x = bar_rect.x + bar_max_w // 2
        pygame.draw.line(surface, config.ACCENT_COLOR, (thresh_x, bar_y), (thresh_x, bar_y + bar_h), 1)
        no_label = _INFO_FONT.render('NO', True, (180, 0, 0))
        surface.blit(no_label, (bar_rect.right + 10, bar_y))

    def _draw_spectrum(self, surface: pygame.Surface) -> None:
        """Mini spectrum display at bottom."""
        if self._spectrum is None:
            return
        spec_rect = pygame.Rect(20, config.SCREEN_HEIGHT - 90, config.SCREEN_WIDTH - 40, 50)
        pygame.draw.rect(surface, config.BUTTON_BG, spec_rect)
        pygame.draw.rect(surface, config.BORDER_COLOR, spec_rect, 1)

        # Downsample spectrum to fit width
        spec = self._spectrum
        n_bins = spec_rect.width
        if len(spec) > n_bins:
            step = len(spec) / n_bins
            indices = np.arange(n_bins) * step
            spec_down = spec[(indices).astype(int)]
        else:
            spec_down = spec

        # Normalize to rect height
        s_min = np.min(spec_down)
        s_max = np.max(spec_down)
        if s_max - s_min > 0:
            normed = (spec_down - s_min) / (s_max - s_min)
        else:
            normed = np.zeros_like(spec_down)

        # Draw bars
        for i in range(min(len(normed), spec_rect.width)):
            h = int(normed[i] * (spec_rect.height - 4))
            if h > 0:
                x = spec_rect.x + i
                y = spec_rect.bottom - 2 - h
                pygame.draw.line(surface, config.ACCENT_COLOR, (x, y), (x, spec_rect.bottom - 2))

    def _draw_history(self, surface: pygame.Surface) -> None:
        """Show recent detections along the right edge."""
        if not self._history:
            return
        x = config.SCREEN_WIDTH - 90
        y_start = config.HEADER_HEIGHT + 10
        label = _INFO_FONT.render('HISTORY', True, config.DIM_ACCENT)
        surface.blit(label, (x, y_start))
        for i, (word, _tick) in enumerate(reversed(self._history)):
            y = y_start + 22 + i * 22
            if y > config.SCREEN_HEIGHT - 100:
                break
            color = (0, 180, 0) if word == 'YES' else (180, 0, 0)
            alpha = max(0.3, 1.0 - i * 0.1)
            faded = tuple(int(c * alpha) for c in color)
            txt = _HIST_FONT.render(word, True, faded)
            surface.blit(txt, (x + 10, y))

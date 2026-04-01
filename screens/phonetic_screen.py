# screens/phonetic_screen.py
"""Phonetic Decoder — Ovilus-style RF-to-word translator."""
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
_WORD_FONT  = None
_INFO_FONT  = None
_HIST_FONT  = None

# Word bank — loaded from data/word_bank.txt
# Paranormal-core words (marked with *) are weighted 3x in the selection pool.
_WORD_BANK: list[str] = []   # weighted pool — paranormal words appear 3 times


def _load_word_bank() -> None:
    global _WORD_BANK
    if _WORD_BANK:
        return
    bank_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                             'data', 'word_bank.txt')
    paranormal: list[str] = []
    common: list[str] = []
    try:
        with open(bank_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('*'):
                    paranormal.append(line[1:])
                else:
                    common.append(line)
    except FileNotFoundError:
        # Fallback minimal bank
        _WORD_BANK.extend(['yes', 'no', 'hello', 'goodbye', 'help', 'spirit',
                           'ghost', 'light', 'dark', 'cold', 'warm'])
        return
    # Build weighted pool: paranormal words 3x, common words 1x
    _WORD_BANK.extend(paranormal * 3)
    _WORD_BANK.extend(common)
    print(f'[Phonetic] Word bank loaded: {len(paranormal)} paranormal, '
          f'{len(common)} common, {len(_WORD_BANK)} weighted slots',
          file=sys.stderr)


def _init_fonts():
    global _TITLE_FONT, _WORD_FONT, _INFO_FONT, _HIST_FONT
    if _TITLE_FONT is None:
        _TITLE_FONT = pygame.font.SysFont('freesans', 20, bold=True)
        _WORD_FONT  = pygame.font.SysFont('freesans', 72, bold=True)
        _INFO_FONT  = pygame.font.SysFont('freesans', 14)
        _HIST_FONT  = pygame.font.SysFont('freesans', 22)


# ======================================================================
# SDR worker — measures RF energy and spectral features
# ======================================================================

def _phonetic_worker(result_q: mp.Queue, cmd_q: mp.Queue) -> None:
    from rtlsdr import RtlSdr

    try:
        sdr = RtlSdr()
        sdr.sample_rate = config.PHONETIC_BANDWIDTH
        sdr.center_freq = config.PHONETIC_FREQ
        sdr.gain = 'auto'
    except Exception as e:
        print(f'[Phonetic worker] SDR open failed: {e}', file=sys.stderr)
        return

    fft_size = 1024

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
            iq = np.asarray(sdr.read_samples(config.PHONETIC_READ_SIZE), dtype=np.complex64)
        except Exception:
            time.sleep(0.1)
            continue

        # Total energy
        energy = float(np.mean(np.abs(iq) ** 2))
        # Spectral centroid — used as a seed for word selection
        spectrum = np.abs(np.fft.fft(iq[:fft_size]))
        freqs = np.arange(fft_size, dtype=np.float64)
        total = np.sum(spectrum)
        centroid = float(np.sum(freqs * spectrum) / total) if total > 0 else 0.0
        # Spectral spread — secondary seed
        spread = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * spectrum) / total)) if total > 0 else 0.0

        try:
            try:
                result_q.get_nowait()
            except queue.Empty:
                pass
            result_q.put_nowait((energy, centroid, spread))
        except Exception:
            pass


# ======================================================================
# TTS
# ======================================================================

def _speak(word: str) -> None:
    def _run():
        try:
            subprocess.run(
                ['espeak-ng', '-v', 'en', '-s', '120', '-p', '40', word],
                timeout=5, capture_output=True,
            )
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


# ======================================================================
# Screen
# ======================================================================

class PhoneticScreen:
    def __init__(self):
        _load_word_bank()
        self._proc: mp.Process | None = None
        self._result_q: mp.Queue | None = None
        self._cmd_q: mp.Queue | None = None

        self._energy = 0.0
        self._centroid = 0.0
        self._spread = 0.0
        self._noise_floor = 0.0
        self._noise_samples: list[float] = []
        self._calibrated = False
        self._start_ms = 0

        self._last_trigger_ms = 0
        self._current_word: str | None = None
        self._word_trigger_ms = 0
        self._word_display_ms = 3000

        self._history: list[tuple[str, int]] = []
        self._max_history = 12
        self._energy_history = [0.0] * 80

    def start(self) -> bool:
        self._result_q = mp.Queue(maxsize=2)
        self._cmd_q = mp.Queue(maxsize=10)
        self._proc = mp.Process(
            target=_phonetic_worker,
            args=(self._result_q, self._cmd_q),
            daemon=True,
        )
        self._proc.start()
        self._start_ms = pygame.time.get_ticks()
        self._calibrated = False
        self._noise_samples = []
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
        self._draw_word(surface)
        self._draw_energy_bar(surface)
        self._draw_history(surface)

    # ------------------------------------------------------------------

    def _pull_data(self) -> None:
        if self._result_q is None:
            return
        try:
            while True:
                self._energy, self._centroid, self._spread = self._result_q.get_nowait()
                self._energy_history.append(self._energy)
                if len(self._energy_history) > 80:
                    self._energy_history.pop(0)
        except (queue.Empty, EOFError, OSError):
            pass

        # Calibrate noise floor
        if not self._calibrated:
            elapsed = (pygame.time.get_ticks() - self._start_ms) / 1000
            if self._energy > 0:
                self._noise_samples.append(self._energy)
            if elapsed >= 3.0 and len(self._noise_samples) > 10:
                self._noise_floor = float(np.mean(self._noise_samples))
                self._calibrated = True

    def _check_trigger(self) -> None:
        if not self._calibrated or self._noise_floor <= 0:
            return
        now = pygame.time.get_ticks()
        if now - self._last_trigger_ms < config.PHONETIC_COOLDOWN_MS:
            return
        ratio = self._energy / self._noise_floor
        if ratio < config.PHONETIC_TRIGGER_MULT:
            return

        # Use spectral features to deterministically pick a word.
        # Centroid and spread together give us a reproducible index
        # that varies with the actual RF signal characteristics.
        seed = int((self._centroid * 1000 + self._spread * 100 +
                    self._energy * 10000) * 97) % len(_WORD_BANK)
        word = _WORD_BANK[seed]

        self._current_word = word
        self._word_trigger_ms = now
        self._last_trigger_ms = now
        self._history.append((word, now))
        if len(self._history) > self._max_history:
            self._history.pop(0)
        _speak(word)

    # ------------------------------------------------------------------

    def _draw_header(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, config.HEADER_BG,
                         (0, 0, config.SCREEN_WIDTH, config.HEADER_HEIGHT))
        draw_button(surface, _BACK_RECT, 'back')
        title = _TITLE_FONT.render('PHONETIC DECODER', True, config.ACCENT_COLOR)
        surface.blit(title, title.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                            centery=config.HEADER_HEIGHT // 2))
        freq_mhz = config.PHONETIC_FREQ / 1_000_000
        info = _INFO_FONT.render(f'{freq_mhz:.1f} MHz', True, config.DIM_ACCENT)
        surface.blit(info, info.get_rect(right=config.SCREEN_WIDTH - 10,
                                          centery=config.HEADER_HEIGHT // 2))

    def _draw_word(self, surface: pygame.Surface) -> None:
        now = pygame.time.get_ticks()
        cx = config.SCREEN_WIDTH // 2 - 40  # offset left to leave room for history
        cy = config.HEADER_HEIGHT + 140

        if not self._calibrated:
            elapsed = (pygame.time.get_ticks() - self._start_ms) / 1000
            progress = min(elapsed / 3.0, 1.0)
            cal = _TITLE_FONT.render('CALIBRATING...', True, config.DIM_ACCENT)
            surface.blit(cal, cal.get_rect(centerx=cx, centery=cy))
            bar_w = 200
            bar_rect = pygame.Rect(cx - bar_w // 2, cy + 30, bar_w, 10)
            pygame.draw.rect(surface, config.BUTTON_BG, bar_rect)
            fill_w = int(progress * bar_w)
            if fill_w > 0:
                pygame.draw.rect(surface, config.ACCENT_COLOR,
                                 (bar_rect.x, bar_rect.y, fill_w, 10))
            return

        if self._current_word and (now - self._word_trigger_ms) < self._word_display_ms:
            age = (now - self._word_trigger_ms) / self._word_display_ms
            # Typewriter reveal effect
            n_chars = min(len(self._current_word),
                          int((now - self._word_trigger_ms) / 80) + 1)
            revealed = self._current_word[:n_chars].upper()

            # Glow fade
            alpha = max(0.4, 1.0 - age * 0.6)
            color = tuple(int(c * alpha) for c in config.ACCENT_COLOR)

            # Flash background
            if age < 0.3:
                flash_alpha = int((1.0 - age / 0.3) * 40)
                flash_rect = pygame.Rect(20, cy - 60, config.SCREEN_WIDTH - 140, 120)
                flash_surf = pygame.Surface(flash_rect.size, pygame.SRCALPHA)
                flash_surf.fill((*config.ACCENT_COLOR, flash_alpha))
                surface.blit(flash_surf, flash_rect.topleft)

            word_surf = _WORD_FONT.render(revealed, True, color)
            surface.blit(word_surf, word_surf.get_rect(centerx=cx, centery=cy))
        else:
            # Idle — pulsing dots
            dots = '·' * (((now // 400) % 3) + 1)
            idle = _TITLE_FONT.render(f'LISTENING {dots}', True, config.DIM_ACCENT)
            surface.blit(idle, idle.get_rect(centerx=cx, centery=cy))

    def _draw_energy_bar(self, surface: pygame.Surface) -> None:
        bar_rect = pygame.Rect(20, config.SCREEN_HEIGHT - 60,
                               config.SCREEN_WIDTH - 140, 40)
        pygame.draw.rect(surface, config.BUTTON_BG, bar_rect)
        pygame.draw.rect(surface, config.BORDER_COLOR, bar_rect, 1)

        hist = self._energy_history
        if not hist or max(hist) == 0:
            return
        max_e = max(hist)
        bar_w = bar_rect.width / len(hist)
        for i, e in enumerate(hist):
            h = int((e / max_e) * (bar_rect.height - 4))
            if h > 0:
                x = bar_rect.x + int(i * bar_w)
                ratio = e / max(self._noise_floor, 0.001) if self._calibrated else 0
                if ratio >= config.PHONETIC_TRIGGER_MULT:
                    c = config.ACCENT_COLOR
                else:
                    c = config.DIM_ACCENT
                pygame.draw.rect(surface, c,
                                 (x, bar_rect.bottom - 2 - h,
                                  max(int(bar_w) - 1, 1), h))

        # Threshold line
        if self._calibrated and max_e > 0:
            thresh_e = self._noise_floor * config.PHONETIC_TRIGGER_MULT
            thresh_y = bar_rect.bottom - 2 - int((thresh_e / max_e) * (bar_rect.height - 4))
            thresh_y = max(bar_rect.y, min(bar_rect.bottom - 2, thresh_y))
            pygame.draw.line(surface, (220, 0, 0),
                             (bar_rect.x, thresh_y), (bar_rect.right, thresh_y), 1)

        label = _INFO_FONT.render('RF ENERGY', True, config.DIM_ACCENT)
        surface.blit(label, (bar_rect.x, bar_rect.y - 16))

    def _draw_history(self, surface: pygame.Surface) -> None:
        x = config.SCREEN_WIDTH - 110
        y_start = config.HEADER_HEIGHT + 10
        label = _INFO_FONT.render('WORDS', True, config.DIM_ACCENT)
        surface.blit(label, (x, y_start))

        # Draw separator line
        pygame.draw.line(surface, config.BORDER_COLOR,
                         (x - 10, y_start), (x - 10, config.SCREEN_HEIGHT - 70), 1)

        for i, (word, _tick) in enumerate(reversed(self._history)):
            y = y_start + 24 + i * 28
            if y > config.SCREEN_HEIGHT - 80:
                break
            alpha = max(0.3, 1.0 - i * 0.08)
            color = tuple(int(c * alpha) for c in config.ACCENT_COLOR)
            txt = _HIST_FONT.render(word.upper(), True, color)
            surface.blit(txt, (x, y))

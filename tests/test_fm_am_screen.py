# tests/test_fm_am_screen.py
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
import numpy as np
import pytest
from unittest.mock import MagicMock

pygame.init()
_surface = pygame.display.set_mode((800, 480))

from screens.fm_am_screen import FmAmScreen


def _mock_sdr():
    m = MagicMock()
    m.get_audio_chunk.return_value = np.zeros(1024, dtype=np.float32)
    return m


def _mock_audio():
    return MagicMock()


def test_back_button_returns_back():
    s = FmAmScreen('fm')
    s.start(_mock_sdr(), _mock_audio())
    result = s.handle_touch((20, 20))   # top-left back button area
    s.stop()
    assert result == 'back'


def test_back_calls_stop_on_sdr_and_audio():
    sdr   = _mock_sdr()
    audio = _mock_audio()
    s = FmAmScreen('fm')
    s.start(sdr, audio)
    s.handle_touch((20, 20))
    s.stop()
    sdr.stop.assert_called()
    audio.stop.assert_called()


def test_scan_fwd_button_activates_forward_scan():
    s = FmAmScreen('fm')
    s.start(_mock_sdr(), _mock_audio())
    s.handle_touch((s._btn_rects['scan_fwd'].centerx, s._btn_rects['scan_fwd'].centery))
    assert s._scan_state == 'forward'
    s.stop()


def test_scan_back_button_activates_backward_scan():
    s = FmAmScreen('fm')
    s.start(_mock_sdr(), _mock_audio())
    s.handle_touch((s._btn_rects['scan_back'].centerx, s._btn_rects['scan_back'].centery))
    assert s._scan_state == 'backward'
    s.stop()


def test_pause_button_stops_scan():
    s = FmAmScreen('fm')
    s.start(_mock_sdr(), _mock_audio())
    s.handle_touch((s._btn_rects['scan_fwd'].centerx, s._btn_rects['scan_fwd'].centery))
    s.handle_touch((s._btn_rects['pause'].centerx,    s._btn_rects['pause'].centery))
    assert s._scan_state == 'none'
    s.stop()


def test_next_button_advances_frequency():
    s = FmAmScreen('fm')
    s.start(_mock_sdr(), _mock_audio())
    idx_before = s._freq_idx
    s.handle_touch((s._btn_rects['next'].centerx, s._btn_rects['next'].centery))
    assert s._freq_idx == (idx_before + 1) % len(s._freqs)
    s.stop()


def test_prev_button_decrements_frequency():
    s = FmAmScreen('fm')
    s.start(_mock_sdr(), _mock_audio())
    idx_before = s._freq_idx
    s.handle_touch((s._btn_rects['prev'].centerx, s._btn_rects['prev'].centery))
    assert s._freq_idx == (idx_before - 1) % len(s._freqs)
    s.stop()


def test_am_mode_uses_am_freqs():
    import config
    s = FmAmScreen('am')
    assert s._freqs == config.AM_FREQS


def test_render_does_not_raise():
    s = FmAmScreen('fm')
    s.start(_mock_sdr(), _mock_audio())
    s.render(_surface)
    s.stop()

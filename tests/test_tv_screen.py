# tests/test_tv_screen.py
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
import numpy as np
import pytest
from unittest.mock import MagicMock

pygame.init()
_surface = pygame.display.set_mode((800, 480))

from screens.tv_screen import TvScreen
import config


def _mock_sdr():
    m = MagicMock()
    frame = np.random.randint(0, 255,
        (config.TV_FRAME_HEIGHT, config.TV_FRAME_WIDTH), dtype=np.uint8)
    m.get_frame.return_value = frame
    m.get_audio_chunk.return_value = np.zeros(1024, dtype=np.float32)
    return m


def _mock_audio():
    return MagicMock()


def test_back_returns_back():
    s = TvScreen()
    s.start(_mock_sdr(), _mock_audio())
    result = s.handle_touch((20, 20))
    s.stop()
    assert result == 'back'


def test_back_stops_sdr_and_audio():
    sdr   = _mock_sdr()
    audio = _mock_audio()
    s = TvScreen()
    s.start(sdr, audio)
    s.handle_touch((20, 20))
    s.stop()
    sdr.stop.assert_called()
    audio.stop.assert_called()


def test_scan_fwd_activates():
    s = TvScreen()
    s.start(_mock_sdr(), _mock_audio())
    s.handle_touch((s._btn_rects['scan_fwd'].centerx, s._btn_rects['scan_fwd'].centery))
    assert s._scan_state == 'forward'
    s.stop()


def test_scan_back_activates():
    s = TvScreen()
    s.start(_mock_sdr(), _mock_audio())
    s.handle_touch((s._btn_rects['scan_back'].centerx, s._btn_rects['scan_back'].centery))
    assert s._scan_state == 'backward'
    s.stop()


def test_next_advances_channel():
    s = TvScreen()
    s.start(_mock_sdr(), _mock_audio())
    idx_before = s._ch_idx
    s.handle_touch((s._btn_rects['next'].centerx, s._btn_rects['next'].centery))
    assert s._ch_idx == (idx_before + 1) % len(config.TV_CHANNELS)
    s.stop()


def test_render_does_not_raise():
    s = TvScreen()
    s.start(_mock_sdr(), _mock_audio())
    s.render(_surface)
    s.stop()

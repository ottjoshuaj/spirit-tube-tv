import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
import pytest

pygame.init()
_surface = pygame.display.set_mode((800, 480))

from screens.band_select import BandSelectScreen

def _screen():
    return BandSelectScreen()

def test_tap_fm_returns_fm():
    s = _screen()
    # FM button is leftmost of three equal-width buttons in lower half
    # Approximate center x of FM button = 800//6 = ~133
    result = s.handle_touch((133, 300))
    assert result == 'fm'

def test_tap_am_returns_am():
    s = _screen()
    # AM button center x ≈ 400
    result = s.handle_touch((400, 300))
    assert result == 'am'

def test_tap_tv_returns_tv():
    s = _screen()
    # TV button center x ≈ 666
    result = s.handle_touch((666, 300))
    assert result == 'tv'

def test_tap_outside_buttons_returns_none():
    s = _screen()
    result = s.handle_touch((400, 50))  # header area
    assert result is None

def test_render_does_not_raise():
    s = _screen()
    s.render(_surface)  # must not raise

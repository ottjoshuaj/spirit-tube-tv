"""Shared PyGame draw helpers for Spirit Tube TV."""
import pygame
import numpy as np
import config

# Cached scanline overlay surfaces keyed by (width, height)
_scanline_cache: dict[tuple[int, int], pygame.Surface] = {}


def draw_button(surface: pygame.Surface, rect: pygame.Rect,
                icon: str, active: bool = False) -> None:
    """Draw a transport button with a drawn icon (no font dependency)."""
    bg = config.BUTTON_ACTIVE_BG if active else config.BUTTON_BG
    pygame.draw.rect(surface, bg, rect, border_radius=8)
    pygame.draw.rect(surface, config.ACCENT_COLOR, rect, width=1, border_radius=8)
    _draw_icon(surface, rect, icon)


def _draw_icon(surface: pygame.Surface, rect: pygame.Rect, icon: str) -> None:
    cx, cy = rect.centerx, rect.centery
    s = rect.height // 5   # size unit
    c = config.ACCENT_COLOR

    if icon == 'prev':          # |◀
        pygame.draw.line(surface, c, (cx - s, cy - s), (cx - s, cy + s), 2)
        pygame.draw.polygon(surface, c, [(cx + s, cy - s), (cx - s + 3, cy), (cx + s, cy + s)])
    elif icon == 'scan_back':   # ◀◀
        pygame.draw.polygon(surface, c, [(cx,     cy - s), (cx - s, cy), (cx,     cy + s)])
        pygame.draw.polygon(surface, c, [(cx + s, cy - s), (cx,     cy), (cx + s, cy + s)])
    elif icon == 'pause':       # ▐▌
        pygame.draw.rect(surface, c, (cx - s, cy - s, s - 1, s * 2))
        pygame.draw.rect(surface, c, (cx + 1, cy - s, s - 1, s * 2))
    elif icon == 'play':        # ▶
        pygame.draw.polygon(surface, c, [(cx - s // 2, cy - s), (cx + s, cy), (cx - s // 2, cy + s)])
    elif icon == 'scan_fwd':    # ▶▶
        pygame.draw.polygon(surface, c, [(cx - s, cy - s), (cx,     cy), (cx - s, cy + s)])
        pygame.draw.polygon(surface, c, [(cx,     cy - s), (cx + s, cy), (cx,     cy + s)])
    elif icon == 'next':        # ▶|
        pygame.draw.polygon(surface, c, [(cx - s, cy - s), (cx + s - 3, cy), (cx - s, cy + s)])
        pygame.draw.line(surface, c, (cx + s, cy - s), (cx + s, cy + s), 2)
    elif icon == 'back':        # ←
        pygame.draw.polygon(surface, c, [(cx + s // 2, cy - s), (cx - s // 2, cy), (cx + s // 2, cy + s)])
        pygame.draw.line(surface, c, (cx - s // 2, cy), (cx + s // 2, cy), 2)


def draw_waveform(surface: pygame.Surface, rect: pygame.Rect,
                  samples: np.ndarray) -> None:
    """Draw rolling audio waveform as a polyline."""
    pygame.draw.rect(surface, (10, 0, 16), rect)
    if len(samples) < 2:
        return
    xs = np.linspace(rect.left, rect.right - 1, len(samples), dtype=int)
    mid_y   = rect.centery
    amp     = max(rect.height // 2 - 4, 1)
    ys      = np.clip((mid_y - samples * amp).astype(int), rect.top, rect.bottom - 1)
    points  = list(zip(xs, ys))
    pygame.draw.lines(surface, config.ACCENT_COLOR, False, points, 2)


def draw_signal_bars(surface: pygame.Surface, rect: pygame.Rect,
                     magnitude: float) -> None:
    """Draw 8 signal-strength bars. magnitude is 0.0–1.0."""
    n     = 8
    gap   = 2
    bar_w = (rect.width - (n - 1) * gap) // n
    for i in range(n):
        bar_h = int(rect.height * (0.2 + 0.8 * (i / (n - 1))))
        x     = rect.left + i * (bar_w + gap)
        y     = rect.bottom - bar_h
        color = config.ACCENT_COLOR if (i / n) <= magnitude else config.BORDER_COLOR
        pygame.draw.rect(surface, color, (x, y, bar_w, bar_h), border_radius=2)


def draw_scanline_overlay(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """Blit a cached semi-transparent scanline overlay onto rect."""
    key = (rect.width, rect.height)
    if key not in _scanline_cache:
        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        for y in range(0, rect.height, 4):
            pygame.draw.line(overlay, (0, 0, 0, 38), (0, y), (rect.width, y))
        _scanline_cache[key] = overlay
    surface.blit(_scanline_cache[key], rect.topleft)


def make_transport_rects(screen_width: int, screen_height: int) -> dict[str, pygame.Rect]:
    """Return hit rects for the 5 transport buttons in the bottom row.

    Keys: 'prev', 'scan_back', 'pause', 'scan_fwd', 'next'
    """
    y      = screen_height - config.BUTTON_ROW_HEIGHT + (config.BUTTON_ROW_HEIGHT - config.BTN_HEIGHT) // 2
    buttons = [('prev', config.BTN_SIDE_W), ('scan_back', config.BTN_SIDE_W),
               ('pause', config.BTN_CENTER_W),
               ('scan_fwd', config.BTN_SIDE_W), ('next', config.BTN_SIDE_W)]
    n_gaps = len(buttons) - 1
    total  = sum(w for _, w in buttons) + config.BTN_MARGIN * n_gaps
    x0     = (screen_width - total) // 2
    rects  = {}
    cursor = x0
    for i, (name, w) in enumerate(buttons):
        rects[name] = pygame.Rect(cursor, y, w, config.BTN_HEIGHT)
        cursor += w + (config.BTN_MARGIN if i < len(buttons) - 1 else 0)
    return rects

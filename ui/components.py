"""Shared PyGame draw helpers for Spirit Tube TV."""
import pygame
import numpy as np
import config

# Cached scanline overlay surfaces keyed by (width, height)
_scanline_cache: dict[tuple[int, int], pygame.Surface] = {}

# Lazy-init fonts
_BTN_FONT: pygame.font.Font | None = None
_SLIDER_FONT: pygame.font.Font | None = None


def _ensure_fonts():
    global _BTN_FONT, _SLIDER_FONT
    if _BTN_FONT is None:
        _BTN_FONT = pygame.font.SysFont('freesans', 11, bold=True)
        _SLIDER_FONT = pygame.font.SysFont('freesans', 12)


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
    elif icon == 'scan_back':   # SCAN ◀◀
        _ensure_fonts()
        txt = _BTN_FONT.render('SCAN', True, c)
        surface.blit(txt, txt.get_rect(centery=cy, left=rect.left + 6))
        arrow_cx = rect.right - 20
        pygame.draw.polygon(surface, c, [(arrow_cx, cy - s), (arrow_cx - s, cy), (arrow_cx, cy + s)])
        pygame.draw.polygon(surface, c, [(arrow_cx + s, cy - s), (arrow_cx, cy), (arrow_cx + s, cy + s)])
    elif icon == 'pause':       # ▐▌
        pygame.draw.rect(surface, c, (cx - s, cy - s, s - 1, s * 2))
        pygame.draw.rect(surface, c, (cx + 1, cy - s, s - 1, s * 2))
    elif icon == 'play':        # ▶
        pygame.draw.polygon(surface, c, [(cx - s // 2, cy - s), (cx + s, cy), (cx - s // 2, cy + s)])
    elif icon == 'scan_fwd':    # SCAN ▶▶
        _ensure_fonts()
        txt = _BTN_FONT.render('SCAN', True, c)
        surface.blit(txt, txt.get_rect(centery=cy, left=rect.left + 6))
        arrow_cx = rect.right - 20
        pygame.draw.polygon(surface, c, [(arrow_cx - s, cy - s), (arrow_cx, cy), (arrow_cx - s, cy + s)])
        pygame.draw.polygon(surface, c, [(arrow_cx, cy - s), (arrow_cx + s, cy), (arrow_cx, cy + s)])
    elif icon == 'next':        # ▶|
        pygame.draw.polygon(surface, c, [(cx - s, cy - s), (cx + s - 3, cy), (cx - s, cy + s)])
        pygame.draw.line(surface, c, (cx + s, cy - s), (cx + s, cy + s), 2)
    elif icon == 'record':      # ● (red circle)
        pygame.draw.circle(surface, (220, 30, 30), (cx, cy), s + 1)
    elif icon == 'recording':   # ● (pulsing red)
        pulse = int(abs(((pygame.time.get_ticks() % 1000) / 500) - 1) * 80)
        pygame.draw.circle(surface, (220, 30 + pulse, 30), (cx, cy), s + 1)
        _ensure_fonts()
        txt = _BTN_FONT.render('REC', True, (220, 30, 30))
        surface.blit(txt, txt.get_rect(centery=cy, left=cx + s + 4))
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


# ------------------------------------------------------------------
# Scan speed slider
# ------------------------------------------------------------------

def make_slider_rect(screen_width: int, screen_height: int) -> pygame.Rect:
    """Return the rect for the scan speed slider, positioned above the transport buttons."""
    row_top = screen_height - config.BUTTON_ROW_HEIGHT
    return pygame.Rect(100, row_top + 4, screen_width - 200, 28)


def draw_scan_slider(surface: pygame.Surface, rect: pygame.Rect,
                     value_s: float) -> None:
    """Draw a horizontal scan speed slider with tick marks and value label."""
    _ensure_fonts()
    min_s = config.SCAN_DWELL_MIN_S
    max_s = config.SCAN_DWELL_MAX_S
    step_s = config.SCAN_DWELL_STEP_S

    track_y = rect.centery

    # Label on the left
    lbl = _SLIDER_FONT.render('SCAN SPEED', True, config.DIM_ACCENT)
    surface.blit(lbl, lbl.get_rect(right=rect.left - 8, centery=track_y))

    # Value on the right
    val_txt = _SLIDER_FONT.render(f'{value_s:.1f}s', True, config.ACCENT_COLOR)
    surface.blit(val_txt, val_txt.get_rect(left=rect.right + 8, centery=track_y))

    # Track line
    pygame.draw.line(surface, config.BORDER_COLOR,
                     (rect.left, track_y), (rect.right, track_y), 2)

    # Tick marks — major ticks every 0.5s, minor every 0.1s
    n_ticks = int((max_s - min_s) / step_s) + 1
    for i in range(n_ticks):
        val = min_s + i * step_s
        t = (val - min_s) / (max_s - min_s)
        x = rect.left + int(t * rect.width)
        is_major = abs(val - round(val * 2) / 2) < 0.01  # every 0.5s
        tick_h = 6 if is_major else 3
        color = config.DIM_ACCENT if is_major else config.BORDER_COLOR
        pygame.draw.line(surface, color,
                         (x, track_y - tick_h), (x, track_y + tick_h), 1)

    # Thumb
    t = (value_s - min_s) / (max_s - min_s)
    thumb_x = rect.left + int(t * rect.width)
    pygame.draw.circle(surface, config.ACCENT_COLOR, (thumb_x, track_y), 9)
    pygame.draw.circle(surface, config.BG_COLOR, (thumb_x, track_y), 5)


def handle_slider_touch(pos: tuple[int, int], rect: pygame.Rect) -> float | None:
    """If pos is within the slider's touch area, return the snapped value in seconds.
    Returns None if the touch is outside the slider."""
    # Expand touch area for fat fingers
    touch_rect = rect.inflate(20, 20)
    if not touch_rect.collidepoint(pos):
        return None
    min_s = config.SCAN_DWELL_MIN_S
    max_s = config.SCAN_DWELL_MAX_S
    step_s = config.SCAN_DWELL_STEP_S
    t = (pos[0] - rect.left) / rect.width
    t = max(0.0, min(1.0, t))
    raw = min_s + t * (max_s - min_s)
    # Snap to nearest step
    snapped = round(raw / step_s) * step_s
    return max(min_s, min(max_s, snapped))


# ------------------------------------------------------------------
# Volume slider (vertical, right side)
# ------------------------------------------------------------------

_VOL_WIDTH = 30  # track area width
_VOL_MARGIN = 8  # right edge padding

def make_volume_rect(screen_width: int, screen_height: int) -> pygame.Rect:
    """Return the rect for the vertical volume slider on the right edge."""
    top = config.HEADER_HEIGHT + 12
    bottom = screen_height - config.BUTTON_ROW_HEIGHT - 12
    x = screen_width - _VOL_WIDTH - _VOL_MARGIN
    return pygame.Rect(x, top, _VOL_WIDTH, bottom - top)


def draw_volume_slider(surface: pygame.Surface, rect: pygame.Rect,
                       volume: float) -> None:
    """Draw a vertical volume slider. volume is 0.0–1.0."""
    _ensure_fonts()
    track_x = rect.centerx

    # Label above
    lbl = _SLIDER_FONT.render('VOL', True, config.DIM_ACCENT)
    surface.blit(lbl, lbl.get_rect(centerx=track_x, bottom=rect.top - 2))

    # Percentage below
    pct = _SLIDER_FONT.render(f'{int(volume * 100)}', True, config.ACCENT_COLOR)
    surface.blit(pct, pct.get_rect(centerx=track_x, top=rect.bottom + 2))

    # Track line (vertical)
    pygame.draw.line(surface, config.BORDER_COLOR,
                     (track_x, rect.top), (track_x, rect.bottom), 2)

    # Tick marks at 0%, 25%, 50%, 75%, 100%
    for pct_val in (0, 25, 50, 75, 100):
        t = pct_val / 100
        y = rect.bottom - int(t * rect.height)
        pygame.draw.line(surface, config.DIM_ACCENT,
                         (track_x - 6, y), (track_x + 6, y), 1)

    # Filled portion below thumb
    thumb_y = rect.bottom - int(volume * rect.height)
    pygame.draw.line(surface, config.ACCENT_COLOR,
                     (track_x, thumb_y), (track_x, rect.bottom), 3)

    # Thumb
    pygame.draw.circle(surface, config.ACCENT_COLOR, (track_x, thumb_y), 9)
    pygame.draw.circle(surface, config.BG_COLOR, (track_x, thumb_y), 5)


def handle_volume_touch(pos: tuple[int, int], rect: pygame.Rect) -> float | None:
    """If pos is within the volume slider touch area, return volume 0.0–1.0.
    Snaps to nearest 5%."""
    touch_rect = rect.inflate(30, 20)
    if not touch_rect.collidepoint(pos):
        return None
    # Bottom = 0%, Top = 100%
    t = (rect.bottom - pos[1]) / rect.height
    t = max(0.0, min(1.0, t))
    # Snap to 5%
    snapped = round(t * 20) / 20
    return max(0.0, min(1.0, snapped))


# ------------------------------------------------------------------
# Transport button layout
# ------------------------------------------------------------------

def make_transport_rects(screen_width: int, screen_height: int) -> dict[str, pygame.Rect]:
    """Return hit rects for the 5 transport buttons in the bottom row.

    Keys: 'prev', 'scan_back', 'pause', 'scan_fwd', 'next'
    """
    # Buttons sit in the lower portion of the button row (below the slider)
    btn_area_bottom = screen_height - 4
    y = btn_area_bottom - config.BTN_HEIGHT
    buttons = [('prev', config.BTN_SIDE_W), ('scan_back', config.BTN_SCAN_W),
               ('pause', config.BTN_CENTER_W),
               ('scan_fwd', config.BTN_SCAN_W), ('next', config.BTN_SIDE_W)]
    n_gaps = len(buttons) - 1
    total  = sum(w for _, w in buttons) + config.BTN_MARGIN * n_gaps
    x0     = (screen_width - total) // 2
    rects  = {}
    cursor = x0
    for i, (name, w) in enumerate(buttons):
        rects[name] = pygame.Rect(cursor, y, w, config.BTN_HEIGHT)
        cursor += w + (config.BTN_MARGIN if i < len(buttons) - 1 else 0)
    return rects

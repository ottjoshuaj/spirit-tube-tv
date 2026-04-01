"""Touchscreen number pad overlay for manual frequency/channel entry."""
import pygame
import config

_PAD_WIDTH  = 340
_PAD_HEIGHT = 370
_KEY_W      = 100
_KEY_H      = 52
_KEY_GAP    = 6
_DISPLAY_H  = 48
_ACTION_H   = 52

_font      = None
_disp_font = None
_hint_font = None


def _init_fonts():
    global _font, _disp_font, _hint_font
    if _font is None:
        _font      = pygame.font.SysFont('freesans', 26, bold=True)
        _disp_font = pygame.font.SysFont('freesans', 30, bold=True)
        _hint_font = pygame.font.SysFont('freesans', 13)


# Key layout: 4 rows of 3 keys, then 2 action keys
_DIGIT_ROWS = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    ['.', '0', '\u232b'],   # last row: dot, zero, backspace symbol
]


class NumberPad:
    """Modal number pad overlay.

    mode: 'fm'  -> input in MHz with decimal (e.g. "98.9"), hint "MHz"
          'am'  -> input in kHz, integers only (e.g. "1200"), hint "kHz"
          'tv'  -> input channel number, integers only (e.g. "14"), hint "CH"
    """

    def __init__(self, mode: str):
        self.mode = mode
        self._input = ''
        self._allow_dot = (mode == 'fm')
        self.active = True

        # Center the pad on screen
        self._x = (config.SCREEN_WIDTH  - _PAD_WIDTH)  // 2
        self._y = (config.SCREEN_HEIGHT - _PAD_HEIGHT) // 2
        self._build_rects()

    def _build_rects(self):
        x0 = self._x
        y0 = self._y

        # Outer background
        self._bg_rect = pygame.Rect(x0, y0, _PAD_WIDTH, _PAD_HEIGHT)

        # Display area
        self._display_rect = pygame.Rect(
            x0 + _KEY_GAP, y0 + _KEY_GAP,
            _PAD_WIDTH - _KEY_GAP * 2, _DISPLAY_H
        )

        # Digit key rects
        self._key_rects: list[tuple[str, pygame.Rect]] = []
        grid_x0 = x0 + (_PAD_WIDTH - (3 * _KEY_W + 2 * _KEY_GAP)) // 2
        grid_y0 = y0 + _KEY_GAP + _DISPLAY_H + _KEY_GAP

        for row_i, row in enumerate(_DIGIT_ROWS):
            for col_i, label in enumerate(row):
                kx = grid_x0 + col_i * (_KEY_W + _KEY_GAP)
                ky = grid_y0 + row_i * (_KEY_H + _KEY_GAP)
                self._key_rects.append((label, pygame.Rect(kx, ky, _KEY_W, _KEY_H)))

        # Action row: Cancel / GO
        action_y = grid_y0 + 4 * (_KEY_H + _KEY_GAP)
        half_w = (_PAD_WIDTH - _KEY_GAP * 3) // 2
        self._cancel_rect = pygame.Rect(x0 + _KEY_GAP, action_y, half_w, _ACTION_H)
        self._go_rect = pygame.Rect(
            x0 + _KEY_GAP * 2 + half_w, action_y, half_w, _ACTION_H
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        """Handle a touch event. Returns:
          'cancel'  - user dismissed the pad
          'go'      - user confirmed (read .value for the result)
          None      - touch was on a key or ignored
        """
        if not self.active:
            return None

        # Cancel
        if self._cancel_rect.collidepoint(pos):
            self.active = False
            return 'cancel'

        # Go
        if self._go_rect.collidepoint(pos):
            self.active = False
            return 'go'

        # Digit / dot / backspace keys
        for label, rect in self._key_rects:
            if rect.collidepoint(pos):
                self._on_key(label)
                return None

        # Touch outside pad = cancel
        if not self._bg_rect.collidepoint(pos):
            self.active = False
            return 'cancel'

        return None

    @property
    def value(self) -> str:
        return self._input

    # ------------------------------------------------------------------

    def _on_key(self, label: str):
        if label == '\u232b':  # backspace
            self._input = self._input[:-1]
        elif label == '.':
            if self._allow_dot and '.' not in self._input:
                self._input += '.'
        else:
            # Limit input length
            max_len = 6 if self.mode == 'fm' else 4 if self.mode == 'am' else 2
            if len(self._input) < max_len:
                self._input += label

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        _init_fonts()

        # Dim overlay behind the pad
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        # Pad background
        pygame.draw.rect(surface, config.BG_COLOR, self._bg_rect, border_radius=12)
        pygame.draw.rect(surface, config.ACCENT_COLOR, self._bg_rect, width=2, border_radius=12)

        # Display
        pygame.draw.rect(surface, (5, 0, 10), self._display_rect, border_radius=6)
        pygame.draw.rect(surface, config.BORDER_COLOR, self._display_rect, width=1, border_radius=6)

        if self.mode == 'fm':
            suffix = ' MHz'
        elif self.mode == 'am':
            suffix = ' kHz'
        else:
            suffix = ''
        display_text = self._input + ('_' if not self._input else '') + suffix
        txt = _disp_font.render(display_text, True, config.ACCENT_COLOR)
        surface.blit(txt, txt.get_rect(center=self._display_rect.center))

        # Hint text above display
        if self.mode == 'fm':
            hint = 'Enter frequency (87.5 - 108.0)'
        elif self.mode == 'am':
            hint = 'Enter frequency (530 - 1700)'
        else:
            hint = 'Enter channel (2 - 51)'
        hint_txt = _hint_font.render(hint, True, config.DIM_ACCENT)
        surface.blit(hint_txt, hint_txt.get_rect(
            centerx=self._bg_rect.centerx,
            bottom=self._display_rect.top - 2
        ))

        # Digit keys
        for label, rect in self._key_rects:
            # Hide dot key for non-FM modes
            if label == '.' and not self._allow_dot:
                pygame.draw.rect(surface, config.BG_COLOR, rect, border_radius=8)
                continue

            pygame.draw.rect(surface, config.BUTTON_BG, rect, border_radius=8)
            pygame.draw.rect(surface, config.BORDER_COLOR, rect, width=1, border_radius=8)
            lbl = _font.render(label, True, config.ACCENT_COLOR)
            surface.blit(lbl, lbl.get_rect(center=rect.center))

        # Cancel button
        pygame.draw.rect(surface, config.BUTTON_BG, self._cancel_rect, border_radius=8)
        pygame.draw.rect(surface, config.BORDER_COLOR, self._cancel_rect, width=1, border_radius=8)
        c_txt = _font.render('CANCEL', True, config.DIM_ACCENT)
        surface.blit(c_txt, c_txt.get_rect(center=self._cancel_rect.center))

        # GO button
        pygame.draw.rect(surface, config.BUTTON_ACTIVE_BG, self._go_rect, border_radius=8)
        pygame.draw.rect(surface, config.ACCENT_COLOR, self._go_rect, width=2, border_radius=8)
        g_txt = _font.render('GO', True, config.ACCENT_COLOR)
        surface.blit(g_txt, g_txt.get_rect(center=self._go_rect.center))

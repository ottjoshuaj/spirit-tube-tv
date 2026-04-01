import pygame
import config

# Layout — Two rows of 3: FM, TV, Spirit Box  |  Yes/No, RF Detector, Phonetic
_MARGIN   = 14
_ROW1_Y   = 80
_ROW2_Y   = 210
_BTN_H    = 110
_COL3_W   = (config.SCREEN_WIDTH - _MARGIN * 4) // 3

def _rc(row_y, col):
    return pygame.Rect(_MARGIN + col * (_COL3_W + _MARGIN), row_y, _COL3_W, _BTN_H)

# (id, rect, label, sublabel)
_BUTTONS = [
    ('fm',          _rc(_ROW1_Y, 0), 'FM RADIO',       '87.5–108 MHz'),
    ('tv',          _rc(_ROW1_Y, 1), 'TV',             'VHF / UHF'),
    ('spiritbox',   _rc(_ROW1_Y, 2), 'SPIRIT BOX',     'FM Sweep'),
    ('yesno',       _rc(_ROW2_Y, 0), 'YES / NO',       '433 MHz ISM'),
    ('disturbance', _rc(_ROW2_Y, 1), 'RF DETECTOR',    'REM-Pod Style'),
    ('phonetic',    _rc(_ROW2_Y, 2), 'PHONETIC',       'Ovilus-Style'),
]

_EXIT_RECT = pygame.Rect(config.SCREEN_WIDTH - 80, config.SCREEN_HEIGHT - 52, 68, 40)

# Theme selector — three colored circles at bottom-left
_THEME_Y      = config.SCREEN_HEIGHT - 42
_THEME_RADIUS = 14
_THEME_GAP    = 40
_THEME_ITEMS  = [
    ('purple', (204, 68, 255)),
    ('green',  (  0, 255,  65)),
    ('ember',  (255, 140,   0)),
]

def _theme_center(i):
    return (20 + _THEME_RADIUS + i * _THEME_GAP, _THEME_Y)

_TITLE_FONT = None
_LABEL_FONT = None
_SUB_FONT   = None
_EXIT_FONT  = None


def _init_fonts():
    global _TITLE_FONT, _LABEL_FONT, _SUB_FONT, _EXIT_FONT
    if _TITLE_FONT is None:
        _TITLE_FONT = pygame.font.SysFont('freesans', 32, bold=True)
        _LABEL_FONT = pygame.font.SysFont('freesans', 22, bold=True)
        _SUB_FONT   = pygame.font.SysFont('freesans', 14)
        _EXIT_FONT  = pygame.font.SysFont('freesans', 16, bold=True)


class BandSelectScreen:
    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        if _EXIT_RECT.collidepoint(pos):
            return 'exit'

        # Theme selector
        for i, (theme_name, _color) in enumerate(_THEME_ITEMS):
            cx, cy = _theme_center(i)
            dx, dy = pos[0] - cx, pos[1] - cy
            if dx * dx + dy * dy <= (_THEME_RADIUS + 4) ** 2:
                config.apply_theme(theme_name)
                return None

        for mode, rect, *_ in _BUTTONS:
            if rect.collidepoint(pos):
                return mode
        return None

    def stop(self) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        _init_fonts()
        surface.fill(config.BG_COLOR)

        # Title
        title = _TITLE_FONT.render('SPIRIT TUBE TV', True, config.ACCENT_COLOR)
        surface.blit(title, title.get_rect(centerx=config.SCREEN_WIDTH // 2, y=24))

        # Buttons
        for _mode, rect, label, sublabel in _BUTTONS:
            border = config.ACCENT_COLOR
            pygame.draw.rect(surface, config.BUTTON_BG, rect, border_radius=10)
            pygame.draw.rect(surface, border, rect, width=2, border_radius=10)

            lbl = _LABEL_FONT.render(label, True, border)
            sub = _SUB_FONT.render(sublabel, True, config.DIM_ACCENT)
            surface.blit(lbl, lbl.get_rect(centerx=rect.centerx,
                                            centery=rect.centery - 12))
            surface.blit(sub, sub.get_rect(centerx=rect.centerx,
                                            centery=rect.centery + 16))

        # Row labels
        r1_label = _SUB_FONT.render('RECEIVERS', True, config.DIM_ACCENT)
        surface.blit(r1_label, (config.SCREEN_WIDTH // 2 - r1_label.get_width() // 2,
                                _ROW1_Y - 16))
        r2_label = _SUB_FONT.render('TOOLS', True, config.DIM_ACCENT)
        surface.blit(r2_label, (config.SCREEN_WIDTH // 2 - r2_label.get_width() // 2,
                                _ROW2_Y - 16))

        # Hint
        hint = _SUB_FONT.render('TAP TO BEGIN', True, config.DIM_ACCENT)
        surface.blit(hint, hint.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                          y=_ROW2_Y + _BTN_H + 14))

        # Theme selector circles
        for i, (theme_name, preview_color) in enumerate(_THEME_ITEMS):
            cx, cy = _theme_center(i)
            pygame.draw.circle(surface, preview_color, (cx, cy), _THEME_RADIUS)
            if config.CURRENT_THEME == theme_name:
                pygame.draw.circle(surface, (255, 255, 255), (cx, cy),
                                   _THEME_RADIUS + 3, 2)
            else:
                pygame.draw.circle(surface, (60, 60, 60), (cx, cy),
                                   _THEME_RADIUS + 1, 1)

        # Exit button
        pygame.draw.rect(surface, config.BUTTON_BG, _EXIT_RECT, border_radius=8)
        pygame.draw.rect(surface, (180, 40, 40), _EXIT_RECT, width=2, border_radius=8)
        ext = _EXIT_FONT.render('EXIT', True, (180, 40, 40))
        surface.blit(ext, ext.get_rect(center=_EXIT_RECT.center))

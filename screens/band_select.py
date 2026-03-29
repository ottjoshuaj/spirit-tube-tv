import pygame
import config

# Button layout: three equal-width buttons in the lower 60% of the screen
_BTN_Y      = 160
_BTN_HEIGHT = 150
_BTN_MARGIN = 20
_BTN_WIDTH  = (config.SCREEN_WIDTH - _BTN_MARGIN * 4) // 3

_BUTTONS = [
    ('fm', pygame.Rect(_BTN_MARGIN,                         _BTN_Y, _BTN_WIDTH, _BTN_HEIGHT), '📻', 'FM',  '87.5–108 MHz'),
    ('am', pygame.Rect(_BTN_MARGIN * 2 + _BTN_WIDTH,        _BTN_Y, _BTN_WIDTH, _BTN_HEIGHT), '🎙', 'AM',  '530–1700 kHz'),
    ('tv', pygame.Rect(_BTN_MARGIN * 3 + _BTN_WIDTH * 2,   _BTN_Y, _BTN_WIDTH, _BTN_HEIGHT), '📺', 'TV',  'VHF / UHF'),
]

_TITLE_FONT = None
_LABEL_FONT = None
_SUB_FONT   = None


def _init_fonts():
    global _TITLE_FONT, _LABEL_FONT, _SUB_FONT
    if _TITLE_FONT is None:
        _TITLE_FONT = pygame.font.SysFont('freesans', 36, bold=True)
        _LABEL_FONT = pygame.font.SysFont('freesans', 28, bold=True)
        _SUB_FONT   = pygame.font.SysFont('freesans', 16)


class BandSelectScreen:
    def handle_touch(self, pos: tuple[int, int]) -> str | None:
        for mode, rect, *_ in _BUTTONS:
            if rect.collidepoint(pos):
                return mode
        return None

    def render(self, surface: pygame.Surface) -> None:
        _init_fonts()
        surface.fill(config.BG_COLOR)

        # Title
        title = _TITLE_FONT.render('SPIRIT TUBE TV', True, config.ACCENT_COLOR)
        surface.blit(title, title.get_rect(centerx=config.SCREEN_WIDTH // 2, y=50))

        subtitle = _SUB_FONT.render('SELECT BAND', True, config.DIM_ACCENT)
        surface.blit(subtitle, subtitle.get_rect(centerx=config.SCREEN_WIDTH // 2, y=110))

        for _mode, rect, _icon, label, sublabel in _BUTTONS:
            pygame.draw.rect(surface, config.BUTTON_BG,   rect, border_radius=12)
            pygame.draw.rect(surface, config.ACCENT_COLOR, rect, width=2, border_radius=12)

            lbl  = _LABEL_FONT.render(label,    True, config.ACCENT_COLOR)
            sub  = _SUB_FONT.render(sublabel,   True, config.DIM_ACCENT)
            surface.blit(lbl, lbl.get_rect(centerx=rect.centerx, y=rect.y + 60))
            surface.blit(sub, sub.get_rect(centerx=rect.centerx, y=rect.y + 100))

        hint = _SUB_FONT.render('TAP A BAND TO BEGIN', True, config.DIM_ACCENT)
        surface.blit(hint, hint.get_rect(centerx=config.SCREEN_WIDTH // 2, y=340))

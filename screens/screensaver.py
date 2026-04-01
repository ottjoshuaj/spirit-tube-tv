# screens/screensaver.py
"""DVD-style bouncing logo screensaver."""
import os
import pygame
import config

_LOGO_SCALE = 96  # px height for the bouncing logo


class Screensaver:
    def __init__(self):
        self._active = False
        self._logo: pygame.Surface | None = None
        self._font: pygame.Font | None = None
        self._x = 100.0
        self._y = 80.0
        self._vx = 1.5   # pixels per frame
        self._vy = 1.0
        self._last_activity_ms = pygame.time.get_ticks()

    def _ensure_assets(self) -> None:
        if self._logo is not None:
            return
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon.png')
        if os.path.exists(icon_path):
            raw = pygame.image.load(icon_path).convert_alpha()
            aspect = raw.get_width() / raw.get_height()
            self._logo = pygame.transform.smoothscale(
                raw, (int(_LOGO_SCALE * aspect), _LOGO_SCALE)
            )
        else:
            self._logo = None
        self._font = pygame.font.SysFont('freesans', 22, bold=True)

    @property
    def active(self) -> bool:
        return self._active

    def poke(self) -> None:
        """Call on any user input to reset the idle timer."""
        self._last_activity_ms = pygame.time.get_ticks()
        self._active = False

    def update(self) -> None:
        """Check idle time and activate if needed."""
        if not self._active:
            elapsed = pygame.time.get_ticks() - self._last_activity_ms
            if elapsed >= config.SCREENSAVER_TIMEOUT_MS:
                self._active = True

    def render(self, surface: pygame.Surface) -> None:
        self._ensure_assets()
        surface.fill((0, 0, 0))

        # Build the composite: logo + text label
        label = self._font.render('SPIRIT TUBE TV', True, config.ACCENT_COLOR)
        logo_w = self._logo.get_width() if self._logo else 0
        logo_h = self._logo.get_height() if self._logo else 0
        total_w = max(logo_w, label.get_width())
        total_h = logo_h + 6 + label.get_height()

        # Bounce
        self._x += self._vx
        self._y += self._vy
        if self._x <= 0 or self._x + total_w >= config.SCREEN_WIDTH:
            self._vx = -self._vx
            self._x = max(0.0, min(self._x, config.SCREEN_WIDTH - total_w))
        if self._y <= 0 or self._y + total_h >= config.SCREEN_HEIGHT:
            self._vy = -self._vy
            self._y = max(0.0, min(self._y, config.SCREEN_HEIGHT - total_h))

        ix, iy = int(self._x), int(self._y)
        if self._logo:
            surface.blit(self._logo, (ix + (total_w - logo_w) // 2, iy))
        surface.blit(label, (ix + (total_w - label.get_width()) // 2,
                             iy + logo_h + 6))

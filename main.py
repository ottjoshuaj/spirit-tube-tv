import os
import subprocess
import sys
import threading
import time

import pygame
import config


# ======================================================================
# Splash screen — shown immediately while BT + imports load
# ======================================================================

def _show_splash(screen: pygame.Surface) -> None:
    """Render a loading splash and flip once."""
    screen.fill((0, 0, 0))
    # Logo
    icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
    if os.path.exists(icon_path):
        logo = pygame.image.load(icon_path).convert_alpha()
        logo = pygame.transform.smoothscale(logo, (128, 128))
        screen.blit(logo, logo.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                         centery=config.SCREEN_HEIGHT // 2 - 40))
    font_big = pygame.font.SysFont('freesans', 36, bold=True)
    font_sm  = pygame.font.SysFont('freesans', 16)
    title = font_big.render('SPIRIT TUBE TV', True, config.ACCENT_COLOR)
    screen.blit(title, title.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                       centery=config.SCREEN_HEIGHT // 2 + 50))
    loading = font_sm.render('Loading...', True, config.DIM_ACCENT)
    screen.blit(loading, loading.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                           centery=config.SCREEN_HEIGHT // 2 + 90))
    pygame.display.flip()


def _connect_bluetooth() -> None:
    """Try to connect BT speaker in background. Non-blocking, best-effort."""
    bt_mac = '5C:FB:7C:B7:B5:AE'
    for _ in range(15):
        try:
            result = subprocess.run(
                ['bluetoothctl', 'info', bt_mac],
                capture_output=True, text=True, timeout=5,
            )
            if 'Connected: yes' in result.stdout:
                return
            subprocess.run(
                ['bluetoothctl', 'connect', bt_mac],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass
        time.sleep(2)


# ======================================================================
# Main
# ======================================================================

def main() -> None:
    pygame.init()
    pygame.mouse.set_visible(False)
    screen = pygame.display.set_mode(
        (config.SCREEN_WIDTH, config.SCREEN_HEIGHT),
        pygame.FULLSCREEN,
    )
    pygame.display.set_caption('Spirit Tube TV')

    # Show splash immediately
    _show_splash(screen)

    # Connect Bluetooth in background while we finish loading
    bt_thread = threading.Thread(target=_connect_bluetooth, daemon=True)
    bt_thread.start()

    # Heavy imports happen here — after splash is visible
    from sdr.sdr_manager import SdrManager
    from sdr.audio_output import AudioOutput
    from screens.band_select import BandSelectScreen
    from screens.fm_am_screen import FmAmScreen
    from screens.tv_screen import TvScreen
    from screens.yesno_screen import YesNoScreen
    from screens.spiritbox_screen import SpiritBoxScreen
    from screens.disturbance_screen import DisturbanceScreen
    from screens.phonetic_screen import PhoneticScreen
    from screens.screensaver import Screensaver

    clock = pygame.time.Clock()
    sdr   = SdrManager()
    audio = AudioOutput()

    current_screen = BandSelectScreen()
    screensaver = Screensaver()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                # If screensaver is showing, dismiss it and swallow the tap
                if screensaver.active:
                    screensaver.poke()
                    continue

                screensaver.poke()
                result = current_screen.handle_touch(event.pos)

                if result == 'exit':
                    running = False

                elif result == 'back':
                    current_screen.stop()
                    current_screen = BandSelectScreen()

                elif result == 'fm':
                    new_screen = FmAmScreen('fm')
                    if new_screen.start(sdr, audio):
                        current_screen = new_screen

                elif result == 'tv':
                    new_screen = TvScreen()
                    if new_screen.start(sdr, audio):
                        current_screen = new_screen

                elif result == 'spiritbox':
                    new_screen = SpiritBoxScreen()
                    if new_screen.start(sdr, audio):
                        current_screen = new_screen

                elif result == 'yesno':
                    new_screen = YesNoScreen()
                    if new_screen.start():
                        current_screen = new_screen

                elif result == 'disturbance':
                    new_screen = DisturbanceScreen()
                    if new_screen.start():
                        current_screen = new_screen

                elif result == 'phonetic':
                    new_screen = PhoneticScreen()
                    if new_screen.start():
                        current_screen = new_screen

        # Screensaver only activates on the band-select (main menu) screen
        if isinstance(current_screen, BandSelectScreen):
            screensaver.update()
        else:
            screensaver.poke()

        if screensaver.active:
            screensaver.render(screen)
        else:
            try:
                current_screen.render(screen)
            except Exception:
                pass  # skip bad frame rather than crash
        pygame.display.flip()
        clock.tick(config.TARGET_FPS)

    # Graceful shutdown
    if hasattr(current_screen, 'stop'):
        current_screen.stop()
    pygame.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()

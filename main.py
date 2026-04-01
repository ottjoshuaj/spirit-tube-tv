import sys
import pygame
import config
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


def main() -> None:
    pygame.init()
    pygame.mouse.set_visible(False)          # hide cursor on touchscreen
    screen = pygame.display.set_mode(
        (config.SCREEN_WIDTH, config.SCREEN_HEIGHT),
        pygame.FULLSCREEN,
    )
    pygame.display.set_caption('Spirit Tube TV')
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

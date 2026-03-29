import sys
import pygame
import config
from sdr.sdr_manager import SdrManager
from sdr.audio_output import AudioOutput
from screens.band_select import BandSelectScreen
from screens.fm_am_screen import FmAmScreen
from screens.tv_screen import TvScreen


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
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                result = current_screen.handle_touch(event.pos)

                if result == 'back':
                    # Full stop — SDR + audio halted before returning to menu
                    current_screen.stop()
                    current_screen = BandSelectScreen()

                elif result in ('fm', 'am'):
                    current_screen = FmAmScreen(result)
                    current_screen.start(sdr, audio)

                elif result == 'tv':
                    current_screen = TvScreen()
                    current_screen.start(sdr, audio)

        current_screen.render(screen)
        pygame.display.flip()
        clock.tick(config.TARGET_FPS)

    # Graceful shutdown
    if hasattr(current_screen, 'stop'):
        current_screen.stop()
    pygame.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()

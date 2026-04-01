# config.py

# Display
SCREEN_WIDTH  = 800
SCREEN_HEIGHT = 480
TARGET_FPS    = 30

# Layout zones (pixels)
HEADER_HEIGHT     = 44
BUTTON_ROW_HEIGHT = 90
TV_FRAME_WIDTH    = SCREEN_WIDTH
TV_FRAME_HEIGHT   = SCREEN_HEIGHT - HEADER_HEIGHT - BUTTON_ROW_HEIGHT  # 382

# Theme definitions — all use black-ish backgrounds
THEMES = {
    'purple': {
        'BG_COLOR':         (10,  0,  16),
        'ACCENT_COLOR':     (204, 68, 255),
        'DIM_ACCENT':       (102,  0, 170),
        'BORDER_COLOR':     ( 61,  0,  96),
        'BUTTON_BG':        ( 20,  0,  36),
        'BUTTON_ACTIVE_BG': ( 61,  0,  96),
        'HEADER_BG':        (  6,  0,  12),
    },
    'green': {
        'BG_COLOR':         (  0,  6,  0),
        'ACCENT_COLOR':     (  0, 255,  65),
        'DIM_ACCENT':       (  0, 120,  30),
        'BORDER_COLOR':     (  0,  60,  15),
        'BUTTON_BG':        (  0,  18,   4),
        'BUTTON_ACTIVE_BG': (  0,  60,  15),
        'HEADER_BG':        (  0,   4,   0),
    },
    'ember': {
        'BG_COLOR':         (  8,   4,   0),
        'ACCENT_COLOR':     (255, 140,   0),
        'DIM_ACCENT':       (140,  70,   0),
        'BORDER_COLOR':     ( 70,  35,   0),
        'BUTTON_BG':        ( 22,  10,   0),
        'BUTTON_ACTIVE_BG': ( 70,  35,   0),
        'HEADER_BG':        (  5,   2,   0),
    },
}

CURRENT_THEME = 'purple'

def apply_theme(name: str) -> None:
    """Switch active color theme. All modules read from config.* so changes are immediate."""
    import config
    if name not in THEMES:
        return
    config.CURRENT_THEME = name
    for key, value in THEMES[name].items():
        setattr(config, key, value)

# Colors — initialized to default theme (purple)
BG_COLOR          = THEMES['purple']['BG_COLOR']
ACCENT_COLOR      = THEMES['purple']['ACCENT_COLOR']
DIM_ACCENT        = THEMES['purple']['DIM_ACCENT']
BORDER_COLOR      = THEMES['purple']['BORDER_COLOR']
BUTTON_BG         = THEMES['purple']['BUTTON_BG']
BUTTON_ACTIVE_BG  = THEMES['purple']['BUTTON_ACTIVE_BG']
HEADER_BG         = THEMES['purple']['HEADER_BG']

# SDR sample rates (chosen so sample_rate // AUDIO_RATE is a clean integer)
FM_SAMPLE_RATE  =   960_000   # decimation 20  → 48 000 Hz audio
AM_SAMPLE_RATE  =   240_000   # decimation  5  → 48 000 Hz audio
TV_SAMPLE_RATE  = 2_400_000
AUDIO_RATE      =    48_000

FM_AUDIO_DECIMATE = FM_SAMPLE_RATE // AUDIO_RATE   # 20
AM_AUDIO_DECIMATE = AM_SAMPLE_RATE // AUDIO_RATE   # 5

# SDR read sizes (samples per acquisition call)
SDR_READ_SIZE = {
    'fm': 65_536,
    'am': 16_384,
    'tv': 131_072,   # more real antenna noise per frame → better snow
}

# Audio
AUDIO_BLOCK_SIZE  = 2_048   # sounddevice callback blocksize
AUDIO_QUEUE_MAX   = 10      # max queued numpy chunks

# Scanning
# Scanning defaults (seconds)
SCAN_DWELL_DEFAULT_S = 1.0
SCAN_DWELL_MIN_S     = 0.1   # 100 ms — fast spirit-box sweep
SCAN_DWELL_MAX_S     = 5.0
SCAN_DWELL_STEP_S    = 0.1

# Screensaver (activates on band-select screen only)
SCREENSAVER_TIMEOUT_MS = 5 * 60 * 1000   # 5 minutes

# Waveform display
WAVEFORM_SAMPLES = 512

# Button layout (5 transport buttons, bottom row)
BTN_HEIGHT   = 44
BTN_MARGIN   = 6
BTN_CENTER_W = 54   # pause/play button slightly wider
BTN_SIDE_W   = 44   # step buttons
BTN_SCAN_W   = 90   # scan buttons (wider for "SCAN" label)

# Yes/No Detector
# Two RF bands monitored simultaneously via FFT.  The SDR tunes to the
# midpoint; energy in each sideband triggers YES or NO.
YESNO_CENTER_FREQ   = 433_000_000      # 433 MHz ISM band center
YESNO_BANDWIDTH     = 240_000          # SDR sample rate (±120 kHz)
YESNO_YES_OFFSET    = +50_000          # YES band: center + 50 kHz
YESNO_NO_OFFSET     = -50_000          # NO  band: center – 50 kHz
YESNO_BIN_WIDTH     = 20_000           # ±10 kHz around each offset
YESNO_THRESHOLD     = 3.0              # spike must be Nx above noise floor
YESNO_COOLDOWN_MS   = 3000             # min ms between triggers
YESNO_FFT_SIZE      = 4096
YESNO_READ_SIZE     = 16_384

# Spirit Box — fast FM sweep
SPIRITBOX_DWELL_DEFAULT_MS = 100   # ms per channel (real SB7 ≈ 75–150 ms)
SPIRITBOX_DWELL_MIN_MS     = 30
SPIRITBOX_DWELL_MAX_MS     = 500
SPIRITBOX_FREQS = [87_500_000 + i * 200_000 for i in range(103)]  # 0.2 MHz steps

# RF Disturbance Detector (REM-pod-like)
DISTURBANCE_FREQ       = 144_000_000   # 2m ham band — usually quiet
DISTURBANCE_BANDWIDTH  = 240_000
DISTURBANCE_READ_SIZE  = 8_192
DISTURBANCE_BASELINE_S = 5.0           # seconds to establish baseline
DISTURBANCE_LEVELS     = 5             # number of alert levels (rings)
DISTURBANCE_SENSITIVITY = 1.5          # multiplier above baseline = level 1

# Phonetic Decoder (Ovilus-style)
PHONETIC_FREQ          = 462_000_000   # FRS/GMRS band
PHONETIC_BANDWIDTH     = 240_000
PHONETIC_READ_SIZE     = 16_384
PHONETIC_TRIGGER_MULT  = 2.5           # energy multiplier to trigger a word
PHONETIC_COOLDOWN_MS   = 2000          # min ms between words

# FM frequencies: 87.5–108.0 MHz, 0.1 MHz steps
FM_FREQS = [87_500_000 + i * 100_000 for i in range(206)]

# AM frequencies: 530–1700 kHz, 10 kHz steps
AM_FREQS = [530_000 + i * 10_000 for i in range(118)]

# NTSC VHF picture-carrier frequencies (Hz)
VHF_CHANNELS = {
     2:  55_250_000,  3:  61_250_000,  4:  67_250_000,
     5:  77_250_000,  6:  83_250_000,
     7: 175_250_000,  8: 181_250_000,  9: 187_250_000,
    10: 193_250_000, 11: 199_250_000, 12: 205_250_000, 13: 211_250_000,
}

# NTSC UHF picture-carrier frequencies Ch14–51 (pre-repack analog)
UHF_CHANNELS = {ch: 471_250_000 + (ch - 14) * 6_000_000 for ch in range(14, 52)}

# Combined TV channel list: list of (ch_num, freq_hz, band_label)
TV_CHANNELS = (
    [(ch, freq, 'VHF') for ch, freq in sorted(VHF_CHANNELS.items())] +
    [(ch, freq, 'UHF') for ch, freq in sorted(UHF_CHANNELS.items())]
)

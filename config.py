# config.py

# Display
SCREEN_WIDTH  = 800
SCREEN_HEIGHT = 480
TARGET_FPS    = 30

# Layout zones (pixels)
HEADER_HEIGHT     = 44
BUTTON_ROW_HEIGHT = 54
TV_FRAME_WIDTH    = SCREEN_WIDTH
TV_FRAME_HEIGHT   = SCREEN_HEIGHT - HEADER_HEIGHT - BUTTON_ROW_HEIGHT  # 382

# Colors (paranormal dark theme)
BG_COLOR          = (13,  0,  21)   # #0d0015
ACCENT_COLOR      = (204, 68, 255)  # #cc44ff
DIM_ACCENT        = (102,  0, 170)  # #6600aa
BORDER_COLOR      = ( 61,  0,  96)  # #3d0060
BUTTON_BG         = ( 26,  0,  48)  # #1a0030
BUTTON_ACTIVE_BG  = ( 61,  0,  96)  # #3d0060
HEADER_BG         = (  8,  0,  15)  # #08000f

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
    'tv': 65_536,
}

# Audio
AUDIO_BLOCK_SIZE  = 2_048   # sounddevice callback blocksize
AUDIO_QUEUE_MAX   = 10      # max queued numpy chunks

# Scanning
SCAN_DWELL_MS = 1_500       # ms per channel during auto-scan

# Waveform display
WAVEFORM_SAMPLES = 512

# Button layout (5 transport buttons, bottom row)
BTN_HEIGHT   = 44
BTN_MARGIN   = 6
BTN_CENTER_W = 54   # pause/play button slightly wider
BTN_SIDE_W   = 44   # all other buttons

# FM frequencies: 87.5–108.0 MHz, 0.1 MHz steps
FM_FREQS = [87_500_000 + i * 100_000 for i in range(205)]

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

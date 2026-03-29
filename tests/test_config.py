# tests/test_config.py
import config

def test_fm_freq_count():
    assert len(config.FM_FREQS) == 206

def test_fm_freq_bounds():
    assert config.FM_FREQS[0]  == 87_500_000
    assert config.FM_FREQS[-1] == 108_000_000   # 108.0 MHz inclusive

def test_am_freq_count():
    assert len(config.AM_FREQS) == 118

def test_am_freq_bounds():
    assert config.AM_FREQS[0]  == 530_000
    assert config.AM_FREQS[-1] == 1_700_000

def test_vhf_ch2_freq():
    assert config.VHF_CHANNELS[2] == 55_250_000

def test_vhf_ch13_freq():
    assert config.VHF_CHANNELS[13] == 211_250_000

def test_uhf_ch14_freq():
    assert config.UHF_CHANNELS[14] == 471_250_000

def test_uhf_ch51_freq():
    assert config.UHF_CHANNELS[51] == 471_250_000 + 37 * 6_000_000

def test_tv_channels_order():
    vhf = [(ch, f, b) for ch, f, b in config.TV_CHANNELS if b == 'VHF']
    uhf = [(ch, f, b) for ch, f, b in config.TV_CHANNELS if b == 'UHF']
    assert vhf[0][0] == 2
    assert uhf[0][0] == 14

def test_audio_decimation_exact():
    assert config.FM_SAMPLE_RATE % config.AUDIO_RATE == 0
    assert config.AM_SAMPLE_RATE % config.AUDIO_RATE == 0

def test_tv_frame_height():
    assert config.TV_FRAME_HEIGHT == config.SCREEN_HEIGHT - config.HEADER_HEIGHT - config.BUTTON_ROW_HEIGHT

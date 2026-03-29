# tests/test_demodulator.py
import numpy as np
import pytest
from sdr.demodulator import fm_demodulate, am_demodulate, iq_to_frame

SAMPLE_RATE = 960_000
AUDIO_RATE  =  48_000

def _make_fm_tone(freq_hz: float, n: int) -> np.ndarray:
    """Generate IQ samples of a single FM-modulated tone."""
    t = np.arange(n) / SAMPLE_RATE
    phase = 2 * np.pi * freq_hz * t
    return np.exp(1j * phase).astype(np.complex64)

def _make_am_tone(carrier_hz: float, audio_hz: float, n: int) -> np.ndarray:
    t = np.arange(n) / 240_000
    carrier   = np.exp(1j * 2 * np.pi * carrier_hz * t)
    envelope  = 1.0 + 0.5 * np.sin(2 * np.pi * audio_hz * t)
    return (carrier * envelope).astype(np.complex64)

def test_fm_demodulate_returns_float32():
    iq = _make_fm_tone(1000, 65_536)
    audio = fm_demodulate(iq, SAMPLE_RATE, AUDIO_RATE)
    assert audio.dtype == np.float32

def test_fm_demodulate_output_length():
    iq = _make_fm_tone(1000, 65_536)
    audio = fm_demodulate(iq, SAMPLE_RATE, AUDIO_RATE)
    expected_len = (len(iq) - 1) // (SAMPLE_RATE // AUDIO_RATE)
    assert len(audio) == expected_len

def test_fm_demodulate_dc_tone_is_near_constant():
    # A pure carrier (no modulation) should demodulate to near-zero audio
    iq = _make_fm_tone(0, 65_536)  # DC
    audio = fm_demodulate(iq, SAMPLE_RATE, AUDIO_RATE)
    assert np.abs(audio).mean() < 0.01

def test_am_demodulate_returns_float32():
    iq = _make_am_tone(10_000, 1_000, 16_384)
    audio = am_demodulate(iq, 240_000, AUDIO_RATE)
    assert audio.dtype == np.float32

def test_am_demodulate_output_length():
    iq = _make_am_tone(10_000, 1_000, 16_384)
    audio = am_demodulate(iq, 240_000, AUDIO_RATE)
    expected_len = len(iq) // (240_000 // AUDIO_RATE)
    assert len(audio) == expected_len

def test_am_demodulate_normalized():
    iq = _make_am_tone(10_000, 1_000, 16_384)
    audio = am_demodulate(iq, 240_000, AUDIO_RATE)
    assert np.max(np.abs(audio)) <= 1.0 + 1e-6

def test_iq_to_frame_shape():
    iq = (np.random.randn(65_536) + 1j * np.random.randn(65_536)).astype(np.complex64)
    frame = iq_to_frame(iq, 800, 382)
    assert frame.shape == (382, 800)

def test_iq_to_frame_dtype():
    iq = (np.random.randn(65_536) + 1j * np.random.randn(65_536)).astype(np.complex64)
    frame = iq_to_frame(iq, 800, 382)
    assert frame.dtype == np.uint8

def test_iq_to_frame_range():
    iq = (np.random.randn(65_536) + 1j * np.random.randn(65_536)).astype(np.complex64)
    frame = iq_to_frame(iq, 800, 382)
    assert frame.min() >= 0
    assert frame.max() <= 255

def test_iq_to_frame_tiles_small_input():
    # Fewer IQ samples than pixels — should tile to fill
    iq = (np.random.randn(1_000) + 1j * np.random.randn(1_000)).astype(np.complex64)
    frame = iq_to_frame(iq, 800, 382)
    assert frame.shape == (382, 800)

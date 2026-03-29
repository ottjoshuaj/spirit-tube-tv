# sdr/demodulator.py
import numpy as np


def fm_demodulate(iq: np.ndarray, sample_rate: int, audio_rate: int) -> np.ndarray:
    """FM discriminator demodulation with integer decimation."""
    conj_product = iq[1:] * np.conj(iq[:-1])
    phase = np.angle(conj_product)
    decimate = sample_rate // audio_rate
    n_out = len(phase) // decimate
    audio = phase[:n_out * decimate:decimate]
    return audio.astype(np.float32)


def am_demodulate(iq: np.ndarray, sample_rate: int, audio_rate: int) -> np.ndarray:
    """AM envelope detection with integer decimation."""
    envelope = np.abs(iq)
    envelope -= envelope.mean()   # remove DC offset
    decimate = sample_rate // audio_rate
    n_out = len(envelope) // decimate
    audio = envelope[:n_out * decimate:decimate]
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val
    return audio.astype(np.float32)


def iq_to_frame(iq: np.ndarray, width: int, height: int) -> np.ndarray:
    """Convert IQ samples to (height, width) uint8 grayscale frame.

    Tiles samples if fewer than width*height, truncates if more.
    """
    n_pixels = width * height
    amplitude = np.abs(iq).astype(np.float32)
    if len(amplitude) < n_pixels:
        repeats = (n_pixels // len(amplitude)) + 1
        amplitude = np.tile(amplitude, repeats)
    amplitude = amplitude[:n_pixels]
    frame = amplitude.reshape(height, width)
    max_val = frame.max()
    if max_val > 0:
        frame = (frame / max_val * 255).astype(np.uint8)
    else:
        frame = np.zeros((height, width), dtype=np.uint8)
    return frame

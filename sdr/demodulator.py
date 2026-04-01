# sdr/demodulator.py
import numpy as np
from scipy.signal import firwin, lfilter, lfilter_zi


def _make_deemph_coefs(sample_rate: int, tau: float = 75e-6):
    """Return (b, a) for a single-pole de-emphasis IIR filter (75 µs NA standard)."""
    alpha = 1.0 / (sample_rate * tau + 1.0)
    b = np.array([alpha], dtype=np.float64)
    a = np.array([1.0, -(1.0 - alpha)], dtype=np.float64)
    return b, a


class FmDemodulator:
    """Stateful FM demodulator that maintains filter state across calls."""

    def __init__(self, sample_rate: int, audio_rate: int):
        self._decimate = sample_rate // audio_rate
        self._prev_sample = np.complex64(0)  # last IQ sample for phase continuity

        # Anti-alias LPF before decimation (cutoff 16 kHz for mono FM audio)
        self._lpf_b = firwin(64, 16_000, fs=sample_rate).astype(np.float64)
        self._lpf_a = np.array([1.0])
        self._lpf_zi = lfilter_zi(self._lpf_b, self._lpf_a) * 0

        # De-emphasis filter (75 µs)
        self._deemph_b, self._deemph_a = _make_deemph_coefs(audio_rate)
        self._deemph_zi = lfilter_zi(self._deemph_b, self._deemph_a) * 0

    def reset(self):
        self._prev_sample = np.complex64(0)
        self._lpf_zi = lfilter_zi(self._lpf_b, self._lpf_a) * 0
        self._deemph_zi = lfilter_zi(self._deemph_b, self._deemph_a) * 0

    def process(self, iq: np.ndarray) -> np.ndarray:
        # Phase discriminator with continuity across blocks
        iq_with_prev = np.concatenate([[self._prev_sample], iq])
        self._prev_sample = iq[-1]
        conj_product = iq_with_prev[1:] * np.conj(iq_with_prev[:-1])
        phase = np.angle(conj_product)

        # Anti-alias low-pass filter (stateful)
        phase_filtered, self._lpf_zi = lfilter(
            self._lpf_b, self._lpf_a, phase, zi=self._lpf_zi
        )

        # Decimate by averaging blocks
        decimate = self._decimate
        n_out = len(phase_filtered) // decimate
        audio = phase_filtered[:n_out * decimate].reshape(n_out, decimate).mean(axis=1)

        # De-emphasis (stateful)
        audio, self._deemph_zi = lfilter(
            self._deemph_b, self._deemph_a, audio, zi=self._deemph_zi
        )

        # Fixed-gain normalization with boost for typical broadcast levels
        audio = (audio / np.pi * 5.0).astype(np.float32)
        return np.clip(audio, -1.0, 1.0)


class AmDemodulator:
    """Stateful AM demodulator that maintains filter state across calls."""

    def __init__(self, sample_rate: int, audio_rate: int):
        self._decimate = sample_rate // audio_rate

        # Anti-alias LPF (cutoff 8 kHz for AM audio)
        self._lpf_b = firwin(64, 8_000, fs=sample_rate).astype(np.float64)
        self._lpf_a = np.array([1.0])
        self._lpf_zi = lfilter_zi(self._lpf_b, self._lpf_a) * 0

        # Running DC estimate for envelope removal (exponential moving average)
        self._dc = 0.0

    def reset(self):
        self._lpf_zi = lfilter_zi(self._lpf_b, self._lpf_a) * 0
        self._dc = 0.0

    def process(self, iq: np.ndarray) -> np.ndarray:
        envelope = np.abs(iq).astype(np.float64)

        # Remove DC with a smooth running average (avoids per-block mean jumps)
        alpha = 0.001
        for i in range(len(envelope)):
            self._dc += alpha * (envelope[i] - self._dc)
            envelope[i] -= self._dc

        # Anti-alias low-pass filter (stateful)
        env_filtered, self._lpf_zi = lfilter(
            self._lpf_b, self._lpf_a, envelope, zi=self._lpf_zi
        )

        # Decimate by averaging
        decimate = self._decimate
        n_out = len(env_filtered) // decimate
        audio = env_filtered[:n_out * decimate].reshape(n_out, decimate).mean(axis=1)

        # Normalize with headroom
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val * 0.8
        return audio.astype(np.float32)


# Standalone functions for backwards compatibility and TV mode

def fm_demodulate(iq, sample_rate, audio_rate):
    """Stateless wrapper — use FmDemodulator for streaming."""
    d = FmDemodulator(sample_rate, audio_rate)
    return d.process(iq)


def am_demodulate(iq, sample_rate, audio_rate):
    """Stateless wrapper — use AmDemodulator for streaming."""
    d = AmDemodulator(sample_rate, audio_rate)
    return d.process(iq)


def iq_to_frame(iq: np.ndarray, width: int, height: int) -> np.ndarray:
    """Convert IQ samples to (height, width) uint8 grayscale frame.

    Produces classic analog TV snow: real antenna noise stretched to fill
    the frame, with additive random noise so every pixel is unique.
    Percentile normalization + gamma give the punchy CRT snow look.
    """
    n_pixels = width * height
    amplitude = np.abs(iq).astype(np.float32)

    if len(amplitude) >= n_pixels:
        pixels = amplitude[:n_pixels]
    else:
        # Tile real data to fill frame (fast), then overlay unique noise
        repeats = (n_pixels // len(amplitude)) + 1
        pixels = np.tile(amplitude, repeats)[:n_pixels]

    frame = pixels.reshape(height, width)

    # Additive noise layer — breaks up any tiling pattern and gives every
    # pixel a unique value, just like real analog snow.
    noise_std = float(np.std(frame)) * 0.5
    frame += np.random.normal(0, max(noise_std, 0.01), frame.shape).astype(np.float32)

    # Percentile-based normalization — ignore outlier spikes so the bulk
    # of the noise uses the full 0-255 range (high contrast snow).
    lo = np.percentile(frame, 2)
    hi = np.percentile(frame, 98)
    if hi - lo > 0:
        frame = (frame - lo) / (hi - lo)
    else:
        frame = frame - lo

    np.clip(frame, 0.0, 1.0, out=frame)

    # Gamma curve (< 1 brightens midtones → classic TV snow look)
    np.power(frame, 0.65, out=frame)

    # Per-scanline brightness jitter — mimics CRT horizontal sync wobble
    jitter = np.random.uniform(0.90, 1.10, height).astype(np.float32)
    frame *= jitter[:, np.newaxis]
    np.clip(frame, 0.0, 1.0, out=frame)

    return (frame * 255).astype(np.uint8)

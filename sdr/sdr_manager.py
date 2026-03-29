# sdr/sdr_manager.py
import threading
from collections import deque
import numpy as np
from rtlsdr import RtlSdr
import config
from sdr.demodulator import fm_demodulate, am_demodulate, iq_to_frame


class SdrManager:
    def __init__(self):
        self._sdr: RtlSdr | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._mode: str | None = None
        self._lock = threading.Lock()
        self._frame_buffer: np.ndarray | None = None
        self._audio_buffer: deque = deque(maxlen=30)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, mode: str, frequency_hz: float) -> None:
        """Open SDR device and begin acquisition in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            return  # already running, call stop() first
        self._stop_event.clear()
        self._mode = mode
        self._sdr = RtlSdr()
        self._sdr.sample_rate = {
            'fm': config.FM_SAMPLE_RATE,
            'am': config.AM_SAMPLE_RATE,
            'tv': config.TV_SAMPLE_RATE,
        }[mode]
        self._sdr.center_freq = frequency_hz
        self._sdr.gain = 'auto'
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop acquisition thread and close SDR device."""
        self._stop_event.set()
        # Close device FIRST so read_samples() unblocks and the thread can exit
        if self._sdr is not None:
            self._sdr.close()
            self._sdr = None
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        with self._lock:
            self._frame_buffer = None
            self._audio_buffer.clear()

    def tune(self, frequency_hz: float) -> None:
        if self._sdr is not None:
            self._sdr.center_freq = frequency_hz

    def is_running(self) -> bool:
        return not self._stop_event.is_set()

    def get_frame(self) -> np.ndarray | None:
        """Return latest (TV_FRAME_HEIGHT, TV_FRAME_WIDTH) uint8 frame, or None."""
        with self._lock:
            return self._frame_buffer.copy() if self._frame_buffer is not None else None

    def get_audio_chunk(self) -> np.ndarray | None:
        """Return all buffered audio samples as a flat float32 array, clearing the buffer."""
        with self._lock:
            if not self._audio_buffer:
                return None
            chunk = np.concatenate(self._audio_buffer)
            self._audio_buffer.clear()
            return chunk

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _read_loop(self) -> None:
        read_size = config.SDR_READ_SIZE[self._mode]
        while not self._stop_event.is_set():
            try:
                iq = self._sdr.read_samples(read_size)
                self._process(np.asarray(iq, dtype=np.complex64))
            except Exception:
                self._stop_event.set()
                break

    def _process(self, iq: np.ndarray) -> None:
        if self._mode == 'tv':
            frame = iq_to_frame(iq, config.TV_FRAME_WIDTH, config.TV_FRAME_HEIGHT)
            with self._lock:
                self._frame_buffer = frame

        elif self._mode == 'fm':
            audio = fm_demodulate(iq, config.FM_SAMPLE_RATE, config.AUDIO_RATE)
            with self._lock:
                self._audio_buffer.append(audio)

        elif self._mode == 'am':
            audio = am_demodulate(iq, config.AM_SAMPLE_RATE, config.AUDIO_RATE)
            with self._lock:
                self._audio_buffer.append(audio)

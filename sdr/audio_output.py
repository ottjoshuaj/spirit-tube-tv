import time as _time
import queue
import numpy as np
import sounddevice as sd
import config

# How often to retry opening the audio stream when no device is available
_RETRY_INTERVAL = 3.0


class AudioOutput:
    def __init__(self):
        self._queue: queue.Queue = queue.Queue(maxsize=config.AUDIO_QUEUE_MAX)
        self._leftover: np.ndarray = np.array([], dtype=np.float32)
        self._stream = None
        self._active = False
        self._last_retry: float = 0.0
        self.volume: float = 0.25  # 0.0–1.0, default 25%

    def start(self) -> None:
        self._active = True
        self._open_stream()

    def stop(self) -> None:
        self._active = False
        self._close_stream()
        # Drain queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._leftover = np.array([], dtype=np.float32)

    def push(self, samples: np.ndarray) -> None:
        # If the stream isn't open yet, periodically retry (speaker may have connected)
        if self._stream is None and self._active:
            now = _time.monotonic()
            if now - self._last_retry >= _RETRY_INTERVAL:
                self._last_retry = now
                self._open_stream()
        chunk = samples.astype(np.float32)
        # Short fade-in to avoid clicks at frequency transitions (spirit-box sweep)
        fade_len = min(64, len(chunk))
        if fade_len > 0:
            chunk[:fade_len] *= np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
        try:
            self._queue.put_nowait(chunk)
        except queue.Full:
            pass  # drop this (newest) chunk to avoid blocking the SDR thread

    def _open_stream(self) -> None:
        if self._stream is not None:
            return
        try:
            self._stream = sd.OutputStream(
                samplerate=config.AUDIO_RATE,
                channels=1,
                dtype='float32',
                blocksize=config.AUDIO_BLOCK_SIZE,
                callback=self._callback,
            )
            self._stream.start()
        except sd.PortAudioError:
            self._stream = None

    def _close_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except sd.PortAudioError:
                pass
            self._stream = None

    def _callback(self, outdata: np.ndarray, frames: int, time, status) -> None:
        buf = self._leftover.copy()

        while len(buf) < frames:
            try:
                chunk = self._queue.get_nowait()
                buf = np.concatenate([buf, chunk])
            except queue.Empty:
                silence = np.zeros(frames - len(buf), dtype=np.float32)
                buf = np.concatenate([buf, silence])
                break

        outdata[:, 0] = buf[:frames] * self.volume
        self._leftover = buf[frames:]

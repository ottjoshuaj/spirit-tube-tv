import queue
import numpy as np
import sounddevice as sd
import config


class AudioOutput:
    def __init__(self):
        self._queue: queue.Queue = queue.Queue(maxsize=config.AUDIO_QUEUE_MAX)
        self._leftover: np.ndarray = np.array([], dtype=np.float32)
        self._stream = None

    def start(self) -> None:
        self._stream = sd.OutputStream(
            samplerate=config.AUDIO_RATE,
            channels=1,
            dtype='float32',
            blocksize=config.AUDIO_BLOCK_SIZE,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        # Drain queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._leftover = np.array([], dtype=np.float32)

    def push(self, samples: np.ndarray) -> None:
        try:
            self._queue.put_nowait(samples.astype(np.float32))
        except queue.Full:
            pass  # drop oldest-ish chunk rather than block

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

        outdata[:, 0] = buf[:frames]
        self._leftover = buf[frames:]

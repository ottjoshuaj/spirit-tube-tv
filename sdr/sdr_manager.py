# sdr/sdr_manager.py
"""Process-isolated SDR manager.

The RTL-SDR device runs in a separate subprocess so that librtlsdr C-level
crashes (segfaults from USB disconnects / undervoltage) kill only the worker
— the main pygame app stays alive and auto-respawns the worker.
"""
import multiprocessing as mp
import queue
import sys
import threading
import time
import numpy as np
import config

_RESPAWN_DELAY = 3.0  # seconds before respawning dead worker


# ======================================================================
# Worker — runs in an isolated subprocess
# ======================================================================

def _worker(cmd_q: mp.Queue, audio_q: mp.Queue, frame_q: mp.Queue,
            mode: str, initial_freq: float) -> None:
    from rtlsdr import RtlSdr
    from sdr.demodulator import FmDemodulator, AmDemodulator, iq_to_frame

    sample_rate = {
        'fm': config.FM_SAMPLE_RATE,
        'am': config.AM_SAMPLE_RATE,
        'tv': config.TV_SAMPLE_RATE,
    }[mode]
    read_size = config.SDR_READ_SIZE[mode]

    try:
        sdr = RtlSdr()
        sdr.sample_rate = sample_rate
        sdr.center_freq = initial_freq
        sdr.gain = 'auto'
    except Exception as e:
        print(f'[SDR worker] failed to open device: {e}', file=sys.stderr)
        return

    fm_demod = FmDemodulator(sample_rate, config.AUDIO_RATE) if mode == 'fm' else None
    am_demod = AmDemodulator(sample_rate, config.AUDIO_RATE) if mode == 'am' else None

    while True:
        # Drain command queue (non-blocking)
        try:
            while True:
                cmd = cmd_q.get_nowait()
                if cmd[0] == 'tune':
                    try:
                        sdr.center_freq = cmd[1]
                    except Exception:
                        pass
                elif cmd[0] == 'stop':
                    try:
                        sdr.close()
                    except Exception:
                        pass
                    return
        except queue.Empty:
            pass

        # Read IQ samples
        try:
            iq = np.asarray(sdr.read_samples(read_size), dtype=np.complex64)
        except Exception:
            time.sleep(0.1)
            continue

        # Process
        if mode == 'tv':
            frame = iq_to_frame(iq, config.TV_FRAME_WIDTH, config.TV_FRAME_HEIGHT)
            try:
                # Drop stale frame so we always have the latest
                try:
                    frame_q.get_nowait()
                except queue.Empty:
                    pass
                frame_q.put_nowait(frame)
            except Exception:
                pass

            # TV audio — decimate amplitude to audio rate
            amp = np.abs(iq).astype(np.float32)
            dec = sample_rate // config.AUDIO_RATE
            n_out = len(amp) // dec
            if n_out > 0:
                audio = amp[:n_out * dec].reshape(n_out, dec).mean(axis=1)
                audio -= audio.mean()
                peak = np.max(np.abs(audio))
                if peak > 0:
                    audio = audio / peak * 0.6
                try:
                    audio_q.put_nowait(audio.astype(np.float32))
                except queue.Full:
                    pass

        elif mode == 'fm' and fm_demod is not None:
            audio = fm_demod.process(iq)
            try:
                audio_q.put_nowait(audio)
            except queue.Full:
                pass

        elif mode == 'am' and am_demod is not None:
            audio = am_demod.process(iq)
            try:
                audio_q.put_nowait(audio)
            except queue.Full:
                pass


# ======================================================================
# Manager — runs in the main process
# ======================================================================

class SdrManager:
    def __init__(self):
        self._proc: mp.Process | None = None
        self._cmd_q: mp.Queue | None = None
        self._audio_q: mp.Queue | None = None
        self._frame_q: mp.Queue | None = None
        self._mode: str | None = None
        self._freq: float = 0.0
        self._last_frame: np.ndarray | None = None
        self._monitor: threading.Thread | None = None
        self._active = False

    # ------------------------------------------------------------------
    # Public API (same interface as before)
    # ------------------------------------------------------------------

    def start(self, mode: str, frequency_hz: float) -> bool:
        if self._proc is not None and self._proc.is_alive():
            return True
        self._mode = mode
        self._freq = frequency_hz
        self._active = True
        return self._spawn()

    def stop(self) -> None:
        self._active = False
        if self._cmd_q is not None:
            try:
                self._cmd_q.put_nowait(('stop',))
            except Exception:
                pass
        if self._proc is not None:
            self._proc.join(timeout=3.0)
            if self._proc.is_alive():
                self._proc.kill()
                self._proc.join(timeout=1.0)
            self._proc = None
        self._cmd_q = None
        self._audio_q = None
        self._frame_q = None
        self._last_frame = None

    def tune(self, frequency_hz: float) -> None:
        self._freq = frequency_hz
        if self._cmd_q is not None:
            try:
                self._cmd_q.put_nowait(('tune', frequency_hz))
            except Exception:
                pass

    def is_running(self) -> bool:
        return self._active

    def get_frame(self) -> np.ndarray | None:
        fq = self._frame_q
        if fq is not None:
            try:
                while True:  # drain, keep latest
                    self._last_frame = fq.get_nowait()
            except (queue.Empty, EOFError, OSError):
                pass
        return self._last_frame.copy() if self._last_frame is not None else None

    def get_audio_chunk(self) -> np.ndarray | None:
        aq = self._audio_q
        if aq is None:
            return None
        chunks = []
        try:
            while True:
                chunks.append(aq.get_nowait())
        except (queue.Empty, EOFError, OSError):
            pass
        if not chunks:
            return None
        return np.concatenate(chunks)

    # ------------------------------------------------------------------
    # Subprocess management
    # ------------------------------------------------------------------

    def _spawn(self) -> bool:
        # Fresh queues — old ones may be corrupt from a crashed subprocess
        self._cmd_q = mp.Queue(maxsize=20)
        self._audio_q = mp.Queue(maxsize=30)
        self._frame_q = mp.Queue(maxsize=2)
        self._proc = mp.Process(
            target=_worker,
            args=(self._cmd_q, self._audio_q, self._frame_q,
                  self._mode, self._freq),
            daemon=True,
        )
        self._proc.start()
        # Monitor thread watches the subprocess and respawns on crash
        self._monitor = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor.start()
        return True

    def _monitor_loop(self) -> None:
        """Watch the worker subprocess; respawn if it dies unexpectedly."""
        while self._active:
            time.sleep(1.0)
            if self._proc is not None and not self._proc.is_alive():
                code = self._proc.exitcode
                print(f'[SDR] worker died (exit={code}), '
                      f'respawning in {_RESPAWN_DELAY}s...', file=sys.stderr)
                time.sleep(_RESPAWN_DELAY)
                if self._active:
                    self._spawn()
                return  # new monitor thread started by _spawn

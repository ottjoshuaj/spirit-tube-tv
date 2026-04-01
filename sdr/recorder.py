# sdr/recorder.py
"""Record audio (FM/AM → MP3) and video+audio (TV → AVI) from SDR streams."""
import os
import subprocess
import tempfile
import threading
import time
import wave
import numpy as np
import config

RECORDINGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'recordings')


class AudioRecorder:
    """Records float32 audio chunks to a WAV file, converts to MP3 on stop."""

    def __init__(self, band: str):
        self._band = band
        self._recording = False
        self._wav_path: str | None = None
        self._wav_file: wave.Wave_write | None = None
        self._out_path: str | None = None

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def output_path(self) -> str | None:
        return self._out_path

    def start(self) -> str:
        """Begin recording. Returns the eventual output path."""
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        epoch = int(time.time())
        self._out_path = os.path.join(RECORDINGS_DIR, f'{self._band}_{epoch}.mp3')
        self._wav_path = self._out_path.replace('.mp3', '.wav')
        self._wav_file = wave.open(self._wav_path, 'wb')
        self._wav_file.setnchannels(1)
        self._wav_file.setsampwidth(2)  # 16-bit
        self._wav_file.setframerate(config.AUDIO_RATE)
        self._recording = True
        return self._out_path

    def write(self, samples: np.ndarray) -> None:
        """Write a chunk of float32 audio samples."""
        if not self._recording or self._wav_file is None:
            return
        pcm = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
        self._wav_file.writeframes(pcm.tobytes())

    def stop(self) -> None:
        """Stop recording and convert WAV → MP3 in background."""
        if not self._recording:
            return
        self._recording = False
        if self._wav_file is not None:
            self._wav_file.close()
            self._wav_file = None
        # Convert in background so we don't block the UI
        threading.Thread(target=self._convert, daemon=True).start()

    def _convert(self) -> None:
        if self._wav_path is None or self._out_path is None:
            return
        try:
            subprocess.run(
                ['ffmpeg', '-y', '-i', self._wav_path,
                 '-codec:a', 'libmp3lame', '-b:a', '128k',
                 self._out_path],
                capture_output=True, timeout=300,
            )
        except Exception:
            pass
        # Clean up temp WAV
        try:
            os.remove(self._wav_path)
        except OSError:
            pass


class VideoRecorder:
    """Records TV frames + audio, muxes to AVI on stop via ffmpeg."""

    def __init__(self):
        self._recording = False
        self._out_path: str | None = None
        self._wav_path: str | None = None
        self._wav_file: wave.Wave_write | None = None
        self._raw_dir: str | None = None
        self._frame_count = 0

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def output_path(self) -> str | None:
        return self._out_path

    def start(self) -> str:
        """Begin recording. Returns the eventual output path."""
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        epoch = int(time.time())
        self._out_path = os.path.join(RECORDINGS_DIR, f'tv_{epoch}.avi')
        # Temp dir for raw frames
        self._raw_dir = tempfile.mkdtemp(prefix='spirit_tv_')
        self._frame_count = 0
        # Audio WAV
        self._wav_path = os.path.join(self._raw_dir, 'audio.wav')
        self._wav_file = wave.open(self._wav_path, 'wb')
        self._wav_file.setnchannels(1)
        self._wav_file.setsampwidth(2)
        self._wav_file.setframerate(config.AUDIO_RATE)
        self._recording = True
        return self._out_path

    def write_frame(self, frame: np.ndarray) -> None:
        """Write a grayscale (H, W) uint8 frame."""
        if not self._recording or self._raw_dir is None:
            return
        path = os.path.join(self._raw_dir, f'{self._frame_count:06d}.raw')
        frame.tofile(path)
        self._frame_count += 1

    def write_audio(self, samples: np.ndarray) -> None:
        """Write a chunk of float32 audio samples."""
        if not self._recording or self._wav_file is None:
            return
        pcm = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
        self._wav_file.writeframes(pcm.tobytes())

    def stop(self) -> None:
        """Stop recording and mux frames+audio → AVI in background."""
        if not self._recording:
            return
        self._recording = False
        if self._wav_file is not None:
            self._wav_file.close()
            self._wav_file = None
        threading.Thread(target=self._mux, daemon=True).start()

    def _mux(self) -> None:
        if self._raw_dir is None or self._out_path is None:
            return
        if self._frame_count == 0:
            self._cleanup()
            return

        w = config.TV_FRAME_WIDTH
        h = config.TV_FRAME_HEIGHT
        # Estimate FPS from frame count and audio duration
        try:
            with wave.open(self._wav_path, 'rb') as wf:
                duration = wf.getnframes() / wf.getframerate()
        except Exception:
            duration = self._frame_count / 10.0
        fps = self._frame_count / max(duration, 0.1)

        # Build raw video pipe: concat .raw files → rawvideo stdin
        frame_list = os.path.join(self._raw_dir, 'frames.txt')
        with open(frame_list, 'w') as f:
            for i in range(self._frame_count):
                f.write(os.path.join(self._raw_dir, f'{i:06d}.raw') + '\n')

        # Use ffmpeg: raw grayscale frames + wav audio → AVI
        try:
            subprocess.run(
                ['ffmpeg', '-y',
                 '-f', 'rawvideo', '-pixel_format', 'gray',
                 '-video_size', f'{w}x{h}', '-framerate', f'{fps:.2f}',
                 '-i', f'concat:' + '|'.join(
                     os.path.join(self._raw_dir, f'{i:06d}.raw')
                     for i in range(self._frame_count)),
                 '-i', self._wav_path,
                 '-c:v', 'mjpeg', '-q:v', '5',
                 '-c:a', 'mp3', '-b:a', '128k',
                 '-shortest',
                 self._out_path],
                capture_output=True, timeout=600,
            )
        except Exception:
            pass

        self._cleanup()

    def _cleanup(self) -> None:
        if self._raw_dir is None:
            return
        import shutil
        try:
            shutil.rmtree(self._raw_dir)
        except OSError:
            pass
        self._raw_dir = None

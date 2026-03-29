import numpy as np
import pytest
from unittest.mock import patch, MagicMock

# Patch sounddevice before import so no hardware is needed
with patch.dict('sys.modules', {'sounddevice': MagicMock()}):
    from sdr.audio_output import AudioOutput

def test_push_stores_chunk():
    ao = AudioOutput()
    chunk = np.ones(1024, dtype=np.float32)
    ao.push(chunk)
    assert ao._queue.qsize() == 1

def test_push_drops_when_full():
    ao = AudioOutput()
    for _ in range(15):   # more than AUDIO_QUEUE_MAX=10
        ao.push(np.zeros(512, dtype=np.float32))
    assert ao._queue.qsize() <= 10

def test_callback_fills_output():
    ao = AudioOutput()
    chunk = np.ones(4096, dtype=np.float32) * 0.5
    ao.push(chunk)
    outdata = np.zeros((2048, 1), dtype=np.float32)
    ao._callback(outdata, 2048, None, None)
    assert np.allclose(outdata[:, 0], 0.5)

def test_callback_pads_silence_on_underrun():
    ao = AudioOutput()
    # Queue empty — callback should fill with zeros, not raise
    outdata = np.zeros((2048, 1), dtype=np.float32)
    ao._callback(outdata, 2048, None, None)
    assert np.all(outdata == 0.0)

def test_callback_handles_leftover():
    ao = AudioOutput()
    # Push exactly 1.5x the block size so leftover must carry over
    chunk = np.ones(3072, dtype=np.float32)
    ao.push(chunk)
    outdata1 = np.zeros((2048, 1), dtype=np.float32)
    ao._callback(outdata1, 2048, None, None)
    outdata2 = np.zeros((2048, 1), dtype=np.float32)
    ao._callback(outdata2, 2048, None, None)
    # First block fully from chunk, second block: 1024 ones + 1024 silence
    assert np.all(outdata1[:, 0] == 1.0)
    assert np.all(outdata2[:1024, 0] == 1.0)
    assert np.all(outdata2[1024:, 0] == 0.0)

def test_stop_clears_queue():
    ao = AudioOutput()
    ao.push(np.zeros(512, dtype=np.float32))
    ao.stop()
    assert ao._queue.empty()
    assert len(ao._leftover) == 0

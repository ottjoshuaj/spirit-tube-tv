# tests/test_sdr_manager.py
import time
import numpy as np
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

def _make_mock_sdr(n_samples=65_536):
    mock = MagicMock()
    iq = (np.random.randn(n_samples) + 1j * np.random.randn(n_samples)).astype(np.complex64)
    mock.read_samples.return_value = iq
    return mock

@patch('sdr.sdr_manager.RtlSdr')
def test_start_sets_running(MockRtlSdr):
    MockRtlSdr.return_value = _make_mock_sdr()
    from sdr.sdr_manager import SdrManager
    mgr = SdrManager()
    mgr.start('fm', 98_000_000)
    time.sleep(0.05)
    assert mgr.is_running()
    mgr.stop()

@patch('sdr.sdr_manager.RtlSdr')
def test_stop_halts_thread(MockRtlSdr):
    MockRtlSdr.return_value = _make_mock_sdr()
    from sdr.sdr_manager import SdrManager
    mgr = SdrManager()
    mgr.start('fm', 98_000_000)
    time.sleep(0.05)
    mgr.stop()
    assert not mgr.is_running()
    assert mgr._thread is None or not mgr._thread.is_alive()

@patch('sdr.sdr_manager.RtlSdr')
def test_fm_mode_produces_audio(MockRtlSdr):
    MockRtlSdr.return_value = _make_mock_sdr(65_536)
    from sdr.sdr_manager import SdrManager
    mgr = SdrManager()
    mgr.start('fm', 98_000_000)
    time.sleep(0.1)
    chunk = mgr.get_audio_chunk()
    mgr.stop()
    assert chunk is not None
    assert isinstance(chunk, np.ndarray)
    assert chunk.dtype == np.float32

@patch('sdr.sdr_manager.RtlSdr')
def test_tv_mode_produces_frame(MockRtlSdr):
    MockRtlSdr.return_value = _make_mock_sdr(65_536)
    from sdr.sdr_manager import SdrManager
    mgr = SdrManager()
    mgr.start('tv', 175_250_000)
    time.sleep(0.1)
    frame = mgr.get_frame()
    mgr.stop()
    assert frame is not None
    assert frame.shape == (382, 800)
    assert frame.dtype == np.uint8

@patch('sdr.sdr_manager.RtlSdr')
def test_tune_updates_center_freq(MockRtlSdr):
    mock_sdr = _make_mock_sdr()
    MockRtlSdr.return_value = mock_sdr
    from sdr.sdr_manager import SdrManager
    mgr = SdrManager()
    mgr.start('fm', 98_000_000)
    mgr.tune(104_500_000)
    assert mock_sdr.center_freq == 104_500_000
    mgr.stop()

@patch('sdr.sdr_manager.RtlSdr')
def test_get_audio_chunk_clears_buffer(MockRtlSdr):
    MockRtlSdr.return_value = _make_mock_sdr(65_536)
    from sdr.sdr_manager import SdrManager
    mgr = SdrManager()
    mgr.start('fm', 98_000_000)
    time.sleep(0.1)
    mgr.get_audio_chunk()   # clears buffer
    mgr.stop()              # halt thread before second read
    chunk2 = mgr.get_audio_chunk()
    assert chunk2 is None   # buffer must be empty after stop + first read

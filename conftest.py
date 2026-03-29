# conftest.py — project-level pytest configuration
# Pre-mock hardware libraries so tests can run without physical devices installed.
import sys
from unittest.mock import MagicMock

# Mock rtlsdr (pyrtlsdr) so sdr/sdr_manager.py can be imported without hardware
if 'rtlsdr' not in sys.modules:
    mock_rtlsdr = MagicMock()
    sys.modules['rtlsdr'] = mock_rtlsdr

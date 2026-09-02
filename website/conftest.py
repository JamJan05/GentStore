"""Put the website's own package on the path when pytest runs from this directory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

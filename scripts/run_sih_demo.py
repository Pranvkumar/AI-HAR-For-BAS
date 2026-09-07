"""Launch the current SIH baseline demo directly from a source checkout."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_SOURCE = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(PROJECT_SOURCE))

from har.demo import main


if __name__ == "__main__":
    main()

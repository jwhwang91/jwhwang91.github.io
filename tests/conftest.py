import sys
from pathlib import Path

# Ensure the repo root (which holds the `portfolio/` package and main.py) is
# importable regardless of pytest's import mode / invocation directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

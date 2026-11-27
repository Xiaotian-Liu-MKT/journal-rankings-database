"""Local journal catalogue, reproducible imports and read-only queries."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "journals.sqlite"
DEFAULT_SOURCE_DIR = ROOT / "sources"

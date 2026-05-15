"""flyatlas — local index + CLI + Web UI for the fly-distill phenotype atlas.

Three entry points:
  python -m flyatlas.build      # one-shot ETL: output/genes/*.json → SQLite
  python -m flyatlas.cli ...    # terminal queries
  python -m flyatlas.server     # FastAPI Web UI (academic style)
"""
__version__ = "0.1.0"

from pathlib import Path
DB_PATH = Path(__file__).resolve().parents[1] / "atlas.db"

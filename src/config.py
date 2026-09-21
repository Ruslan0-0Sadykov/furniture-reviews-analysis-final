from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_INTERIM = ROOT / "data" / "interim"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
FIGURES = OUTPUTS / "figures"
TABLES = OUTPUTS / "tables"
METRICS = OUTPUTS / "metrics"
DATALENS = ROOT / "datalens"
REPORT = ROOT / "report"
CACHE = ROOT / "yandex_cache"
RANDOM_SEED = 42
SOURCE_DATE = "2024-04-03"


def ensure_directories() -> None:
    for path in [DATA_RAW, DATA_INTERIM, DATA_PROCESSED, FIGURES, TABLES, METRICS, DATALENS, REPORT, CACHE]:
        path.mkdir(parents=True, exist_ok=True)


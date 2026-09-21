from __future__ import annotations

from pathlib import Path
import pandas as pd

EXPECTED_COLUMNS = [
    "Наименование", "Оценка", "Количество оценок", "Адрес", "Координаты объекта",
    "Количество отзывов", "Автор", "Статус автора", "Оценка автора", "Дата",
    "Текст", "Like", "Dislike",
]


def load_raw_files(raw_dir: Path) -> pd.DataFrame:
    files = sorted(raw_dir.glob("*.xlsx"))
    if not files:
        raise FileNotFoundError(f"В {raw_dir} нет XLSX-файлов")
    frames = []
    for path in files:
        frame = pd.read_excel(path)
        missing = sorted(set(EXPECTED_COLUMNS) - set(frame.columns))
        if missing:
            raise ValueError(f"{path.name}: отсутствуют поля {missing}")
        frame["source"] = path.stem.replace("reviews_", "")
        frame["source_row"] = range(2, len(frame) + 2)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def build_audit(raw_dir: Path) -> dict:
    result = {"files": [], "combined": {}}
    total_rows = 0
    for path in sorted(raw_dir.glob("*.xlsx")):
        df = pd.read_excel(path)
        total_rows += len(df)
        result["files"].append({
            "file": path.name,
            "rows": int(len(df)),
            "columns": int(df.shape[1]),
            "exact_duplicates": int(df.duplicated().sum()),
            "fields": [
                {
                    "column": str(c),
                    "dtype": str(df[c].dtype),
                    "missing": int(df[c].isna().sum()),
                    "missing_share": float(df[c].isna().mean()),
                    "unique": int(df[c].nunique(dropna=True)),
                }
                for c in df.columns
            ],
        })
    result["combined"] = {"rows_before_cleaning": total_rows, "files": len(result["files"])}
    return result


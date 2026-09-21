from __future__ import annotations

import hashlib
import html
import re
import pandas as pd

RENAME = {
    "Наименование": "company", "Оценка": "company_rating_raw",
    "Количество оценок": "company_ratings_count_raw", "Адрес": "address",
    "Координаты объекта": "coordinates", "Количество отзывов": "company_reviews_count",
    "Автор": "author", "Статус автора": "author_status", "Оценка автора": "rating_raw",
    "Дата": "date_raw", "Текст": "text_original", "Like": "likes", "Dislike": "dislikes",
}


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_number(value: object) -> float:
    if pd.isna(value):
        return float("nan")
    match = re.search(r"\d+(?:[,.]\d+)?", str(value).replace("\xa0", " "))
    return float(match.group(0).replace(",", ".")) if match else float("nan")


MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}


def parse_russian_date(value: object, reference: str = "2024-04-03") -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    text = str(value).strip().lower()
    ref = pd.Timestamp(reference)
    absolute = re.search(r"(\d{1,2})\s+([а-яё]+)(?:\s+(\d{4}))?", text)
    if absolute and absolute.group(2) in MONTHS:
        year = int(absolute.group(3)) if absolute.group(3) else ref.year
        return pd.Timestamp(year, MONTHS[absolute.group(2)], int(absolute.group(1)))
    rel = re.search(r"(\d+)\s+(дн|недел|месяц|месяц|год|лет|года)", text)
    if rel:
        n = int(rel.group(1)); unit = rel.group(2)
        if unit.startswith("дн"): return ref - pd.Timedelta(days=n)
        if unit.startswith("недел"): return ref - pd.Timedelta(weeks=n)
        if unit.startswith("месяц"): return ref - pd.DateOffset(months=n)
        return ref - pd.DateOffset(years=n)
    if "неделю назад" in text: return ref - pd.Timedelta(weeks=1)
    if "месяц назад" in text: return ref - pd.DateOffset(months=1)
    if "год назад" in text: return ref - pd.DateOffset(years=1)
    return pd.NaT


def preprocess(raw: pd.DataFrame, reference_date: str) -> tuple[pd.DataFrame, dict]:
    df = raw.rename(columns=RENAME).copy()
    before = len(df)
    df["rating"] = df["rating_raw"].map(parse_number)
    df["company_rating"] = df["company_rating_raw"].map(parse_number)
    df["text_original"] = df["text_original"].fillna("").astype(str)
    df["text"] = df["text_original"].map(normalize_text)
    df["review_date"] = df["date_raw"].map(lambda x: parse_russian_date(x, reference_date))
    df = df[(df["rating"].notna()) | (df["text"].str.len() > 0)].copy()
    blank_rows_removed = before - len(df)
    exact_dupes = int(df.duplicated(subset=["source", "company", "author", "date_raw", "text", "rating"], keep="first").sum())
    df = df.drop_duplicates(subset=["source", "company", "author", "date_raw", "text", "rating"], keep="first")
    df["review_id"] = df.apply(lambda r: hashlib.sha1(
        f"{r['source']}|{r.get('company','')}|{r.get('author','')}|{r.get('date_raw','')}|{r['text']}".encode("utf-8")
    ).hexdigest()[:16], axis=1)
    df["sentiment"] = pd.cut(df["rating"], bins=[-float("inf"), 2, 3, float("inf")], labels=["negative", "neutral", "positive"]).astype("string")
    df.loc[df["rating"].isna(), "sentiment"] = "unknown"
    audit = {
        "rows_loaded": before, "blank_or_nonreview_rows_removed": blank_rows_removed,
        "exact_duplicates_removed": exact_dupes, "rows_processed": int(len(df)),
        "text_nonempty": int((df["text"].str.len() > 0).sum()), "rating_nonmissing": int(df["rating"].notna().sum()),
    }
    return df.reset_index(drop=True), audit


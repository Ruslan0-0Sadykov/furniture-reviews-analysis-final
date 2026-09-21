"""Build external-safe aggregate exports from local review-level artifacts.

The source files stay local and are ignored by Git.  This script deliberately
does not export review text, author/profile fields, company/address fields, or
stable review identifiers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DATASET = ROOT / "data" / "processed" / "reviews_enriched.csv"
PRIVATE_HYPOTHESES = ROOT / "outputs" / "metrics" / "hypotheses.json"
PUBLIC_DATALENS = ROOT / "datalens" / "datalens_dataset_public.csv"
PUBLIC_DIR = ROOT / "outputs" / "public"


def build_public_datalens() -> None:
    reviews = pd.read_csv(PRIVATE_DATASET, low_memory=False)
    # Keep the public grain coarse enough to prevent reconstruction of a
    # specific review by combining a date, rating, category and platform.
    dimensions = ["source", "rating", "sentiment"]
    for column in dimensions:
        reviews[column] = reviews[column].fillna("unknown")

    flags = [
        "service_issue",
        "product_quality_issue",
        "delivery_mentioned",
        "return_or_claim",
    ]
    for column in flags:
        reviews[column] = reviews[column].fillna(False).astype(bool).astype(int)

    for value in ("fast", "normal", "slow"):
        reviews[f"delivery_{value}"] = (reviews["delivery_speed"] == value).astype(int)
    for value in ("soft", "cabinet", "other", "unknown"):
        reviews[f"furniture_{value}"] = (reviews["furniture_group"] == value).astype(int)
    reviews["classified_by_yandexgpt"] = (
        reviews["classification_basis"] == "yandexgpt"
    ).astype(int)
    public = (
        reviews.groupby(dimensions, dropna=False, observed=True)
        .agg(
            review_count=("rating", "size"),
            avg_word_count=("word_count", "mean"),
            avg_sentence_count=("sentence_count", "mean"),
            avg_emotion_intensity=("emotion_intensity", "mean"),
            service_issue_count=("service_issue", "sum"),
            product_quality_issue_count=("product_quality_issue", "sum"),
            delivery_mentioned_count=("delivery_mentioned", "sum"),
            return_or_claim_count=("return_or_claim", "sum"),
            delivery_fast_count=("delivery_fast", "sum"),
            delivery_normal_count=("delivery_normal", "sum"),
            delivery_slow_count=("delivery_slow", "sum"),
            furniture_soft_count=("furniture_soft", "sum"),
            furniture_cabinet_count=("furniture_cabinet", "sum"),
            furniture_other_count=("furniture_other", "sum"),
            furniture_unknown_count=("furniture_unknown", "sum"),
            yandexgpt_count=("classified_by_yandexgpt", "sum"),
        )
        .reset_index()
        .sort_values(dimensions, kind="stable")
    )
    PUBLIC_DATALENS.parent.mkdir(parents=True, exist_ok=True)
    public.to_csv(PUBLIC_DATALENS, index=False, encoding="utf-8-sig")


def build_public_hypotheses() -> None:
    raw = json.loads(PRIVATE_HYPOTHESES.read_text(encoding="utf-8"))
    summary = [
        {
            "hypothesis": item["hypothesis"],
            "n": item["n"],
            "verdict": item["verdict"],
            "p_value": item["p_value"],
            "adjusted_p_value": item.get("adjusted_p_value"),
            "effect_size": item["effect_size"],
            "test": item["test"],
            "limitations": item["limitations"],
        }
        for item in raw
    ]
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary).to_csv(
        PUBLIC_DIR / "hypotheses_summary.csv", index=False, encoding="utf-8-sig"
    )
    (PUBLIC_DIR / "hypotheses_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    build_public_datalens()
    build_public_hypotheses()

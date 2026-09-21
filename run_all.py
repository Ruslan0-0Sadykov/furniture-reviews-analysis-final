from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import *
from src.data_loading import load_raw_files, build_audit
from src.preprocessing import preprocess
from src.features import extract_features
from src.hypotheses import evaluate_all, save_results
from src.visualization import create_figures
from src.report import create_report
from src.yandex_gpt import YandexGPTClient


def apply_limited_llm(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    limit = max(0, int(os.getenv("YANDEX_GPT_MAX_REVIEWS", "0")))
    client = YandexGPTClient(CACHE)
    stats = {"enabled": client.enabled, "requested_limit": limit, "attempted": 0, "successful": 0}
    historic_403 = client.error_log.exists() and '"http_status": 403' in client.error_log.read_text(encoding="utf-8", errors="ignore")
    if not client.enabled:
        stats["blocked_reason"] = "YandexGPT credentials are not configured"
        return df, stats
    if limit == 0:
        if historic_403:
            stats["blocked_reason"] = "Historical Yandex Cloud API response: HTTP 403 PermissionDenied"
        return df, stats
    candidates = df[(df.text.str.len().between(40, 2500)) & ((df.rating <= 3) | (df.delivery_mentioned) | (df.return_or_claim))].copy()
    if candidates.empty:
        return df, stats
    sample = (candidates.groupby(["source", "sentiment"], group_keys=False, observed=True)
              .apply(lambda x: x.sample(min(len(x), max(1, limit // max(1, candidates.groupby(["source", "sentiment"], observed=True).ngroups))), random_state=RANDOM_SEED), include_groups=False)
              .head(limit))
    stats["strata"] = int(candidates.groupby(["source", "sentiment"], observed=True).ngroups)
    bool_fields = ["service_issue", "product_quality_issue", "delivery_mentioned", "return_or_claim"]
    text_fields = ["delivery_speed", "return_reason", "product_type", "furniture_group"]
    for idx, row in sample.iterrows():
        stats["attempted"] += 1
        label = client.classify(row.review_id, row.text)
        if label is None:
            continue
        stats["successful"] += 1
        data = label.model_dump()
        for field in bool_fields + text_fields + ["emotion_intensity", "aspects_count", "confidence"]:
            df.at[idx, field] = data[field]
        df.at[idx, "topics"] = "|".join(data["topics"])
        df.at[idx, "complaint_categories"] = "|".join(data["complaint_categories"])
        df.at[idx, "classification_basis"] = "yandexgpt_auto"
    stats["cache_hits"] = client.cache_hits
    stats["network_successful"] = stats["successful"] - client.cache_hits
    stats["status"] = "completed" if stats["successful"] else "failed"
    if not stats["successful"] and historic_403:
        stats["blocked_reason"] = "Yandex Cloud API returned HTTP 403 PermissionDenied"
    return df, stats


def classification_audit(df: pd.DataFrame) -> pd.DataFrame:
    parts=[]
    for sentiment,group in df.groupby("sentiment",observed=True):
        parts.append(group.sample(min(40,len(group)),random_state=RANDOM_SEED))
    sample=pd.concat(parts).drop_duplicates("review_id").head(160)
    cols=["review_id","text_original","source","rating","sentiment","topics","complaint_categories","service_issue","product_quality_issue","delivery_mentioned","delivery_speed","return_or_claim","return_reason","product_type","furniture_group","emotion_intensity","aspects_count","confidence","classification_basis"]
    return sample[cols]


def data_dictionary(df: pd.DataFrame) -> pd.DataFrame:
    descriptions={
        "review_id":"Стабильный идентификатор отзыва", "source":"Источник", "company":"Название организации",
        "rating":"Оценка автора от 1 до 5", "review_date":"Дата отзыва, если распознана", "text":"Очищенный текст",
        "sentiment":"Тональность по рейтингу", "service_issue":"Признак сервисной проблемы", "product_quality_issue":"Признак проблемы качества",
        "delivery_speed":"Явная оценка скорости доставки", "return_or_claim":"Возврат, обмен, претензия или рекламация",
        "return_reason":"Причины возврата или претензии через |", "furniture_group":"soft, cabinet, other или unknown",
        "price_rub":"Явно упомянутая сумма в рублях", "word_count":"Количество слов", "emotion_intensity":"Индекс эмоциональности 0–1",
        "detail_score":"Индекс подробности для записей с ценой", "classification_basis":"Источник автоматической классификации",
    }
    return pd.DataFrame([{"field":c,"dtype":str(df[c].dtype),"description":descriptions.get(c,"Техническое или исходное поле"),"missing":int(df[c].isna().sum())} for c in df.columns])


def save_tables(df, results, h5data):
    summary=pd.DataFrame([{"hypothesis":r["hypothesis"],"n":r["n"],"verdict":r["verdict"],"p_value":r.get("p_value"),"adjusted_p_value":r.get("adjusted_p_value"),"effect_size":r.get("effect_size"),"limitations":r["limitations"]} for r in results])
    summary.to_csv(TABLES/"hypotheses_summary.csv",index=False,encoding="utf-8-sig")
    classification_audit(df).to_csv(TABLES/"classification_audit.csv",index=False,encoding="utf-8-sig")
    data_dictionary(df).to_csv(DATALENS/"data_dictionary.csv",index=False,encoding="utf-8-sig")
    h5data.to_csv(TABLES/"h5_price_records.csv",index=False,encoding="utf-8-sig")


def build_datalens(df):
    cols=["review_id","source","company","address","rating","review_date","sentiment","word_count","sentence_count","unique_words","emotion_intensity","service_issue","product_quality_issue","delivery_mentioned","delivery_speed","return_or_claim","return_reason","product_type","furniture_group","price_rub","aspects_count","classification_basis"]
    out=df[cols].copy(); out["review_date"]=out.review_date.dt.strftime("%Y-%m-%d"); out.to_csv(DATALENS/"datalens_dataset.csv",index=False,encoding="utf-8-sig")


def maybe_build_workbooks():
    if os.getenv("BUILD_XLSX") != "1":
        return
    node=os.getenv("CODEX_NODE") or shutil.which("node")
    if not node:
        raise RuntimeError("Для XLSX требуется Node.js с @oai/artifact-tool")
    subprocess.run([node,str(ROOT/"tools"/"build_workbooks.mjs")],check=True,cwd=ROOT)


def main():
    np.random.seed(RANDOM_SEED); ensure_directories()
    raw_audit=build_audit(DATA_RAW); raw=load_raw_files(DATA_RAW); clean,prep=preprocess(raw,SOURCE_DATE); enriched=extract_features(clean); enriched,llm_stats=apply_limited_llm(enriched)
    results,h5data=evaluate_all(enriched)
    enriched.to_csv(DATA_PROCESSED/"reviews_enriched.csv",index=False,encoding="utf-8-sig")
    clean.to_csv(DATA_PROCESSED/"reviews_processed.csv",index=False,encoding="utf-8-sig")
    audit={"raw":raw_audit,"preprocessing":prep,"llm":llm_stats}; (METRICS/"data_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    save_results(results,METRICS/"hypotheses.json"); save_tables(enriched,results,h5data); build_datalens(enriched)
    figures=create_figures(enriched,results,h5data,FIGURES)
    create_report(enriched,audit,results,figures,REPORT/"Аналитический_отчет_по_отзывам_мебели.docx")
    maybe_build_workbooks()
    print(json.dumps({"rows":len(enriched),"llm":llm_stats,"verdicts":{r['hypothesis']:r['verdict'] for r in results}},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()

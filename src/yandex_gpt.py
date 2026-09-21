from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Literal
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ReviewLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentiment: Literal["negative", "neutral", "positive"]
    sentiment_score: float = Field(ge=-1, le=1, description="Negative values for negative sentiment, 0 for neutral, positive values for positive sentiment")
    topics: list[str]
    complaint_categories: list[str]
    service_issue: bool
    product_quality_issue: bool
    delivery_mentioned: bool
    delivery_speed: Literal["fast", "normal", "slow", "unknown"]
    return_or_claim: bool
    return_reason: str
    product_type: str
    furniture_group: Literal["soft", "cabinet", "other", "unknown"]
    emotion_intensity: float = Field(ge=0, le=1)
    aspects_count: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)


SYSTEM_PROMPT = """Ты классифицируешь русскоязычные отзывы о мебельных магазинах. Верни только JSON, строго соответствующий переданной JSON Schema, без Markdown и пояснений. Не додумывай факты. sentiment: negative, neutral или positive; sentiment_score должен быть отрицательным для negative, равен 0 для neutral и положительным для positive. delivery_speed: fast только при явно быстрой доставке, normal при явно соблюденном обычном сроке, slow при задержке, иначе unknown. furniture_group: soft, cabinet, other или unknown. return_reason и product_type всегда строки; используй пустую строку, если значения нет. topics и complaint_categories всегда массивы строк, допускается пустой массив. emotion_intensity и confidence — числа от 0 до 1; aspects_count — число явно упомянутых аспектов, целое и неотрицательное. Автоматическая классификация не является ручной разметкой."""

CLASSIFIER_VERSION = "v2-json-schema"


def redact_pii(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-zА-Яа-я]{2,}", "[EMAIL]", text)
    text = re.sub(r"(?:\+7|8)[\s()\-]*\d{3}[\s()\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}", "[PHONE]", text)
    return text


def parse_json_response(text: str) -> ReviewLabel:
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start: raise ValueError("JSON object not found")
    return ReviewLabel.model_validate(json.loads(cleaned[start:end+1]))


class YandexGPTClient:
    def __init__(self, cache_dir: Path):
        load_dotenv()
        self.api_key=os.getenv("YANDEX_API_KEY")
        self.folder_id=os.getenv("YANDEX_FOLDER_ID")
        self.model=os.getenv("YANDEX_GPT_MODEL","yandexgpt-lite")
        self.cache_dir=cache_dir; cache_dir.mkdir(parents=True,exist_ok=True)
        self.error_log=cache_dir/"errors.jsonl"
        self.cache_hits=0

    @property
    def enabled(self): return bool(self.api_key and self.folder_id)

    def classify(self, review_id: str, text: str, retries: int=3) -> ReviewLabel | None:
        safe=redact_pii(text)[:5000]; key=hashlib.sha256((CLASSIFIER_VERSION+self.model+review_id+safe).encode()).hexdigest(); path=self.cache_dir/f"{key}.json"
        if path.exists():
            self.cache_hits += 1
            return ReviewLabel.model_validate_json(path.read_text(encoding="utf-8"))
        if not self.enabled: return None
        payload={"modelUri":f"gpt://{self.folder_id}/{self.model}","completionOptions":{"stream":False,"temperature":0,"maxTokens":"1200"},"messages":[{"role":"system","text":SYSTEM_PROMPT},{"role":"user","text":safe}],"jsonSchema":{"schema":ReviewLabel.model_json_schema()}}
        headers={"Authorization":f"Api-Key {self.api_key}","Content-Type":"application/json"}
        for attempt in range(retries):
            try:
                response=requests.post("https://ai.api.cloud.yandex.net/foundationModels/v1/completion",headers=headers,json=payload,timeout=45)
                if response.status_code == 400 and "does not match with service account folder ID" in response.text:
                    match = re.search(r"service account folder ID '([^']+)'", response.text)
                    if match:
                        self.folder_id = match.group(1)
                        payload["modelUri"] = f"gpt://{self.folder_id}/{self.model}"
                        continue
                response.raise_for_status(); raw=response.json()["result"]["alternatives"][0]["message"]["text"]
                label=parse_json_response(raw); path.write_text(label.model_dump_json(indent=2),encoding="utf-8"); return label
            except (requests.RequestException,KeyError,ValueError,ValidationError) as exc:
                response = getattr(exc, "response", None)
                status = getattr(response, "status_code", None)
                with self.error_log.open("a",encoding="utf-8") as f: f.write(json.dumps({"review_id":review_id,"attempt":attempt+1,"error":type(exc).__name__,"http_status":status},ensure_ascii=False)+"\n")
                if attempt+1<retries: time.sleep(2**attempt)
        return None

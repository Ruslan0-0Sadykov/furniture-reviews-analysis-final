from __future__ import annotations

import math
import re
import pandas as pd

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")

SERVICE = ["менеджер", "консультант", "персонал", "продавец", "обслужив", "сервис", "поддержк", "гарант", "хам", "груб", "оператор", "дозвон", "салон", "магазин", "сборщик", "сборк", "достав", "курьер"]
QUALITY = ["качеств", "материал", "брак", "дефект", "слом", "полом", "трещ", "царап", "фурнитур", "покрыт", "прочност", "шов", "пружин", "механизм", "скрип", "развал"]
POSITIVE = ["хорош", "отлич", "прекрас", "доволь", "рекоменд", "понрав", "супер", "спасибо", "качествен"]
NEGATIVE = ["плох", "ужас", "отврат", "кошмар", "недоволь", "не рекоменд", "обман", "проблем", "претенз"]
INTENSIFIERS = ["очень", "крайне", "ужасно", "супер", "безумно", "совсем", "абсолютно", "реально", "отвратительно", "восторг"]
SOFT = {"sofa": ["диван"], "armchair": ["кресл"], "ottoman": ["пуф", "банкетк"], "soft_bed": ["мягк", "тахт"]}
CABINET = {"wardrobe": ["шкаф", "гардероб"], "dresser": ["комод"], "cabinet": ["тумб"], "shelving": ["стеллаж", "полк"], "wall_unit": ["стенк"], "kitchen": ["кухн", "кухон"], "table": ["стол"], "bed": ["кроват"]}


def contains_any(text: str, stems: list[str]) -> bool:
    return any(stem in text for stem in stems)


def extract_price(text: str) -> float:
    candidates = []
    for m in re.finditer(r"(?<!\d)(\d{1,3}(?:[\s\u00a0]\d{3})+|\d{3,7})(?:[,.]\d+)?\s*(₽|руб(?:л(?:ей|я|ь)?)?)", text, re.I):
        value = float(re.sub(r"[\s\u00a0]", "", m.group(1)).replace(",", "."))
        if 500 <= value <= 5_000_000: candidates.append(value)
    for m in re.finditer(r"(?<!\d)(\d+(?:[,.]\d+)?)\s*(тыс(?:яч[аи]?)?)(?:\s*руб)?", text, re.I):
        value = float(m.group(1).replace(",", ".")) * 1000
        if 500 <= value <= 5_000_000: candidates.append(value)
    return min(candidates) if candidates else float("nan")


def classify_product(text: str) -> tuple[str, str]:
    soft_hits = [(kind, sum(text.count(k) for k in keys)) for kind, keys in SOFT.items()]
    cabinet_hits = [(kind, sum(text.count(k) for k in keys)) for kind, keys in CABINET.items()]
    s_kind, s_count = max(soft_hits, key=lambda x: x[1])
    c_kind, c_count = max(cabinet_hits, key=lambda x: x[1])
    if s_count > 0 and c_count == 0: return s_kind, "soft"
    if c_count > 0 and s_count == 0: return c_kind, "cabinet"
    if s_count > c_count: return s_kind, "soft"
    if c_count > s_count: return c_kind, "cabinet"
    return "unknown", "unknown"


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    records = []
    for text_original, text_norm, rating in zip(out["text_original"], out["text"], out["rating"]):
        low = text_norm.lower().replace("ё", "е")
        tokens = TOKEN_RE.findall(low)
        product_type, group = classify_product(low)
        service = contains_any(low, SERVICE)
        quality = contains_any(low, QUALITY)
        delivery = "достав" in low or "привез" in low or "курьер" in low
        if delivery and re.search(r"\b(быстро|оперативно|раньше|за день|на следующий день)\b", low): speed = "fast"
        elif delivery and re.search(r"(вовремя|точно в срок|как обещал|по сроку|в назначенн)", low): speed = "normal"
        elif delivery and re.search(r"(долго|задерж|просроч|опозд|не привез|ждал|ждали|месяц|недел)", low): speed = "slow"
        else: speed = "unknown"
        claim = bool(re.search(r"(возврат|вернут|вернуть|обмен|претенз|рекламац|деньги назад|суд)", low))
        reasons = []
        if re.search(r"(не соответств.{0,20}(описан|фото|заявлен)|не как на фото|другой товар)", low): reasons.append("mismatch_description")
        if contains_any(low, QUALITY): reasons.append("quality_defect")
        if re.search(r"(поврежд|царап|скол|разбит|порван)", low): reasons.append("damage")
        if re.search(r"(не тот товар|перепутал|чужой товар|другая модель)", low): reasons.append("wrong_item")
        if re.search(r"(не комплект|некомплект|не хват|отсутствовал).{0,30}(детал|элемент|фурнитур|част)", low): reasons.append("incomplete_set")
        if re.search(r"(размер|габарит).{0,30}(не подош|не совп|друг)", low): reasons.append("dimensions")
        if re.search(r"(цвет|оттенок).{0,30}(не совп|друг|не соответств)", low): reasons.append("color")
        if delivery and speed == "slow": reasons.append("delivery")
        if re.search(r"(сборк|собрал|собирал).{0,30}(плох|ужас|ошиб|крив|проблем)", low): reasons.append("assembly")
        reasons = list(dict.fromkeys(reasons))
        if claim and not reasons: reasons = ["other"]
        exclam = str(text_original).count("!")
        emojis = len(EMOJI_RE.findall(str(text_original)))
        intens = sum(low.count(x) for x in INTENSIFIERS)
        caps = sum(1 for c in str(text_original) if c.isupper()) / max(1, sum(1 for c in str(text_original) if c.isalpha()))
        rating_intensity = abs(float(rating) - 3) / 2 if pd.notna(rating) else 0
        emotion = min(1.0, 0.30 * min(exclam, 4) / 4 + 0.20 * min(emojis, 3) / 3 + 0.20 * min(intens, 4) / 4 + 0.10 * min(caps, .3) / .3 + 0.20 * rating_intensity)
        price = extract_price(low)
        aspects = sum([service, quality, delivery, claim, pd.notna(price), group != "unknown", "сборк" in low, "цен" in low])
        sentences = [x for x in re.split(r"[.!?]+", text_norm) if x.strip()]
        topics = []
        if service: topics.append("service")
        if quality: topics.append("product_quality")
        if delivery: topics.append("delivery")
        if claim: topics.append("return_or_claim")
        if "цен" in low or pd.notna(price): topics.append("price")
        records.append({
            "word_count": len(tokens), "char_count": len(text_norm), "sentence_count": len(sentences),
            "unique_words": len(set(tokens)), "exclamation_count": exclam, "emoji_count": emojis,
            "intensifier_count": intens, "emotion_intensity": emotion, "sentiment_score": (float(rating)-3)/2 if pd.notna(rating) else 0,
            "service_issue": service and (rating <= 3 if pd.notna(rating) else contains_any(low, NEGATIVE)),
            "product_quality_issue": quality and (rating <= 3 if pd.notna(rating) else contains_any(low, NEGATIVE)),
            "delivery_mentioned": delivery, "delivery_speed": speed, "return_or_claim": claim,
            "return_reason": "|".join(reasons), "complaint_categories": "|".join(reasons),
            "product_type": product_type, "furniture_group": group, "price_rub": price,
            "aspects_count": aspects, "topics": "|".join(topics), "classification_basis": "rules_v1", "confidence": 0.75,
        })
    features = pd.DataFrame(records, index=out.index)
    return pd.concat([out, features], axis=1)


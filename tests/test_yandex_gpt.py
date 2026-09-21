import pytest
from src.yandex_gpt import ReviewLabel, parse_json_response, redact_pii


def test_json_parser_and_redaction():
    raw='''```json\n{"sentiment":"positive","sentiment_score":0.8,"topics":[],"complaint_categories":[],"service_issue":false,"product_quality_issue":false,"delivery_mentioned":false,"delivery_speed":"unknown","return_or_claim":false,"return_reason":"","product_type":"unknown","furniture_group":"unknown","emotion_intensity":0.4,"aspects_count":1,"confidence":0.9}\n```'''
    assert parse_json_response(raw).confidence==.9
    assert "[PHONE]" in redact_pii("Позвоните +7 (999) 123-45-67")


def test_json_parser_rejects_invalid():
    with pytest.raises(Exception): parse_json_response("not json")


def test_json_schema_has_strict_enums():
    schema = ReviewLabel.model_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["properties"]["delivery_speed"]["enum"] == ["fast", "normal", "slow", "unknown"]

"""Pipeline validation: check if product/order data has required keys for pipeline execution."""

from __future__ import annotations

from typing import Any

PIPELINE_REQUIRED_KEYS = ["place_url"]

PIPELINE_OPTIONAL_KEYS = [
    "campaign_type",
    "daily_limit",
    "total_limit",
    "duration_days",
    "target_count",
    "max_rank",
    "min_rank",
    "name_keyword_ratio",
]


def _extract_field_names(form_schema: list | dict | None) -> set[str]:
    """Extract field names from form_schema (supports both old and new formats)."""
    if form_schema is None:
        return set()

    names: set[str] = set()
    if isinstance(form_schema, list):
        for field in form_schema:
            if isinstance(field, dict):
                names.add(field.get("name", field.get("key", "")))
    elif isinstance(form_schema, dict):
        for field in form_schema.get("fields", []):
            if isinstance(field, dict):
                names.add(field.get("name", field.get("key", "")))
            elif isinstance(field, str):
                names.add(field)
    return names


def validate_schema_for_pipeline(form_schema: list | dict | None) -> list[str]:
    """Check if form_schema fields contain required/optional pipeline keys. Return warnings."""
    warnings: list[str] = []
    field_names = _extract_field_names(form_schema)

    if not field_names:
        warnings.append("폼 스키마가 비어 있어 파이프라인 자동 입력을 수행할 수 없습니다.")
        return warnings

    for key in PIPELINE_REQUIRED_KEYS:
        if key not in field_names:
            warnings.append(f"폼 스키마에 필수 파이프라인 필드 '{key}'가 없습니다.")

    missing_optional = [k for k in PIPELINE_OPTIONAL_KEYS if k not in field_names]
    if missing_optional:
        warnings.append(
            f"선택 파이프라인 필드가 누락되었습니다: {', '.join(missing_optional)}. "
            "기본값으로 진행합니다."
        )

    return warnings


def validate_item_data_for_pipeline(item_data: dict | None) -> list[str]:
    """Check if item_data has required/optional pipeline keys. Return warnings."""
    warnings: list[str] = []

    if not item_data or not isinstance(item_data, dict):
        warnings.append("item_data가 비어 있어 파이프라인 입력값이 없습니다.")
        return warnings

    for key in PIPELINE_REQUIRED_KEYS:
        if key not in item_data or not item_data[key]:
            warnings.append(f"item_data에 필수 파이프라인 필드 '{key}'가 없습니다.")

    missing_optional = [
        k for k in PIPELINE_OPTIONAL_KEYS
        if k not in item_data or item_data[k] is None
    ]
    if missing_optional:
        warnings.append(
            f"item_data에서 선택 파이프라인 필드가 누락되었습니다: {', '.join(missing_optional)}. "
            "기본값으로 진행합니다."
        )

    return warnings

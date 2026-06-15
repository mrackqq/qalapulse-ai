from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import replace
from datetime import datetime
from typing import Any

from app.schemas import CATEGORIES, DISTRICTS
from app.services.ai_analyzer import AnalysisResult, analyze_issue, risk_from_score


def analyze_issue_mvp(
    text: str,
    latitude: float | None = None,
    longitude: float | None = None,
    image_path: str | None = None,
    created_at: datetime | None = None,
    category_hint: str | None = None,
) -> AnalysisResult:
    fallback = analyze_issue(
        text=text,
        latitude=latitude,
        longitude=longitude,
        image_path=image_path,
        created_at=created_at,
        category_hint=category_hint,
    )
    if os.getenv("ENABLE_LLM", "false").lower() not in {"1", "true", "yes"}:
        return fallback

    try:
        payload = _call_llm(text=text, latitude=latitude, longitude=longitude, category_hint=category_hint)
        if not payload:
            return fallback
        category = payload.get("category") if payload.get("category") in CATEGORIES else fallback.category
        district = payload.get("district") if payload.get("district") in DISTRICTS else fallback.district
        priority = _clamp_int(payload.get("priority_score"), fallback.priority_score)
        confidence = _clamp_int(payload.get("confidence"), fallback.confidence, low=30, high=98)
        tags = payload.get("tags") if isinstance(payload.get("tags"), list) else fallback.tags
        summary = str(payload.get("summary") or fallback.summary)[:220]
        explanation = str(payload.get("explanation") or fallback.explanation)
        mode = payload.get("provider") or _provider_name()
        return replace(
            fallback,
            category=category,
            district=district,
            priority_score=priority,
            risk_level=risk_from_score(priority),
            confidence=confidence,
            summary=summary,
            explanation=f"{explanation} AI mode: {mode}.",
            tags=list(dict.fromkeys([str(tag)[:40] for tag in tags])),
            mode=str(mode),
        )
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
        return fallback


def _call_llm(
    text: str,
    latitude: float | None,
    longitude: float | None,
    category_hint: str | None,
) -> dict[str, Any] | None:
    openai_key = os.getenv("OPENAI_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if openai_key:
        return _chat_completion(
            url="https://api.openai.com/v1/chat/completions",
            api_key=openai_key,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            provider="openai",
            text=text,
            latitude=latitude,
            longitude=longitude,
            category_hint=category_hint,
        )
    if deepseek_key:
        return _chat_completion(
            url="https://api.deepseek.com/chat/completions",
            api_key=deepseek_key,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            provider="deepseek",
            text=text,
            latitude=latitude,
            longitude=longitude,
            category_hint=category_hint,
        )
    return None


def _chat_completion(
    url: str,
    api_key: str,
    model: str,
    provider: str,
    text: str,
    latitude: float | None,
    longitude: float | None,
    category_hint: str | None,
) -> dict[str, Any] | None:
    system = (
        "You classify Astana city citizen reports. Return only compact JSON with keys: "
        "category, district, priority_score, risk_level, confidence, summary, explanation, tags."
    )
    user = {
        "text": text,
        "latitude": latitude,
        "longitude": longitude,
        "category_hint": category_hint,
        "allowed_categories": CATEGORIES,
        "allowed_districts": DISTRICTS,
        "priority_formula": "0-100, higher for safety, pedestrian risk, flooding, utilities, night risk, duplicates.",
    }
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        raw = json.loads(response.read().decode("utf-8"))
    content = raw["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    parsed["provider"] = provider
    return parsed


def _provider_name() -> str:
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("DEEPSEEK_API_KEY"):
        return "deepseek"
    return "rule_based"


def _clamp_int(value: Any, fallback: int, low: int = 0, high: int = 100) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return fallback

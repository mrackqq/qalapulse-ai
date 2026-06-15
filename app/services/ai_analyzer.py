from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from app.schemas import CATEGORIES


BASE_SCORES = {
    "safety": 70,
    "flooding": 65,
    "snow_ice": 60,
    "utilities": 60,
    "lighting": 55,
    "transport": 55,
    "roads": 50,
    "smell_ecology": 50,
    "playground": 45,
    "trash": 35,
    "other": 30,
}

CATEGORY_KEYWORDS = {
    "transport": ["автобус", "останов", "пробк", "транспорт", "маршрут", "bus", "traffic", "парков"],
    "roads": ["яма", "дорог", "асфальт", "тротуар", "бордюр", "разметк", "переход", "road"],
    "lighting": ["фонар", "освещ", "свет", "темно", "темн", "lamp", "lighting"],
    "flooding": ["затоп", "ливнев", "луж", "дожд", "вода", "потоп", "канализац", "flood"],
    "snow_ice": ["снег", "голол", "лед", "лёд", "мороз", "скольз", "сугроб", "winter"],
    "trash": ["мусор", "контейнер", "свалк", "отход", "урн", "trash", "garbage"],
    "smell_ecology": ["запах", "вон", "воздух", "дым", "смог", "эколог", "выброс", "канализац"],
    "playground": ["детская площад", "площадк", "качел", "горк", "спорт", "playground"],
    "safety": ["опас", "драка", "краж", "напад", "авар", "дтп", "травм", "security", "safe"],
    "utilities": ["вода", "отоплен", "электр", "свет отключ", "канализац", "лифт", "тепло", "жкх", "utility"],
}

DISTRICT_KEYWORDS = {
    "Esil": ["mega", "silk way", "экспо", "expo", "кабанбай", "мангилик", "мәңгілік", "ботан", "сығанак", "сығанақ", "достык", "достық", "улы дала", "ұлы дала"],
    "Nura": ["туран", "нура", "қорғалжын", "коргалжын"],
    "Almaty": ["абылай", "тауелсыздык", "тәуелсіздік", "жумабаева", "момышулы", "аль-фараби"],
    "Saryarka": ["сарыарка", "кенесары", "республика", "женис", "жеңіс"],
    "Baikonur": ["байконур", "бейбитшилик", "бейбітшілік", "сейфуллин", "пушкина", "бараева", "богенбай"],
}

DISTRICT_CENTERS = {
    "Esil": (51.103, 71.427),
    "Nura": (51.132, 71.357),
    "Almaty": (51.142, 71.485),
    "Saryarka": (51.187, 71.410),
    "Baikonur": (51.179, 71.468),
}

TAG_KEYWORDS = {
    "kindergarten": ["садик", "детсад", "балабақша"],
    "hospital": ["больниц", "поликлиник", "клиник"],
    "elderly": ["пожил", "пенсионер"],
    "night": ["ноч", "вечер", "темно"],
    "recurring": ["снова", "опять", "повтор", "каждый день", "постоянно"],
}


@dataclass
class AnalysisResult:
    category: str
    district: str
    priority_score: int
    risk_level: str
    confidence: int
    mode: str
    summary: str
    explanation: str
    tags: list[str]
    location_missing: bool
    photo_evidence: bool


def analyze_issue(
    text: str,
    latitude: float | None = None,
    longitude: float | None = None,
    image_path: str | None = None,
    created_at: datetime | None = None,
    category_hint: str | None = None,
) -> AnalysisResult:
    del created_at
    normalized = _normalize(text)
    category = category_hint if category_hint in CATEGORIES else _detect_category(normalized)
    district = _detect_district(normalized, latitude, longitude)
    tags = _detect_tags(normalized, category)
    location_missing = latitude is None or longitude is None
    photo_evidence = bool(image_path)
    if photo_evidence:
        tags.append("photo_evidence")

    score, reasons = _score(
        normalized,
        category,
        tags,
        location_missing,
        duplicate_count=0,
        photo_evidence=photo_evidence,
    )
    risk_level = risk_from_score(score)
    confidence = _confidence_score(normalized, category, tags, location_missing, category_hint, photo_evidence)
    summary = _make_summary(text, category)
    explanation = _make_explanation(category, score, risk_level, district, confidence, reasons)

    return AnalysisResult(
        category=category,
        district=district,
        priority_score=score,
        risk_level=risk_level,
        confidence=confidence,
        mode="rule_based",
        summary=summary,
        explanation=explanation,
        tags=list(dict.fromkeys(tags + (["location_missing"] if location_missing else []))),
        location_missing=location_missing,
        photo_evidence=photo_evidence,
    )


def apply_duplicate_bonus(result: AnalysisResult, duplicate_count: int) -> AnalysisResult:
    if duplicate_count <= 0:
        return result
    bonus = min(20, 5 * duplicate_count)
    score = max(0, min(100, result.priority_score + bonus))
    risk_level = risk_from_score(score)
    plural = "обращение" if duplicate_count == 1 else "обращений"
    explanation = (
        f"{result.explanation} Дополнительно найдено {duplicate_count} похожее {plural} рядом, "
        f"поэтому приоритет повышен на {bonus} баллов."
    )
    tags = result.tags[:]
    if "duplicate_cluster" not in tags:
        tags.append("duplicate_cluster")
    return AnalysisResult(
        category=result.category,
        district=result.district,
        priority_score=score,
        risk_level=risk_level,
        confidence=min(100, result.confidence + min(10, duplicate_count * 2)),
        mode=result.mode,
        summary=result.summary,
        explanation=explanation,
        tags=tags,
        location_missing=result.location_missing,
        photo_evidence=result.photo_evidence,
    )


def risk_from_score(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _detect_category(text: str) -> str:
    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        scores[category] = sum(1 for keyword in keywords if keyword in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "other"


def _detect_district(text: str, latitude: float | None, longitude: float | None) -> str:
    for district, keywords in DISTRICT_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return district
    if latitude is None or longitude is None:
        return "Unknown"
    return min(
        DISTRICT_CENTERS,
        key=lambda district: (latitude - DISTRICT_CENTERS[district][0]) ** 2
        + (longitude - DISTRICT_CENTERS[district][1]) ** 2,
    )


def _detect_tags(text: str, category: str) -> list[str]:
    tags = [category]
    for tag, keywords in TAG_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
    if "опас" in text or "травм" in text or "дтп" in text:
        tags.append("safety")
    return list(dict.fromkeys(tags))


def _score(
    text: str,
    category: str,
    tags: list[str],
    location_missing: bool,
    duplicate_count: int,
    photo_evidence: bool = False,
) -> tuple[int, list[str]]:
    score = BASE_SCORES.get(category, 30)
    reasons = [f"базовый балл категории {category}: {score}"]

    if any(keyword in text for keyword in ["опас", "травм", "пожил", "аварийн", "инвалид", "коляск"]):
        score += 14
        reasons.append("прямой риск для здоровья людей: +14")

    if any(keyword in text for keyword in ["проезжая част", "проезжую част", "на проезжей", "выход на дорог", "выходят на дорог", "под колес"]):
        score += 10
        reasons.append("людей вынуждает идти по проезжей части: +10")

    if any(keyword in text for keyword in ["переход", "пешеходн"]):
        score += 6
        reasons.append("затронут пешеходный маршрут: +6")

    if any(keyword in text for keyword in ["холод", "мороз", "зима", "голол", "лед", "лёд"]):
        score += 10
        reasons.append("зимний риск или гололед: +10")

    if any(keyword in text for keyword in ["дожд", "вода", "затоп", "ливнев", "луж"]):
        score += 10
        reasons.append("вода, дождь или подтопление: +10")

    if any(keyword in text for keyword in ["ноч", "темно", "вечер"]):
        score += 8
        reasons.append("темное или вечернее время: +8")

    if any(keyword in text for keyword in ["снова", "опять", "повтор", "постоянно", "каждый день"]):
        score += 10
        reasons.append("проблема повторяется: +10")

    if duplicate_count:
        bonus = min(20, duplicate_count * 5)
        score += bonus
        reasons.append(f"похожие обращения рядом: +{bonus}")

    if photo_evidence:
        score += 3
        reasons.append("есть фото-доказательство: +3")

    if location_missing:
        score -= 15
        reasons.append("не выбрана точка на карте: -15")

    return max(0, min(100, score)), reasons


def _confidence_score(
    text: str,
    category: str,
    tags: list[str],
    location_missing: bool,
    category_hint: str | None,
    photo_evidence: bool,
) -> int:
    keyword_hits = sum(1 for keyword in CATEGORY_KEYWORDS.get(category, []) if keyword in text)
    confidence = 48
    confidence += min(22, keyword_hits * 7)
    confidence += min(14, max(0, len(text) - 30) // 12)
    confidence += min(10, len(tags) * 2)
    if category_hint:
        confidence += 8
    if not location_missing:
        confidence += 8
    if photo_evidence:
        confidence += 6
    if category == "other" and keyword_hits == 0:
        confidence -= 12
    return max(25, min(98, confidence))


def _make_summary(text: str, category: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) > 105:
        compact = compact[:102].rstrip() + "..."
    return compact or f"Новое обращение: {category}"


def _make_explanation(
    category: str,
    score: int,
    risk_level: str,
    district: str,
    confidence: int,
    reasons: list[str],
) -> str:
    reason_text = "; ".join(reasons)
    district_text = district if district != "Unknown" else "район не определен"
    return (
        f"AI присвоил категории {category} приоритет {score}/100 и риск {risk_level}. "
        f"Уверенность: {confidence}%. Район: {district_text}. Логика оценки: {reason_text}."
    )


def _normalize(text: str) -> str:
    return text.lower().replace("ё", "е")

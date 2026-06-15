from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Protocol


STOPWORDS = {
    "возле",
    "около",
    "после",
    "перед",
    "очень",
    "сильно",
    "нужно",
    "прошу",
    "есть",
    "нет",
    "для",
    "что",
    "как",
    "это",
    "там",
    "тут",
    "уже",
    "день",
    "ночью",
    "вечером",
    "утром",
}


class IssueLike(Protocol):
    id: int
    text: str
    category: str
    latitude: float | None
    longitude: float | None


@dataclass
class DuplicateCandidate:
    issue_id: int
    similarity_score: float
    distance_meters: float
    shared_keywords: list[str]


def find_duplicates(
    new_text: str,
    category: str,
    latitude: float | None,
    longitude: float | None,
    existing_issues: list[IssueLike],
    max_distance_meters: float = 500,
) -> list[DuplicateCandidate]:
    if latitude is None or longitude is None:
        return []

    new_keywords = extract_keywords(new_text)
    candidates: list[DuplicateCandidate] = []
    for issue in existing_issues:
        if issue.category != category or issue.latitude is None or issue.longitude is None:
            continue
        distance = haversine_meters(latitude, longitude, issue.latitude, issue.longitude)
        if distance > max_distance_meters:
            continue
        issue_keywords = extract_keywords(issue.text)
        shared = sorted(new_keywords.intersection(issue_keywords))
        if not shared:
            continue
        keyword_score = len(shared) / max(1, len(new_keywords.union(issue_keywords)))
        distance_score = max(0.0, 1 - distance / max_distance_meters)
        similarity = round((keyword_score * 0.65 + distance_score * 0.35) * 100, 1)
        if similarity >= 22:
            candidates.append(
                DuplicateCandidate(
                    issue_id=issue.id,
                    similarity_score=similarity,
                    distance_meters=round(distance, 1),
                    shared_keywords=shared,
                )
            )
    return sorted(candidates, key=lambda item: item.similarity_score, reverse=True)[:8]


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def extract_keywords(text: str) -> set[str]:
    normalized = text.lower().replace("ё", "е")
    words = re.findall(r"[a-zа-яәғқңөұүһі]+", normalized)
    return {word for word in words if len(word) >= 4 and word not in STOPWORDS}

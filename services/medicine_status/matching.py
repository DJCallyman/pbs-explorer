from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from db.models import MedicineStatusEntry


NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
SPACE_RE = re.compile(r"\s+")


def normalize_match_text(value: str | None) -> str:
    text = NON_ALNUM_RE.sub(" ", (value or "").lower())
    return SPACE_RE.sub(" ", text).strip()


def _token_set(value: str | None) -> set[str]:
    text = normalize_match_text(value)
    if not text:
        return set()
    return {token for token in text.split(" ") if len(token) >= 3}


def _purpose_score(purpose: str | None, conditions: Sequence[str]) -> int:
    normalized_purpose = normalize_match_text(purpose)
    purpose_tokens = _token_set(purpose)
    if not normalized_purpose:
        return 0

    best_score = 0
    for condition in conditions:
        normalized_condition = normalize_match_text(condition)
        if not normalized_condition:
            continue
        if normalized_condition == normalized_purpose:
            best_score = max(best_score, 1000)
            continue
        if normalized_condition in normalized_purpose or normalized_purpose in normalized_condition:
            best_score = max(best_score, 500)
            continue
        overlap = len(purpose_tokens & _token_set(condition))
        best_score = max(best_score, overlap)
    return best_score


def choose_best_medicine_status_entry(
    candidates: Iterable[MedicineStatusEntry],
    *,
    conditions: Sequence[str],
) -> MedicineStatusEntry | None:
    candidate_list = list(candidates)
    if not candidate_list:
        return None

    def sort_key(entry: MedicineStatusEntry) -> tuple[int, str, str, str]:
        score = _purpose_score(entry.purpose, conditions)
        pbac_date = entry.pbac_meeting_date.isoformat() if entry.pbac_meeting_date else ""
        meeting_date = entry.meeting_date.isoformat() if entry.meeting_date else ""
        synced = entry.last_synced_at.isoformat() if entry.last_synced_at else ""
        return (score, pbac_date, meeting_date, synced)

    return max(candidate_list, key=sort_key)

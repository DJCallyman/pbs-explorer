from __future__ import annotations

from datetime import date, datetime, timezone

from db.models import MedicineStatusEntry
from services.medicine_status.matching import choose_best_medicine_status_entry, normalize_match_text


def _entry(
    medicine_status_id: str,
    purpose: str,
    meeting_date: str,
) -> MedicineStatusEntry:
    return MedicineStatusEntry(
        medicine_status_id=medicine_status_id,
        document_url=f"https://www.pbs.gov.au/medicinestatus/document/{medicine_status_id}.html",
        drug_name="NIVOLUMAB",
        drug_name_normalized="NIVOLUMAB",
        purpose=purpose,
        pbac_meeting_date=date.fromisoformat(meeting_date),
        last_synced_at=datetime.now(timezone.utc),
    )


def test_normalize_match_text_normalizes_case_and_punctuation() -> None:
    assert normalize_match_text("Non-small cell lung cancer (NSCLC)") == "non small cell lung cancer nsclc"


def test_choose_best_medicine_status_entry_prefers_matching_indication() -> None:
    lung = _entry("1", "Non-small cell lung cancer (NSCLC)", "2024-12-13")
    urothelial = _entry("2", "Urothelial carcinoma (UC)", "2024-11-06")
    fallback_latest = _entry("3", "Multiple indications", "2025-07-09")

    best = choose_best_medicine_status_entry(
        [fallback_latest, urothelial, lung],
        conditions=["Resectable non-small cell lung cancer (NSCLC)"],
    )

    assert best is not None
    assert best.medicine_status_id == "1"


def test_choose_best_medicine_status_entry_falls_back_to_latest_when_no_condition_match() -> None:
    older = _entry("1", "Melanoma", "2024-03-13")
    newer = _entry("2", "Multiple indications", "2025-07-09")

    best = choose_best_medicine_status_entry(
        [older, newer],
        conditions=[],
    )

    assert best is not None
    assert best.medicine_status_id == "2"

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from api.deps import get_db
from config import get_settings
from db.models import Item, MedicineStatusEntry, Schedule
from main import create_app
from services.medicine_status.parser import normalize_medicine_name
import main as main_module


def test_web_items_includes_medicine_status_columns(db, monkeypatch) -> None:
    monkeypatch.setenv("PBS_EXPLORER_WEB_USERNAME", "")
    monkeypatch.setenv("PBS_EXPLORER_WEB_PASSWORD", "")
    monkeypatch.setattr(main_module, "auth_store_has_users", lambda: False)
    get_settings.cache_clear()

    db.add(
        Schedule(
            schedule_code="SC-2025-03",
            effective_date=date(2025, 3, 1),
            effective_month="03",
            effective_year=2025,
        )
    )
    db.add(
        Item(
            li_item_id="ITEM-001",
            schedule_code="SC-2025-03",
            drug_name="PEMBROLIZUMAB",
            brand_name="Keytruda",
            pbs_code="1234J",
            program_code="GE",
            benefit_type_code="S",
            first_listed_date=date(2025, 3, 1),
        )
    )
    db.add(
        MedicineStatusEntry(
            medicine_status_id="1341",
            document_url="https://www.pbs.gov.au/medicinestatus/document/1341.html",
            drug_name="PEMBROLIZUMAB",
            drug_name_normalized=normalize_medicine_name("PEMBROLIZUMAB"),
            brand_names="Keytruda",
            sponsor="MERCK",
            purpose="Cervical cancer",
            meeting_date=date(2025, 3, 12),
            meeting_date_label="March 2025",
            listing_outcome_status="Recommended",
            pbac_meeting_date=date(2025, 3, 12),
            pbac_outcome_published_text="Recommended",
            pbac_outcome_published_url="https://www.pbs.gov.au/info/outcomes",
            public_summary_title="PBAC Public Summary Documents – March 2025",
            public_summary_url="https://www.pbs.gov.au/info/psd/march-2025",
            status="Finalised",
            page_last_updated=date(2026, 1, 31),
            last_synced_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    app = create_app()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/web/items?drug_name=PEMBROLIZUMAB")

    assert response.status_code == 200
    body = response.text
    assert "PBAC Meeting" in body
    assert "PBAC Outcome" in body
    assert "Public Summary" in body
    assert "12-Mar-2025" in body
    assert "https://www.pbs.gov.au/info/outcomes" in body
    assert "https://www.pbs.gov.au/info/psd/march-2025" in body
    get_settings.cache_clear()

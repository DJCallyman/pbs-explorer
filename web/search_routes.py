from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import get_db
from db.models import Item, Indication, MedicineStatusEntry, PrescribingText, Schedule
from services.medicine_status.matching import choose_best_medicine_status_entry
from services.medicine_status.parser import normalize_medicine_name
from services.reports import VALID_RPT_FMT, VALID_VAR, build_report_url, parse_pbs_codes, resolve_start_date
from services.sync.incremental import IncrementalSync
from services.sync.orchestrator import SyncOrchestrator
from utils import escape_like
from web.helpers import (
    DISPENSING_RULE_LABELS,
    PROGRAM_CODE_METADATA,
    PBS_SCHEDULE_LAST_CHECKED_AT_KEY,
    PBS_SCHEDULE_LAST_CHECK_STATUS_KEY,
    PBS_SCHEDULE_LATEST_API_KEY,
    PBS_SCHEDULE_LATEST_EFFECTIVE_DATE_KEY,
    SPA_PRESCRIBING_TEXT,
    SPA_PRESCRIBING_TEXT_ID,
    _build_chart_csv_content,
    _chart_benefit_type_labels,
    _chart_drug_labels,
    _build_filter_options,
    _chart_program_labels,
    _chart_treatment_phase_labels,
    _fetch_sas_report_html,
    _format_admin_effective_date,
    _format_currency,
    _format_dispensing_rule,
    _format_month_year,
    _get_medicare_end_date,
    _matching_indication_pbs_codes_subquery,
    _pbs_schedule_status_payload,
    _resolve_medicare_end_date_for_run,
    _set_setting_value,
    _subtract_months,
    templates,
)

router = APIRouter(include_in_schema=False)


@router.get("/web/settings/medicare-end-date")
def get_medicare_end_date(db: Session = Depends(get_db)):
    return {"end_date": _get_medicare_end_date(db)}


@router.get("/search")
def search(request: Request, db: Session = Depends(get_db)):
    end_date = _get_medicare_end_date(db)
    episodicity_options = [
        row[0]
        for row in db.execute(
            select(Indication.episodicity)
            .where(Indication.episodicity.isnot(None))
            .where(func.trim(Indication.episodicity) != "")
            .distinct()
            .order_by(Indication.episodicity)
        ).all()
    ]
    program_options = [
        {"code": code, **metadata}
        for code, metadata in sorted(PROGRAM_CODE_METADATA.items(), key=lambda item: (item[1]["schedule"], item[1]["pbs_program"]))
    ]
    return templates.TemplateResponse(
        "search.html",
        {"request": request, "medicare_end_date": end_date, "episodicity_options": episodicity_options, "program_options": program_options},
    )


@router.get("/web/pbs-schedule-status")
async def web_pbs_schedule_status(db: Session = Depends(get_db)):
    return await _pbs_schedule_status_payload(db)


@router.post("/web/pbs-schedule-check")
async def web_pbs_schedule_check(db: Session = Depends(get_db)):
    incremental = IncrementalSync(db)
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    current_db_schedule = await incremental.get_current_db_schedule()
    current_db_effective_date = db.execute(
        select(Schedule.effective_date).where(Schedule.schedule_code == current_db_schedule)
    ).scalar() if current_db_schedule else None

    try:
        latest_api_schedule = await incremental.get_latest_schedule_code()
        latest_api_effective_date = await incremental._get_schedule_effective_date(latest_api_schedule) if latest_api_schedule else ""
    except Exception as exc:
        _set_setting_value(db, PBS_SCHEDULE_LAST_CHECKED_AT_KEY, checked_at)
        _set_setting_value(db, PBS_SCHEDULE_LAST_CHECK_STATUS_KEY, f"Check failed: {exc}")
        db.commit()
        payload = await _pbs_schedule_status_payload(db)
        payload["message"] = "Could not check the latest PBS schedule."
        return payload

    latest_api_schedule = latest_api_schedule or ""
    latest_api_effective_date = latest_api_effective_date or ""
    _set_setting_value(db, PBS_SCHEDULE_LAST_CHECKED_AT_KEY, checked_at)
    _set_setting_value(db, PBS_SCHEDULE_LATEST_API_KEY, latest_api_schedule)
    _set_setting_value(db, PBS_SCHEDULE_LATEST_EFFECTIVE_DATE_KEY, latest_api_effective_date)

    if latest_api_schedule and current_db_schedule and latest_api_schedule != current_db_schedule:
        status = f"New PBS schedule available: {_format_admin_effective_date(latest_api_effective_date)} (current database: {_format_admin_effective_date(current_db_effective_date.isoformat() if current_db_effective_date else '')})."
        new_available = True
    elif latest_api_schedule and current_db_schedule:
        status = f"Database is already on the latest PBS schedule: {_format_admin_effective_date(current_db_effective_date.isoformat() if current_db_effective_date else '')}."
        new_available = False
    elif latest_api_schedule:
        status = f"Latest PBS schedule available: {_format_admin_effective_date(latest_api_effective_date)}."
        new_available = False
    else:
        status = "Could not determine the latest PBS schedule."
        new_available = False

    _set_setting_value(db, PBS_SCHEDULE_LAST_CHECK_STATUS_KEY, status)
    db.commit()

    payload = await _pbs_schedule_status_payload(db)
    payload["new_schedule_available"] = new_available
    payload["message"] = status
    return payload


@router.get("/web/suggestions")
def web_suggestions(field: str, q: str = "", db: Session = Depends(get_db)):
    q = q.strip()
    if len(q) < 2:
        return {"options": []}

    field_map = {
        "drug_name": Item.drug_name,
        "brand_name": Item.brand_name,
        "pbs_code": Item.pbs_code,
    }
    column = field_map.get(field)
    if column is None:
        raise HTTPException(status_code=400, detail="Unsupported suggestion field")

    rows = db.execute(
        select(column)
        .where(column.isnot(None))
        .where(func.trim(column) != "")
        .where(column.ilike(f"{escape_like(q)}%"))
        .distinct()
        .order_by(column)
        .limit(8)
    ).all()

    return {"options": [row[0] for row in rows if row[0]]}


@router.get("/web/items")
def web_items(
    request: Request,
    drug_name: str | None = None,
    brand_name: str | None = None,
    pbs_code: str | None = None,
    program_code: str | None = None,
    benefit_type_code: str | None = None,
    indication: str | None = None,
    episodicity: str | None = None,
    schedule_mode: str = "all",
    db: Session = Depends(get_db),
):
    from db.models.relationships import (
        ItemDispensingRuleRelationship,
        ItemPrescribingTextRelationship,
        ItemRestrictionRelationship,
        RestrictionPrescribingTextRelationship,
    )

    schedule_mode = schedule_mode.lower()
    if schedule_mode not in {"current", "historical", "all"}:
        raise HTTPException(status_code=400, detail="Invalid schedule_mode")

    latest_schedule = db.execute(
        select(Schedule.schedule_code, Schedule.effective_date)
        .order_by(Schedule.effective_date.desc(), Schedule.schedule_code.desc())
        .limit(1)
    ).first()

    if latest_schedule is None:
        return templates.TemplateResponse("partials/items_table.html", {"request": request, "items": [], "schedule_mode": schedule_mode})

    latest_schedule_code = latest_schedule.schedule_code
    latest_schedule_date = latest_schedule.effective_date

    filtered_query = (
        select(
            Item.li_item_id.label("li_item_id"),
            Item.schedule_code.label("schedule_code"),
            Schedule.effective_date.label("schedule_effective_date"),
            Item.drug_name.label("drug_name"),
            Item.brand_name.label("brand_name"),
            Item.pbs_code.label("pbs_code"),
            Item.first_listed_date.label("first_listed_date"),
        )
        .join(Schedule, Item.schedule_code == Schedule.schedule_code)
        .where(Item.pbs_code.isnot(None))
    )

    if drug_name:
        filtered_query = filtered_query.where(Item.drug_name.ilike(f"%{escape_like(drug_name)}%"))
    if brand_name:
        filtered_query = filtered_query.where(Item.brand_name.ilike(f"%{escape_like(brand_name)}%"))
    if pbs_code:
        filtered_query = filtered_query.where(Item.pbs_code.ilike(f"%{escape_like(pbs_code)}%"))
    if program_code:
        filtered_query = filtered_query.where(Item.program_code == program_code)
    if benefit_type_code:
        filtered_query = filtered_query.where(Item.benefit_type_code == benefit_type_code)
    if schedule_mode == "current":
        filtered_query = filtered_query.where(Item.schedule_code == latest_schedule_code)
    elif schedule_mode == "historical":
        filtered_query = filtered_query.where(Item.schedule_code != latest_schedule_code)
    if indication or episodicity:
        matching_codes = _matching_indication_pbs_codes_subquery(
            indication=indication,
            episodicity=episodicity,
            latest_schedule_code=latest_schedule_code,
            schedule_mode=schedule_mode,
        )
        filtered_query = filtered_query.where(Item.pbs_code.in_(select(matching_codes.c.pbs_code)))

    filtered_subquery = filtered_query.subquery()
    ranked_subquery = select(
        filtered_subquery,
        func.row_number().over(
            partition_by=filtered_subquery.c.pbs_code,
            order_by=(filtered_subquery.c.schedule_effective_date.desc(), filtered_subquery.c.schedule_code.desc()),
        ).label("row_number"),
    ).subquery()
    grouped_subquery = (
        select(
            filtered_subquery.c.pbs_code.label("pbs_code"),
            func.min(filtered_subquery.c.first_listed_date).label("first_listed_date"),
            func.min(filtered_subquery.c.schedule_effective_date).label("first_seen_date"),
            func.max(filtered_subquery.c.schedule_effective_date).label("last_seen_date"),
            func.count(func.distinct(filtered_subquery.c.schedule_code)).label("schedule_count"),
        )
        .group_by(filtered_subquery.c.pbs_code)
        .subquery()
    )

    items = db.execute(
        select(
            ranked_subquery.c.li_item_id,
            ranked_subquery.c.drug_name,
            ranked_subquery.c.brand_name,
            ranked_subquery.c.pbs_code,
            ranked_subquery.c.schedule_code,
            grouped_subquery.c.first_listed_date,
            grouped_subquery.c.first_seen_date,
            grouped_subquery.c.last_seen_date,
            grouped_subquery.c.schedule_count,
        )
        .join(grouped_subquery, grouped_subquery.c.pbs_code == ranked_subquery.c.pbs_code)
        .where(ranked_subquery.c.row_number == 1)
        .order_by(ranked_subquery.c.drug_name, ranked_subquery.c.brand_name, ranked_subquery.c.pbs_code)
        .limit(50)
    ).all()

    pbs_codes = [item.pbs_code for item in items if item.pbs_code]
    indication_map: dict[str, dict] = {}
    latest_schedule_by_code = {item.pbs_code: item.schedule_code for item in items if item.pbs_code}
    latest_item_rows_map: dict[str, list] = {}
    spa_map: dict[tuple[str, str], bool] = {}
    medicine_status_map: dict[str, list[MedicineStatusEntry]] = {}

    if pbs_codes:
        latest_item_rows = db.execute(
            select(
                Item.pbs_code,
                Item.schedule_code,
                Item.program_code,
                Item.li_form,
                Item.determined_price,
                Item.maximum_prescribable_pack,
                Item.maximum_quantity_units,
                Item.maximum_amount,
                Item.formulary,
                Item.brand_name,
                ItemDispensingRuleRelationship.cmnwlth_dsp_price_max_qty,
                ItemDispensingRuleRelationship.special_patient_contribution,
            )
            .outerjoin(
                ItemDispensingRuleRelationship,
                (ItemDispensingRuleRelationship.li_item_id == Item.li_item_id)
                & (ItemDispensingRuleRelationship.schedule_code == Item.schedule_code),
            )
            .where(Item.pbs_code.in_(pbs_codes))
        ).all()

        for row in latest_item_rows:
            if latest_schedule_by_code.get(row.pbs_code) != row.schedule_code:
                continue
            latest_item_rows_map.setdefault(row.pbs_code, []).append(row)

        spa_rows = db.execute(
            select(ItemRestrictionRelationship.pbs_code, ItemRestrictionRelationship.schedule_code)
            .join(
                RestrictionPrescribingTextRelationship,
                (ItemRestrictionRelationship.res_code == RestrictionPrescribingTextRelationship.res_code)
                & (ItemRestrictionRelationship.schedule_code == RestrictionPrescribingTextRelationship.schedule_code),
            )
            .join(
                PrescribingText,
                (RestrictionPrescribingTextRelationship.prescribing_text_id == PrescribingText.prescribing_txt_id)
                & (RestrictionPrescribingTextRelationship.schedule_code == PrescribingText.schedule_code),
            )
            .where(ItemRestrictionRelationship.pbs_code.in_(pbs_codes))
            .where((PrescribingText.prescribing_txt_id == SPA_PRESCRIBING_TEXT_ID) | (PrescribingText.prescribing_txt == SPA_PRESCRIBING_TEXT))
            .distinct()
        ).all()
        for row in spa_rows:
            spa_map[(row.pbs_code, row.schedule_code)] = True

        item_spa_rows = db.execute(
            select(ItemPrescribingTextRelationship.pbs_code, ItemPrescribingTextRelationship.schedule_code)
            .join(
                PrescribingText,
                (ItemPrescribingTextRelationship.prescribing_txt_id == PrescribingText.prescribing_txt_id)
                & (ItemPrescribingTextRelationship.schedule_code == PrescribingText.schedule_code),
            )
            .where(ItemPrescribingTextRelationship.pbs_code.in_(pbs_codes))
            .where((PrescribingText.prescribing_txt_id == SPA_PRESCRIBING_TEXT_ID) | (PrescribingText.prescribing_txt == SPA_PRESCRIBING_TEXT))
            .distinct()
        ).all()
        for row in item_spa_rows:
            spa_map[(row.pbs_code, row.schedule_code)] = True

        detail_query = (
            select(ItemRestrictionRelationship.pbs_code, Indication.condition, Indication.episodicity)
            .join(
                RestrictionPrescribingTextRelationship,
                (Indication.indication_prescribing_txt_id == RestrictionPrescribingTextRelationship.prescribing_text_id)
                & (Indication.schedule_code == RestrictionPrescribingTextRelationship.schedule_code),
            )
            .join(
                PrescribingText,
                (RestrictionPrescribingTextRelationship.prescribing_text_id == PrescribingText.prescribing_txt_id)
                & (RestrictionPrescribingTextRelationship.schedule_code == PrescribingText.schedule_code),
            )
            .join(
                ItemRestrictionRelationship,
                (RestrictionPrescribingTextRelationship.res_code == ItemRestrictionRelationship.res_code)
                & (RestrictionPrescribingTextRelationship.schedule_code == ItemRestrictionRelationship.schedule_code),
            )
            .where(ItemRestrictionRelationship.pbs_code.in_(pbs_codes))
            .distinct()
        )
        if schedule_mode == "current":
            detail_query = detail_query.where(ItemRestrictionRelationship.schedule_code == latest_schedule_code)
        elif schedule_mode == "historical":
            detail_query = detail_query.where(ItemRestrictionRelationship.schedule_code != latest_schedule_code)

        indication_rows = db.execute(detail_query).all()
        for row in indication_rows:
            entry = indication_map.setdefault(row.pbs_code, {"conditions": [], "episodicities": []})
            if row.condition and row.condition not in entry["conditions"]:
                entry["conditions"].append(row.condition)
            if row.episodicity and row.episodicity not in entry["episodicities"]:
                entry["episodicities"].append(row.episodicity)

        drug_keys = {
            normalize_medicine_name(item.drug_name)
            for item in items
            if item.drug_name
        }
        if drug_keys:
            medicine_status_rows = db.execute(
                select(MedicineStatusEntry)
                .where(MedicineStatusEntry.drug_name_normalized.in_(drug_keys))
                .order_by(
                    MedicineStatusEntry.pbac_meeting_date.desc(),
                    MedicineStatusEntry.meeting_date.desc(),
                    MedicineStatusEntry.last_synced_at.desc(),
                )
            ).scalars().all()
            for row in medicine_status_rows:
                medicine_status_map.setdefault(row.drug_name_normalized, []).append(row)

    items_with_data = []
    for item in items:
        ind = indication_map.get(item.pbs_code, {})
        latest_rows = latest_item_rows_map.get(item.pbs_code, [])
        medicine_status = choose_best_medicine_status_entry(
            medicine_status_map.get(normalize_medicine_name(item.drug_name), []),
            conditions=ind.get("conditions", []),
        )

        distinct_forms = sorted({row.li_form for row in latest_rows if row.li_form})
        if len(distinct_forms) <= 2:
            form_summary = " | ".join(distinct_forms)
        else:
            form_summary = " | ".join(distinct_forms[:2]) + f" (+{len(distinct_forms) - 2} more)"

        def summarise_value(values: list):
            distinct_values = [value for value in dict.fromkeys(values) if value not in (None, "", "None")]
            if not distinct_values:
                return ""
            if len(distinct_values) == 1:
                return distinct_values[0]
            return "Multiple"

        aemp_value = summarise_value([row.determined_price for row in latest_rows])
        dispensed_price_value = summarise_value([row.cmnwlth_dsp_price_max_qty for row in latest_rows])
        aemp_filter_values = [
            _format_currency(value)
            for value in dict.fromkeys(row.determined_price for row in latest_rows if row.determined_price not in (None, "", "None"))
        ]
        current_schedule_code = item.schedule_code
        spa_flag_value = "Y" if spa_map.get((item.pbs_code, current_schedule_code), False) else "N"
        max_qty_packs_value = summarise_value([row.maximum_prescribable_pack for row in latest_rows])
        max_qty_units_value = summarise_value([row.maximum_quantity_units if row.maximum_quantity_units is not None else row.maximum_amount for row in latest_rows])
        formulary_value = summarise_value([row.formulary for row in latest_rows])
        schedule_value = summarise_value([PROGRAM_CODE_METADATA.get(row.program_code, {}).get("schedule", row.program_code) for row in latest_rows])
        pbs_program_value = summarise_value([PROGRAM_CODE_METADATA.get(row.program_code, {}).get("pbs_program", row.program_code) for row in latest_rows])
        pbac_meeting_date = medicine_status.pbac_meeting_date or medicine_status.meeting_date if medicine_status else None
        pbac_meeting_date_display = pbac_meeting_date.strftime("%d-%b-%Y") if pbac_meeting_date else ""

        items_with_data.append(
            {
                "li_item_id": item.li_item_id,
                "drug_name": item.drug_name,
                "brand_name": item.brand_name,
                "pbs_code": item.pbs_code,
                "first_listed_date": item.first_listed_date,
                "first_listed_date_display": _format_month_year(item.first_listed_date),
                "first_seen_date": item.first_seen_date,
                "last_seen_date": item.last_seen_date,
                "last_seen_date_display": _format_month_year(item.last_seen_date),
                "latest_schedule_code": item.schedule_code,
                "status": "Current" if item.last_seen_date == latest_schedule_date else "Historical",
                "item_code_status": "Active" if item.last_seen_date == latest_schedule_date else "Inactive",
                "form_summary": form_summary,
                "aemp": aemp_value,
                "aemp_display": _format_currency(aemp_value),
                "aemp_filter_values": aemp_filter_values,
                "dispensed_price": dispensed_price_value,
                "dispensed_price_display": _format_currency(dispensed_price_value),
                "spa_flag": spa_flag_value,
                "max_qty_packs": max_qty_packs_value,
                "max_qty_units": max_qty_units_value,
                "formulary": formulary_value,
                "schedule_label": schedule_value,
                "pbs_program_label": pbs_program_value,
                "indications": "; ".join(ind.get("conditions", [])[:3]),
                "episodicity": "; ".join(ind.get("episodicities", [])[:3]) or "Not specified",
                "pbac_meeting_date": pbac_meeting_date.isoformat() if pbac_meeting_date else "",
                "pbac_meeting_date_display": pbac_meeting_date_display,
                "pbac_outcome_published": medicine_status.pbac_outcome_published_text if medicine_status else "",
                "pbac_outcome_link": medicine_status.pbac_outcome_published_url if medicine_status else "",
                "public_summary_title": medicine_status.public_summary_title if medicine_status else "",
                "public_summary_url": medicine_status.public_summary_url if medicine_status else "",
                "medicine_status_url": medicine_status.document_url if medicine_status else "",
            }
        )

    return templates.TemplateResponse(
        "partials/items_table.html",
        {"request": request, "items": items_with_data, "filter_options": _build_filter_options(items_with_data), "schedule_mode": schedule_mode},
    )


@router.get("/web/items/{pbs_code}/history")
def web_item_history(request: Request, pbs_code: str, schedule_mode: str = "all", db: Session = Depends(get_db)):
    from db.models.item_pricing_event import ItemPricingEvent
    from db.models.relationships import (
        ItemDispensingRuleRelationship,
        ItemPrescribingTextRelationship,
        ItemRestrictionRelationship,
        RestrictionPrescribingTextRelationship,
    )

    schedule_mode = schedule_mode.lower()
    if schedule_mode not in {"current", "historical", "all"}:
        raise HTTPException(status_code=400, detail="Invalid schedule_mode")

    latest_schedule = db.execute(
        select(Schedule.schedule_code, Schedule.effective_date)
        .order_by(Schedule.effective_date.desc(), Schedule.schedule_code.desc())
        .limit(1)
    ).first()
    latest_schedule_code = latest_schedule.schedule_code if latest_schedule else None

    query = (
        select(
            Item.li_item_id, Item.schedule_code, Schedule.effective_date, Item.drug_name, Item.brand_name, Item.program_code,
            Item.li_form, Item.determined_price, Item.maximum_prescribable_pack, Item.maximum_quantity_units,
            Item.maximum_amount, Item.formulary, Item.first_listed_date,
            ItemDispensingRuleRelationship.cmnwlth_dsp_price_max_qty,
            ItemDispensingRuleRelationship.dispensing_rule_mnem,
            ItemDispensingRuleRelationship.dispensing_rule_reference,
            ItemDispensingRuleRelationship.special_patient_contribution,
        )
        .join(Schedule, Item.schedule_code == Schedule.schedule_code)
        .outerjoin(
            ItemDispensingRuleRelationship,
            (ItemDispensingRuleRelationship.li_item_id == Item.li_item_id)
            & (ItemDispensingRuleRelationship.schedule_code == Item.schedule_code),
        )
        .where(Item.pbs_code == pbs_code)
        .order_by(Item.li_form.asc(), Schedule.effective_date.asc(), Item.schedule_code.asc())
    )
    if latest_schedule_code:
        if schedule_mode == "current":
            query = query.where(Item.schedule_code == latest_schedule_code)
        elif schedule_mode == "historical":
            query = query.where(Item.schedule_code != latest_schedule_code)
    rows = db.execute(query).all()

    spa_rows = db.execute(
        select(ItemRestrictionRelationship.pbs_code, ItemRestrictionRelationship.schedule_code)
        .join(
            RestrictionPrescribingTextRelationship,
            (ItemRestrictionRelationship.res_code == RestrictionPrescribingTextRelationship.res_code)
            & (ItemRestrictionRelationship.schedule_code == RestrictionPrescribingTextRelationship.schedule_code),
        )
        .join(
            PrescribingText,
            (RestrictionPrescribingTextRelationship.prescribing_text_id == PrescribingText.prescribing_txt_id)
            & (RestrictionPrescribingTextRelationship.schedule_code == PrescribingText.schedule_code),
        )
        .where(ItemRestrictionRelationship.pbs_code == pbs_code)
        .where((PrescribingText.prescribing_txt_id == SPA_PRESCRIBING_TEXT_ID) | (PrescribingText.prescribing_txt == SPA_PRESCRIBING_TEXT))
        .distinct()
    ).all()
    item_spa_rows = db.execute(
        select(ItemPrescribingTextRelationship.pbs_code, ItemPrescribingTextRelationship.schedule_code)
        .join(
            PrescribingText,
            (ItemPrescribingTextRelationship.prescribing_txt_id == PrescribingText.prescribing_txt_id)
            & (ItemPrescribingTextRelationship.schedule_code == PrescribingText.schedule_code),
        )
        .where(ItemPrescribingTextRelationship.pbs_code == pbs_code)
        .where((PrescribingText.prescribing_txt_id == SPA_PRESCRIBING_TEXT_ID) | (PrescribingText.prescribing_txt == SPA_PRESCRIBING_TEXT))
        .distinct()
    ).all()
    spa_schedules = {(row.pbs_code, row.schedule_code) for row in spa_rows} | {(row.pbs_code, row.schedule_code) for row in item_spa_rows}

    pricing_events = db.execute(
        select(ItemPricingEvent.li_item_id, ItemPricingEvent.schedule_code, ItemPricingEvent.event_type_code, ItemPricingEvent.percentage_applied)
        .where(ItemPricingEvent.li_item_id.in_([row.li_item_id for row in rows]))
    ).all() if rows else []

    pricing_event_map: dict[tuple[str, str], list[str]] = {}
    for event in pricing_events:
        label = event.event_type_code
        if event.percentage_applied is not None:
            label = f"{label} ({event.percentage_applied}%)"
        pricing_event_map.setdefault((event.li_item_id, event.schedule_code), []).append(label)

    grouped_history: dict[str, list[dict]] = {}
    for row in rows:
        max_qty_units_display = row.maximum_quantity_units if row.maximum_quantity_units is not None else row.maximum_amount
        history_row = {
            "li_item_id": row.li_item_id,
            "schedule_code": row.schedule_code,
            "effective_date": row.effective_date,
            "effective_date_display": _format_month_year(row.effective_date),
            "drug_name": row.drug_name,
            "brand_name": row.brand_name,
            "li_form": row.li_form,
            "aemp": _format_currency(row.determined_price),
            "dispensed_price": _format_currency(row.cmnwlth_dsp_price_max_qty),
            "dispensing_rule": _format_dispensing_rule(row.dispensing_rule_mnem or row.dispensing_rule_reference or ""),
            "spa_flag": "Y" if (pbs_code, row.schedule_code) in spa_schedules else "N",
            "max_qty_packs": row.maximum_prescribable_pack,
            "max_qty_units": max_qty_units_display,
            "formulary": row.formulary,
            "first_listed_date": row.first_listed_date,
            "pricing_events": pricing_event_map.get((row.li_item_id, row.schedule_code), []),
            "status": "Current" if row.schedule_code == latest_schedule_code else "Historical",
            "schedule_label": PROGRAM_CODE_METADATA.get(row.program_code, {}).get("schedule", row.program_code),
            "pbs_program_label": PROGRAM_CODE_METADATA.get(row.program_code, {}).get("pbs_program", row.program_code),
        }
        grouped_history.setdefault(row.li_form or row.li_item_id, []).append(history_row)

    history_groups = [{"label": label, "rows": list(reversed(group_rows)), "li_item_id": group_rows[0]["li_item_id"]} for label, group_rows in grouped_history.items()]
    return templates.TemplateResponse(
        "partials/item_history.html",
        {"request": request, "pbs_code": pbs_code, "history_groups": history_groups, "schedule_mode": schedule_mode},
    )


@router.get("/web/stats")
def web_stats(request: Request, db: Session = Depends(get_db)):
    total_items = db.execute(select(func.count(Item.li_item_id))).scalar()
    latest_schedule = db.execute(select(Schedule.schedule_code).order_by(Schedule.effective_date.desc()).limit(1)).scalar()
    orchestrator = SyncOrchestrator(db)
    sync_status = orchestrator.get_sync_status()
    last_sync = sync_status.get("last_sync")
    last_sync_display = "Never"
    if last_sync and last_sync.get("at"):
        last_sync_display = last_sync["at"][:10] if "T" in last_sync["at"] else last_sync["at"]
    return templates.TemplateResponse(
        "partials/home_stats.html",
        {"request": request, "total_items": total_items or 0, "latest_schedule": latest_schedule or "N/A", "last_sync": last_sync_display},
    )


@router.get("/web/pbs-report")
async def pbs_report(
    request: Request,
    pbs_codes: str,
    start_date: str | None = None,
    end_date: str | None = None,
    var: str = "SERVICES",
    rpt_fmt: str = "2",
    db: Session = Depends(get_db),
):
    if var not in VALID_VAR:
        raise HTTPException(status_code=400, detail=f"Invalid var: {var}. Must be one of {VALID_VAR}")
    if rpt_fmt not in VALID_RPT_FMT:
        raise HTTPException(status_code=400, detail=f"Invalid rpt_fmt: {rpt_fmt}. Must be one of {VALID_RPT_FMT}")
    codes = parse_pbs_codes(pbs_codes)
    if not codes:
        raise HTTPException(status_code=400, detail="No PBS codes provided")
    start_date = resolve_start_date(db, codes, start_date)
    end_date, _ = await _resolve_medicare_end_date_for_run(db, codes, start_date, var, rpt_fmt, end_date)
    return RedirectResponse(url=build_report_url(codes, start_date, end_date, var, rpt_fmt), status_code=302)


@router.post("/web/pbs-report-warmup")
async def pbs_report_warmup(
    request: Request,
    pbs_codes: str,
    start_date: str | None = None,
    end_date: str | None = None,
    var: str = "SERVICES",
    rpt_fmt: str = "2",
    db: Session = Depends(get_db),
):
    return Response(status_code=204)


@router.get("/web/pbs-report-excel")
async def pbs_report_excel(
    request: Request,
    pbs_codes: str,
    start_date: str | None = None,
    end_date: str | None = None,
    var: str = "SERVICES",
    rpt_fmt: str = "2",
    db: Session = Depends(get_db),
):
    codes = parse_pbs_codes(pbs_codes)
    if not codes:
        raise HTTPException(status_code=400, detail="No PBS codes provided")
    if len(codes) > 20:
        raise HTTPException(status_code=400, detail="Medicare Statistics allows up to 20 item codes per report")
    if var not in VALID_VAR:
        raise HTTPException(status_code=400, detail=f"Invalid var: {var}. Must be one of {VALID_VAR}")
    if rpt_fmt not in VALID_RPT_FMT:
        raise HTTPException(status_code=400, detail=f"Invalid rpt_fmt: {rpt_fmt}. Must be one of {VALID_RPT_FMT}")
    start_date = resolve_start_date(db, codes, start_date)
    end_date, probed_html = await _resolve_medicare_end_date_for_run(db, codes, start_date, var, rpt_fmt, end_date)
    html = probed_html or await _fetch_sas_report_html(codes, start_date, end_date, var, rpt_fmt)
    csv_content, filename = _build_chart_csv_content(
        html,
        codes,
        start_date,
        end_date,
        var,
        rpt_fmt,
        _chart_program_labels(db, codes),
        _chart_benefit_type_labels(db, codes),
        _chart_treatment_phase_labels(db, codes),
        _chart_drug_labels(db, codes),
    )
    excel_filename = filename.replace(".csv", "_excel.csv") if filename.endswith(".csv") else f"{filename}_excel.csv"
    return Response(content=csv_content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{excel_filename}"'})


@router.get("/web/pbs-report-clean-csv")
async def pbs_report_clean_csv(
    request: Request,
    pbs_codes: str,
    start_date: str | None = None,
    end_date: str | None = None,
    var: str = "SERVICES",
    rpt_fmt: str = "2",
    db: Session = Depends(get_db),
):
    codes = parse_pbs_codes(pbs_codes)
    if not codes:
        raise HTTPException(status_code=400, detail="No PBS codes provided")
    if len(codes) > 20:
        raise HTTPException(status_code=400, detail="Medicare Statistics allows up to 20 item codes per report")
    if var not in VALID_VAR:
        raise HTTPException(status_code=400, detail=f"Invalid var: {var}. Must be one of {VALID_VAR}")
    if rpt_fmt not in VALID_RPT_FMT:
        raise HTTPException(status_code=400, detail=f"Invalid rpt_fmt: {rpt_fmt}. Must be one of {VALID_RPT_FMT}")
    start_date = resolve_start_date(db, codes, start_date)
    end_date, probed_html = await _resolve_medicare_end_date_for_run(db, codes, start_date, var, rpt_fmt, end_date)
    html = probed_html or await _fetch_sas_report_html(codes, start_date, end_date, var, rpt_fmt)
    csv_content, filename = _build_chart_csv_content(
        html,
        codes,
        start_date,
        end_date,
        var,
        rpt_fmt,
        _chart_program_labels(db, codes),
        _chart_benefit_type_labels(db, codes),
        _chart_treatment_phase_labels(db, codes),
        _chart_drug_labels(db, codes),
    )
    return Response(content=csv_content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

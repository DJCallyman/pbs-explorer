from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from api.deps import get_db
from services.saved_reports import (
    can_manage_report as can_manage_saved_report,
    can_view_report as can_view_saved_report,
    create_report as create_saved_report,
    delete_report as delete_saved_report,
    ensure_csv_access_token as ensure_saved_report_csv_access_token,
    get_report as get_saved_report,
    list_reports as list_saved_reports,
    manifest_path as saved_reports_manifest_path,
    rotate_csv_access_token as rotate_saved_report_csv_access_token,
    update_report as update_saved_report,
)
from web.helpers import (
    REPORT_FORMAT_LABELS,
    _available_saved_report_users,
    _build_chart_csv_content,
    _chart_benefit_type_labels,
    _chart_drug_labels,
    _build_saved_report_definition_from_form,
    _chart_program_labels,
    _chart_treatment_phase_labels,
    _fetch_sas_report_html,
    _format_display_date,
    _medicare_status_payload,
    _request_role,
    _request_username,
    _resolve_medicare_end_date_for_run,
    _resolve_saved_report_codes,
    _resolve_saved_report_codes_for_run,
    _resolve_saved_report_start_date,
    _resolve_saved_report_window,
    _saved_report_code_summaries,
    _saved_report_form_initial,
    _saved_report_needs_narrowing,
    _subtract_months,
    refresh_latest_medicare_data,
    templates,
)

router = APIRouter(include_in_schema=False)


@router.get("/saved-reports")
def saved_reports(request: Request, db: Session = Depends(get_db)):
    current_user = _request_username(request)
    current_role = _request_role(request)
    edit_slug = str(request.query_params.get("edit") or "").strip()
    edit_definition = get_saved_report(edit_slug) if edit_slug else None
    if edit_definition and not can_manage_saved_report(edit_definition, current_user, current_role):
        raise HTTPException(status_code=403, detail="You do not have permission to edit this saved report")
    form_initial = _saved_report_form_initial(edit_definition)
    rows = []
    for report in list_saved_reports():
        if not can_view_saved_report(report, current_user, current_role):
            continue
        slug = str(report.get("slug") or "").strip()
        if not slug:
            continue
        csv_access_token = ensure_saved_report_csv_access_token(slug)
        source_type = report.get("source_type", "search_based")
        cached_validation = report.get("cached_validation", {}) or {}
        cached_codes = cached_validation.get("resolved_codes", []) or []
        cached_summaries = cached_validation.get("code_summaries", []) or []
        validated_at = _format_display_date(str(cached_validation.get("validated_at") or ""))
        code_summary = "Not validated yet"
        warning = ""
        status_level = "ready"
        status_text = "Ready"
        if source_type == "fixed_codes":
            fixed_codes = report.get("codes", []) or []
            code_summary = f"{len(fixed_codes)} fixed code" + ("" if len(fixed_codes) == 1 else "s")
        elif cached_codes:
            code_summary = f"{len(cached_codes)} code" + ("" if len(cached_codes) == 1 else "s") + " from last validation"
            status_text = "Validated"
        elif _saved_report_needs_narrowing(report):
            warning = "Add Drug, Brand, or PBS code before validating. Broad indication-only searches can hang."
            status_level = "warning"
            status_text = "Needs narrowing"

        window = (report.get("report", {}) or {}).get("window", {}) or {}
        window_type = window.get("type", "rolling_months")
        if window_type == "rolling_months":
            window_label = f"Rolling {window.get('months', 12)} months"
        elif window_type == "since_first_listing":
            window_label = "From First PBS listing"
        else:
            window_label = "Explicit dates"

        search = report.get("search", {}) or {}
        search_parts = []
        for label, key in [
            ("Drug", "drug_name"),
            ("Brand", "brand_name"),
            ("Item code", "pbs_code"),
            ("Indication", "indication"),
        ]:
            if search.get(key):
                search_parts.append(f"{label}: {search[key]}")

        rows.append(
            {
                "slug": slug,
                "name": report.get("name") or slug,
                "owner": report.get("owner") or "",
                "shared_with": report.get("shared_with") or [],
                "can_manage": can_manage_saved_report(report, current_user, current_role),
                "description": report.get("description") or "",
                "metric": (report.get("report", {}) or {}).get("var", "SERVICES"),
                "report_format_label": REPORT_FORMAT_LABELS.get((report.get("report", {}) or {}).get("rpt_fmt", "2"), "Unknown"),
                "window_label": window_label,
                "code_summary": code_summary,
                "warning": warning,
                "status_level": status_level,
                "status_text": status_text,
                "search_summary": " | ".join(search_parts),
                "absolute_csv_url": str(request.base_url).rstrip("/") + f"/web/saved-reports/{slug}.csv?access_token={csv_access_token}",
                "edit_url": f"/saved-reports?edit={slug}",
                "delete_url": f"/web/saved-reports/{slug}/delete",
                "validate_url": f"/web/saved-reports/{slug}/validate",
                "rotate_token_url": f"/web/saved-reports/{slug}/rotate-token",
                "share_url": f"/web/saved-reports/{slug}/share",
                "validated_at": validated_at,
                "cached_summaries": cached_summaries,
            }
        )

    return templates.TemplateResponse(
        "saved_reports.html",
        {
            "request": request,
            "reports": rows,
            "medicare_status": _medicare_status_payload(db),
            "manifest_path": str(saved_reports_manifest_path()),
            "message": request.query_params.get("message", ""),
            "error": request.query_params.get("error", ""),
            "edit_slug": edit_slug,
            "edit_mode": edit_definition is not None,
            "form_action": f"/web/saved-reports/{edit_slug}/update" if edit_definition else "/web/saved-reports/create",
            "form_submit_label": "Save Changes" if edit_definition else "Create Saved Report",
            "form_heading": "Edit Saved Report" if edit_definition else "Create Saved Report",
            "form_initial": form_initial,
            "share_user_options": [username for username in _available_saved_report_users(request) if username != _request_username(request)],
        },
    )


@router.post("/web/saved-reports/check-latest")
async def saved_reports_check_latest():
    status = await refresh_latest_medicare_data()
    month = status.get("end_date_label") or status.get("end_date") or "Unknown"
    return RedirectResponse(url=f"/saved-reports?message=Latest+Medicare+data+checked:+{month}", status_code=303)


@router.post("/web/saved-reports/create")
async def saved_reports_create(request: Request):
    current_user = _request_username(request)
    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    if str((parsed.get("source_type") or ["search_based"])[0]) == "search_based":
        if not str((parsed.get("drug_name") or [""])[0]).strip() and not str((parsed.get("brand_name") or [""])[0]).strip():
            return RedirectResponse(
                url="/saved-reports?error=Search-based+reports+must+include+at+least+one+Drug+or+Brand+value",
                status_code=303,
            )
    try:
        report_definition = _build_saved_report_definition_from_form(parsed, owner=current_user)
        create_saved_report(report_definition)
    except ValueError as exc:
        return RedirectResponse(url=f"/saved-reports?error={str(exc).replace(' ', '+')}", status_code=303)

    return RedirectResponse(url=f"/saved-reports?message=Saved+report+created:+{report_definition['slug']}", status_code=303)


@router.post("/web/saved-reports/{slug}/update")
async def saved_reports_update(slug: str, request: Request):
    current_user = _request_username(request)
    current_role = _request_role(request)
    existing = get_saved_report(slug)
    if not existing:
        return RedirectResponse(url="/saved-reports?error=Saved+report+not+found", status_code=303)
    if not can_manage_saved_report(existing, current_user, current_role):
        return RedirectResponse(url="/saved-reports?error=You+do+not+have+permission+to+edit+this+saved+report", status_code=303)

    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    if str((parsed.get("source_type") or ["search_based"])[0]) == "search_based":
        if not str((parsed.get("drug_name") or [""])[0]).strip() and not str((parsed.get("brand_name") or [""])[0]).strip():
            return RedirectResponse(
                url=f"/saved-reports?edit={slug}&error=Search-based+reports+must+include+at+least+one+Drug+or+Brand+value",
                status_code=303,
            )
    try:
        report_definition = _build_saved_report_definition_from_form(
            parsed,
            owner=str(existing.get("owner") or current_user),
            existing_slug=slug,
            existing_token=str(existing.get("csv_access_token") or ""),
            existing_shared_with=[str(username).strip() for username in (existing.get("shared_with") or []) if str(username).strip()],
        )
        update_saved_report(slug, report_definition)
    except ValueError as exc:
        return RedirectResponse(url=f"/saved-reports?edit={slug}&error={str(exc).replace(' ', '+')}", status_code=303)

    return RedirectResponse(url=f"/saved-reports?message=Saved+report+updated:+{slug}", status_code=303)


@router.post("/web/saved-reports/{slug}/delete")
def saved_reports_delete(slug: str, request: Request):
    definition = get_saved_report(slug)
    if not definition:
        return RedirectResponse(url="/saved-reports?error=Saved+report+not+found", status_code=303)
    if not can_manage_saved_report(definition, _request_username(request), _request_role(request)):
        return RedirectResponse(url="/saved-reports?error=You+do+not+have+permission+to+delete+this+saved+report", status_code=303)
    try:
        delete_saved_report(slug)
    except ValueError as exc:
        return RedirectResponse(url=f"/saved-reports?error={str(exc).replace(' ', '+')}", status_code=303)

    return RedirectResponse(url="/saved-reports?message=Saved+report+deleted", status_code=303)


@router.post("/web/saved-reports/{slug}/rotate-token")
def saved_reports_rotate_token(slug: str, request: Request):
    definition = get_saved_report(slug)
    if not definition:
        return RedirectResponse(url="/saved-reports?error=Saved+report+not+found", status_code=303)
    if not can_manage_saved_report(definition, _request_username(request), _request_role(request)):
        return RedirectResponse(url="/saved-reports?error=You+do+not+have+permission+to+rotate+this+Power+Query+URL", status_code=303)
    try:
        rotate_saved_report_csv_access_token(slug)
    except ValueError as exc:
        return RedirectResponse(url=f"/saved-reports?error={str(exc).replace(' ', '+')}", status_code=303)
    return RedirectResponse(url=f"/saved-reports?message=Power+Query+URL+rotated+for+{slug}", status_code=303)


@router.post("/web/saved-reports/{slug}/share")
async def saved_reports_share(slug: str, request: Request):
    current_user = _request_username(request)
    current_role = _request_role(request)
    existing = get_saved_report(slug)
    if not existing:
        return RedirectResponse(url="/saved-reports?error=Saved+report+not+found", status_code=303)
    if not can_manage_saved_report(existing, current_user, current_role):
        return RedirectResponse(url="/saved-reports?error=You+do+not+have+permission+to+share+this+saved+report", status_code=303)

    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    shared_with = sorted(
        {
            str(username).strip()
            for username in parsed.get("shared_with", [])
            if str(username).strip() and str(username).strip() != current_user
        },
        key=str.lower,
    )
    updated = dict(existing)
    updated["shared_with"] = shared_with
    try:
        update_saved_report(slug, updated)
    except ValueError as exc:
        return RedirectResponse(url=f"/saved-reports?error={str(exc).replace(' ', '+')}", status_code=303)

    if shared_with:
        return RedirectResponse(url=f"/saved-reports?message=Sharing+updated+for+{slug}", status_code=303)
    return RedirectResponse(url=f"/saved-reports?message=Sharing+cleared+for+{slug}", status_code=303)


@router.post("/web/saved-reports/{slug}/validate")
def saved_reports_validate(slug: str, request: Request, db: Session = Depends(get_db)):
    definition = get_saved_report(slug)
    if not definition:
        return RedirectResponse(url="/saved-reports?error=Saved+report+not+found", status_code=303)
    if not can_view_saved_report(definition, _request_username(request), _request_role(request)):
        return RedirectResponse(url="/saved-reports?error=You+do+not+have+permission+to+use+this+saved+report", status_code=303)

    if _saved_report_needs_narrowing(definition):
        return RedirectResponse(
            url=f"/saved-reports?edit={slug}&error=Validation+for+{slug}+needs+Drug,+Brand,+or+PBS+code+to+avoid+a+broad+scan",
            status_code=303,
        )

    try:
        codes = _resolve_saved_report_codes(definition, db, limit=21)
        if not codes:
            return RedirectResponse(url=f"/saved-reports?error=Validation:+{slug}+currently+matches+no+PBS+codes", status_code=303)
        if len(codes) > 20:
            return RedirectResponse(url=f"/saved-reports?error=Validation:+{slug}+currently+matches+more+than+20+PBS+codes", status_code=303)
        validated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        definition["cached_validation"] = {
            "validated_at": validated_at,
            "resolved_codes": codes,
            "resolved_code_count": len(codes),
            "code_summaries": _saved_report_code_summaries(db, codes),
        }
        update_saved_report(slug, definition)
    except Exception as exc:
        return RedirectResponse(url=f"/saved-reports?error=Validation+failed+for+{slug}:+{str(exc).replace(' ', '+')}", status_code=303)

    return RedirectResponse(
        url=f"/saved-reports?message=Validation:+{slug}+matches+{len(codes)}+PBS+code" + ("" if len(codes) == 1 else "s"),
        status_code=303,
    )


@router.get("/web/saved-reports/{slug}.csv")
async def saved_report_csv(request: Request, slug: str, db: Session = Depends(get_db)):
    definition = get_saved_report(slug)
    if not definition:
        raise HTTPException(status_code=404, detail="Saved report not found")
    token = str(request.query_params.get("access_token") or "").strip()
    if not token and not can_view_saved_report(definition, _request_username(request), _request_role(request)):
        raise HTTPException(status_code=403, detail="You do not have permission to use this saved report")

    codes = _resolve_saved_report_codes_for_run(definition, db, limit=25)
    if not codes:
        raise HTTPException(status_code=400, detail="This saved report currently resolves to no PBS codes")
    if len(codes) > 20:
        raise HTTPException(status_code=400, detail="This saved report currently resolves to more than 20 PBS codes. Narrow the search or switch the report to fixed codes.")

    report = definition.get("report", {}) or {}
    var = report.get("var", "SERVICES")
    rpt_fmt = report.get("rpt_fmt", "2")
    report_window = report.get("window", {}) or {}
    explicit_end_date = report_window.get("end_date") if report_window.get("type") == "explicit" else None
    start_date = _resolve_saved_report_start_date(definition, db, codes)
    end_date, probed_html = await _resolve_medicare_end_date_for_run(db, codes, start_date, var, rpt_fmt, explicit_end_date)
    if report_window.get("type") == "rolling_months":
        months = int(report_window.get("months", 12))
        start_date = _subtract_months(end_date, max(months - 1, 0))
        probed_html = None
    elif report_window.get("type") == "since_first_listing":
        start_date = _resolve_saved_report_start_date(definition, db, codes)
        probed_html = None

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

    safe_filename = f"{slug}.csv"
    if filename:
        safe_filename = filename.replace("pbs_report_chart", slug)
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename=\"{safe_filename}\"'},
    )


@router.get("/web/saved-reports/{slug}.json")
def saved_report_json(request: Request, slug: str, db: Session = Depends(get_db)):
    definition = get_saved_report(slug)
    if not definition:
        raise HTTPException(status_code=404, detail="Saved report not found")
    if not can_view_saved_report(definition, _request_username(request), _request_role(request)):
        raise HTTPException(status_code=403, detail="You do not have permission to use this saved report")

    codes = _resolve_saved_report_codes_for_run(definition, db, limit=25)
    report = definition.get("report", {}) or {}
    start_date = end_date = None
    if codes and len(codes) <= 20:
        start_date, end_date = _resolve_saved_report_window(definition, db, codes)

    payload = {
        "slug": slug,
        "name": definition.get("name") or slug,
        "description": definition.get("description") or "",
        "source_type": definition.get("source_type", "search_based"),
        "search": definition.get("search", {}) or {},
        "report": report,
        "resolved_codes": codes,
        "resolved_code_count": len(codes),
        "start_date": start_date,
        "end_date": end_date,
        "cached_validation": definition.get("cached_validation", {}) or {},
    }
    return Response(content=json.dumps(payload, indent=2), media_type="application/json")

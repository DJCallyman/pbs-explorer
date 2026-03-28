from __future__ import annotations

from services.medicine_status.parser import parse_detail_page, parse_search_page


def test_parse_search_page_extracts_embedded_results() -> None:
    html = """
    <search-result :result="{&quot;page&quot;:1,&quot;totalPages&quot;:12,&quot;totalResults&quot;:1177,&quot;results&quot;:[{&quot;psid&quot;:&quot;1341&quot;,&quot;pspropertyDrugName&quot;:&quot;PEMBROLIZUMAB&quot;,&quot;pspropertyBrandNames&quot;:&quot;Keytruda®&quot;,&quot;pspropertySponsors&quot;:&quot;MERCK&quot;,&quot;pspropertyPurpose&quot;:&quot;Cervical cancer&quot;,&quot;pspropertyMeetingDate&quot;:&quot;20250312&quot;,&quot;pspropertyMeetingDatepspropertyFormattedMeetingDate&quot;:&quot;March 2025&quot;,&quot;pspropertyPbacOutcomeStatus&quot;:&quot;Recommended&quot;}]}"></search-result>
    """

    parsed = parse_search_page(html)

    assert parsed.page == 1
    assert parsed.total_pages == 12
    assert parsed.total_results == 1177
    assert len(parsed.entries) == 1
    assert parsed.entries[0].medicine_status_id == "1341"
    assert parsed.entries[0].document_url.endswith("/medicinestatus/document/1341.html")
    assert parsed.entries[0].meeting_date.isoformat() == "2025-03-12"
    assert parsed.entries[0].listing_outcome_status == "Recommended"


def test_parse_detail_page_extracts_pbac_fields() -> None:
    html = """
    <h1 class="h1">PEMBROLIZUMAB</h1>
    <dl class="au-dl">
      <dt class="col-sm-3 au-dl__title">Brand name:</dt>
      <dd class="col-sm-9 au-dl__description">Keytruda®</dd>
      <dt class="col-sm-3 au-dl__title">Condition/indication:<br>(therapeutic use)</dt>
      <dd class="col-sm-9 au-dl__description">Cervical cancer</dd>
      <dt class="col-sm-3 au-dl__title">Submission sponsor:</dt>
      <dd class="col-sm-9 au-dl__description">MERCK</dd>
      <dt class="col-sm-3 au-dl__title"><b>Submission received for:</b></dt>
      <dd class="col-sm-9 au-dl__description">March 2025 PBAC meeting</dd>
      <dt class="col-sm-3 au-dl__title"><b>PBAC meeting:</b></dt>
      <dd class="col-sm-9 au-dl__description">Held on 12/03/2025</dd>
      <dt class="col-sm-3 au-dl__title"><b>PBAC outcome published:</b></dt>
      <dd class="col-sm-9 au-dl__description">Recommended (see <a href="/info/outcomes">PBAC Outcomes</a>)</dd>
      <dt class="col-sm-3 au-dl__title">Status:</dt>
      <dd class="col-sm-9 au-dl__description">Finalised</dd>
      <dt class="col-sm-3 au-dl__title">Public Summary Document:</dt>
      <dd class="col-sm-9 au-dl__description"><a href="/info/psd/march-2025">PBAC Public Summary Documents – March 2025</a></dd>
      <dt class="col-sm-3 au-dl__title">Page last updated:</dt>
      <dd class="col-sm-9 au-dl__description">31 January 2026</dd>
    </dl>
    """

    parsed = parse_detail_page(html)

    assert parsed.drug_name == "PEMBROLIZUMAB"
    assert parsed.pbac_meeting_date.isoformat() == "2025-03-12"
    assert parsed.pbac_outcome_published_text == "Recommended (see PBAC Outcomes)"
    assert parsed.pbac_outcome_published_url == "https://www.pbs.gov.au/info/outcomes"
    assert parsed.public_summary_title == "PBAC Public Summary Documents – March 2025"
    assert parsed.public_summary_url == "https://www.pbs.gov.au/info/psd/march-2025"
    assert parsed.status == "Finalised"
    assert parsed.page_last_updated.isoformat() == "2026-01-31"

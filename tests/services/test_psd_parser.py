from __future__ import annotations

from services.psd.parser import extract_page_last_updated, is_product_page, parse_psd_page


def test_extract_page_last_updated() -> None:
    html = """
    <html>
      <body>
        <p>Page last updated: 6 March 2026</p>
      </body>
    </html>
    """

    assert extract_page_last_updated(html) == "6 March 2026"


def test_parse_psd_index_page_collects_listing_links() -> None:
    html = """
    <html>
      <body>
        <a href="/info/industry/listing/elements/pbac-meetings/psd/public-summary-documents-by-product">By product</a>
        <a href="/info/industry/listing/elements/pbac-meetings/psd/pbac-public-summary-documents-november-2025">November 2025</a>
        <a href="https://www.pbs.gov.au/files/example.pdf">PDF</a>
      </body>
    </html>
    """

    parsed = parse_psd_page("https://www.pbs.gov.au/info/industry/listing/elements/pbac-meetings/psd", html)

    assert parsed.links == [
        "https://www.pbs.gov.au/info/industry/listing/elements/pbac-meetings/psd/public-summary-documents-by-product",
        "https://www.pbs.gov.au/info/industry/listing/elements/pbac-meetings/psd/pbac-public-summary-documents-november-2025",
    ]
    assert parsed.document_links == ["https://www.pbs.gov.au/files/example.pdf"]


def test_parse_psd_primary_index_ignores_meeting_indexes() -> None:
    html = """
    <html>
      <body>
        <a href="/info/industry/listing/elements/pbac-meetings/psd/pbac-public-summary-documents-november-2025">Meeting page</a>
        <a href="/info/industry/listing/elements/pbac-meetings/psd/2024-11/vutrisiran-PSD-November-2024">Product page</a>
      </body>
    </html>
    """

    parsed = parse_psd_page(
        "https://www.pbs.gov.au/info/industry/listing/elements/pbac-meetings/psd/public-summary-documents-by-product",
        html,
    )

    assert parsed.links == [
        "https://www.pbs.gov.au/info/industry/listing/elements/pbac-meetings/psd/2024-11/vutrisiran-PSD-November-2024",
    ]


def test_parse_product_page_collects_document_links() -> None:
    html = """
    <html>
      <body>
        <a href="/info/industry/listing/elements/pbac-meetings/psd/2024-11/vutrisiran-PSD-November-2024">
          Product page
        </a>
        <a href="https://www.pbs.gov.au/industry/listing/elements/pbac-meetings/psd/files/vutrisiran.pdf">
          PDF
        </a>
        <a href="https://www.pbs.gov.au/industry/listing/elements/pbac-meetings/psd/files/vutrisiran.docx">
          Word
        </a>
      </body>
    </html>
    """

    parsed = parse_psd_page(
        "https://www.pbs.gov.au/info/industry/listing/elements/pbac-meetings/psd/2024-11/vutrisiran-PSD-November-2024",
        html,
    )

    assert parsed.document_links == [
        "https://www.pbs.gov.au/industry/listing/elements/pbac-meetings/psd/files/vutrisiran.pdf",
        "https://www.pbs.gov.au/industry/listing/elements/pbac-meetings/psd/files/vutrisiran.docx",
    ]


def test_is_product_page() -> None:
    assert is_product_page(
        "https://www.pbs.gov.au/info/industry/listing/elements/pbac-meetings/psd/2024-11/vutrisiran-PSD-November-2024"
    )
    assert not is_product_page(
        "https://www.pbs.gov.au/info/industry/listing/elements/pbac-meetings/psd/pbac-public-summary-documents-november-2025"
    )


def test_parse_dusc_index_page_collects_listing_links() -> None:
    html = """
    <html>
      <body>
        <a href="/info/industry/listing/participants/public-release-docs/dusc-public-release-documents-by-condition">By condition</a>
        <a href="/info/industry/listing/participants/public-release-docs/dusc-public-release-documents-by-meeting">By meeting</a>
        <a href="/info/industry/listing/participants/public-release-docs/daratumumab-al-amyloidosis">Item page</a>
      </body>
    </html>
    """

    parsed = parse_psd_page(
        "https://www.pbs.gov.au/info/industry/listing/participants/public-release-docs/dusc-public-release-documents-by-medicine",
        html,
    )

    assert parsed.source == "DUSC"
    assert parsed.links == [
        "https://www.pbs.gov.au/info/industry/listing/participants/public-release-docs/daratumumab-al-amyloidosis",
    ]


def test_dusc_item_page_is_product_page() -> None:
    assert is_product_page(
        "https://www.pbs.gov.au/info/industry/listing/participants/public-release-docs/daratumumab-al-amyloidosis"
    )

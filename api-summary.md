# PBS Public Data API Summary

The **PBS Public Data API** is a Postman collection for accessing the Pharmaceutical Benefits Scheme (PBS) data from the Australian Department of Health. It provides programmatic access to detailed information about subsidized medicines, pricing, restrictions, and related entities. The collection is based on the official PBS API (v3) and includes 35 GET endpoints.

## Key Details
- **Base URL**: `https://data-api.health.gov.au/pbs/api/v3/`
- **Authentication**: Requires a `subscription-key` header (stored as a collection variable: `2384af7c667342ceb5a736fe29f1dc6b`).
- **Response Format**: Primarily CSV (via `Accept: text/csv` header), though some endpoints may support JSON.
- **Common Query Parameters**:
  - `schedule_code`: Filters data by a specific PBS schedule (e.g., set dynamically from the `/schedules` endpoint).
  - `limit`: Limits the number of results (default: 100,000 in the collection).
- **Collection Variables**:
  - `subscription-key`: API key for authentication.
  - `schedule_code`: Dynamically set to the latest schedule code (e.g., 3922) via a test script on the `/schedules` endpoint.
  - `limit`: Result limit (e.g., 100,000).
- **Structure**: All requests are at the root level (no folders). The first request (`/schedules`) includes a test script to extract and set the `schedule_code` variable for subsequent calls.

## API Endpoints and Methods
All endpoints use **GET** method and follow a consistent pattern: base URL + endpoint + query params. Here's a categorized summary:

### 1. Core Data Entities
- `/schedules`: Retrieves PBS schedules (e.g., pricing periods). Includes a test script to set `schedule_code`.
- `/items`: Core PBS items (medicines/products).
- `/organisations`: Organizations involved (e.g., manufacturers).
- `/containers`: Packaging/container details.
- `/programs`: PBS programs or schemes.

### 2. Pricing and Fees
- `/copayments`: Patient copayment amounts.
- `/fees`: Dispensing fees.
- `/item-pricing-events`: Historical pricing changes.
- `/markup-bands`: Pricing markup bands.
- `/extemporaneous-tariffs`: Tariffs for extemporaneous preparations.

### 3. Restrictions and Criteria
- `/restrictions`: PBS restrictions on prescribing.
- `/criteria`: Criteria for restrictions.
- `/parameters`: Parameters for criteria.
- `/indications`: Approved indications for items.
- `/prescribing-texts`: Prescribing guidelines.
- `/prescribers`: Authorized prescribers.

### 4. Relationships and Classifications
- `/atc-codes`: Anatomical Therapeutic Chemical (ATC) classifications.
- `/item-atc-relationships`: Links items to ATC codes.
- `/item-organisation-relationships`: Links items to organizations.
- `/item-restriction-relationships`: Links items to restrictions.
- `/item-prescribing-text-relationships`: Links items to prescribing texts.
- `/restriction-prescribing-text-relationships`: Links restrictions to texts.
- `/criteria-parameter-relationships`: Links criteria to parameters.
- `/container-organisation-relationships`: Links containers to organizations.

### 5. Dispensing and Preparations
- `/dispensing-rules`: Rules for dispensing.
- `/item-dispensing-rule-relationships`: Links items to dispensing rules.
- `/amt-items`: Australian Medicines Terminology (AMT) items.
- `/extemporaneous-preparations`: Extemporaneous (compounded) preparations.
- `/extemporaneous-ingredients`: Ingredients for extemporaneous prep.
- `/extemporaneous-prep-sfp-relationships`: Links to standard formula preparations.
- `/standard-formula-preparations`: Standard formula preparations.

### 6. Other
- `/summary-of-changes`: Summary of PBS changes.

## Usage Notes
- **Workflow**: Start with `/schedules` to get the latest schedule code, then query other endpoints with that code.
- **Data Volume**: Many endpoints support high limits (e.g., 100,000), indicating large datasets.
- **Purpose**: This API enables analysis of PBS data for research, compliance, or integration into health systems. Data includes pricing, restrictions, and classifications for subsidized medicines in Australia.
- **Forked Collection**: This is a fork of an original collection (from user 33098837), last updated in 2024.
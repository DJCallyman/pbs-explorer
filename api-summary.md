# PBS API Summary

## Key Details
- **Base URL**: `https://data-api.health.gov.au/pbs/api/v3/`
- **Authentication**: Requires a `subscription-key` header. See `.env.example` for configuration.
- **Response Format**: Primarily CSV (via `Accept: text/csv` header), though some endpoints may support JSON.
- **Common Query Parameters**:
  - `schedule_code`: Filters data by a specific PBS schedule (e.g., set dynamically from the `/schedules` endpoint).
  - `limit`: Limits the number of results (default: 100,000 in the collection).
- **Collection Variables**:
  - `subscription-key`: API key for authentication.
  - `schedule_code`: Dynamically set to the latest schedule code (e.g., 3922) via a test script on the `/schedules` endpoint.
  - `limit`: Result limit (e.g., 100,000).
- **Structure**: All requests are at the root level (no folders). The first request (`/schedules`) includes a test script to extract and set the `schedule_code` variable for subsequent calls.

## API Endpoints

### 1. Core Data Entities
- `/schedules`: Retrieves PBS schedules (e.g., pricing periods). Includes a test script to set `schedule_code`.
- `/items`: Core PBS items (medicines/products).
- `/organisations`: Organizations involved (e.g., manufacturers).
- `/containers`: Packaging/container details.
- `/programs`: PBS programs or schemes.

### 2. Classifications & Rules
- `/atc-codes`: ATC classification codes and hierarchy.
- `/dispensing-rules`: Rules for dispensing PBS items.
- `/criteria`: Criteria related to restrictions.
- `/parameters`: Parameter definitions for criteria.

### 3. Restrictions & Texts
- `/restrictions`: PBS prescribing restrictions.
- `/prescribing-texts`: Prescribing notes and guidance.
- `/indications`: Clinical indications related to restrictions.

### 4. Financial & Pricing
- `/copayments`: Patient co-payment amounts.
- `/fees`: Dispensing fees and related charges.
- `/item-pricing-events`: Historical pricing events for items.
- `/markup-bands`: Price markup bands.

### 5. Relationships
- `/item-atc-relationships`: Links between items and ATC codes.
- `/item-organisation-relationships`: Links between items and organisations.
- `/item-restriction-relationships`: Links between items and restrictions.
- `/item-dispensing-rule-relationships`: Links between items and dispensing rules.
- `/item-prescribing-text-relationships`: Links between items and prescribing texts.
- `/restriction-prescribing-text-relationships`: Links between restrictions and prescribing texts.
- `/criteria-parameter-relationships`: Links between restriction criteria and parameters.
- `/container-organisation-relationships`: Links between containers and organisations.

### 6. Other / Supplementary Data
- `/amt-items`: Australian Medicines Terminology (AMT) items.
- `/extemporaneous-preparations`: Compounded preparation data.
- `/extemporaneous-ingredients`: Ingredients used in compounded preparations.
- `/extemporaneous-tariffs`: Pricing for compounded preparations.
- `/standard-formula-preparations`: Standard formula preparations.
- `/prescribers`: Authorized prescriber information.
- `/summary-of-changes`: Summary of PBS changes across schedules.

## Usage Notes
- **Workflow**: Start with `/schedules` to get the latest schedule code, then query other endpoints with that code.
- **Data Volume**: Many endpoints support high limits (e.g., 100,000), indicating large datasets.
- **Purpose**: This API enables analysis of PBS data for research, compliance, or integration into health systems. Data includes pricing, restrictions, and classifications for subsidized medicines in Australia.
- **Forked Collection**: This is a fork of an original collection (from user 33098837), last updated in 2024.

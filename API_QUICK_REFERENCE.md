# PBS API Quick Reference Guide

## Server Status
- **URL**: `http://localhost:8000`
- **Status**: ✅ Running
- **Rate Limiting**: 2-second delays between PBS API calls
- **Caching**: 24-hour TTL with 201,811 items cached

## Core Endpoints

### 1. Search Earliest Listing
Find when a drug first appeared in PBS

```bash
GET /api/search/earliest-listing?q=paracetamol
```

**Parameters**:
- `q` (required): Drug name (max 200 chars, SQL injection protected)

**Response**:
```json
{
  "count": 2,
  "query": "paracetamol",
  "results": [
    {
      "drug_name": "Paracetamol",
      "earliest_pbs_code": "10582Y",
      "earliest_listing_date": "2025-02-01",
      "earliest_schedule_code": "3571",
      "all_pbs_codes": [...],
      "all_schedules": [...]
    }
  ]
}
```

### 2. Search Incidents
Find drugs involved in change incidents

```bash
GET /api/search/incidents?q=atorvastatin&incident=12345
```

**Parameters**:
- `q` (optional): Drug name
- `incident` (optional): Incident number

**Response**: Array of incidents matching query

### 3. Item Price History
Get pricing changes for a PBS code

```bash
GET /api/item-price-history/10582Y
```

**Parameters**:
- PBS Code (alphanumeric, max 10 chars) - in URL path

**Status Codes**:
- `200 OK`: Success
- `400 Bad Request`: Invalid PBS code

**Response**:
```json
{
  "pbs_code": "10582Y",
  "count": 5,
  "events": [...]
}
```

### 4. Item Full Profile
Get comprehensive information about a PBS code

```bash
GET /api/item-profile/10582Y?schedule_code=4580
```

**Parameters**:
- PBS Code (in URL path)
- `schedule_code` (optional): Filter by specific schedule

**Status Codes**:
- `200 OK`: Success
- `400 Bad Request`: Invalid code

**Response**: Complete item details including:
- Drug information
- Pricing details
- Manufacturer details
- Restriction codes
- Medical chart eligibility

### 5. ATC Hierarchy
Get ATC (Anatomical Therapeutic Chemical) classifications

```bash
GET /api/atc-hierarchy
```

**Response**: Hierarchical ATC code structure

### 6. Manufacturer Portfolio
Find items by manufacturer organization

```bash
GET /api/manufacturer-portfolio?org_name=Pfizer
```

**Parameters**:
- `org_name` (required): Organization name (max 200 chars)

**Response**: Array of items manufactured by organization

### 7. Compare Schedules
Find items across multiple schedules

```bash
GET /api/compare-schedules?schedules=4580,4581
```

**Parameters**:
- `schedules` (required): Comma-separated schedule codes (min 2)

**Status Codes**:
- `200 OK`: Success (≥2 valid codes)
- `400 Bad Request`: Fewer than 2 valid codes

**Response**:
```json
{
  "schedules": ["4580", "4581"],
  "total_unique_items": 6899,
  "items_in_all": [...],
  "items_in_only_4580": [...],
  "items_in_only_4581": [...]
}
```

### 8. Recent Changes
Get recent changes across all schedules

```bash
GET /api/recent-changes?limit=100&change_type=UPDATE
```

**Parameters**:
- `limit` (optional): Number of results (1-1000, default: 100)
- `change_type` (optional): Filter by change type (INSERT, UPDATE, DELETE)

**Response**: Array of recent changes sorted by date (descending)

## Administrative Endpoints

### Cache Statistics
```bash
GET /api/cache/stats
```

**Response**:
```json
{
  "total_items": 201811,
  "schedules_cached": 14,
  "cache_ttl_hours": 24
}
```

### Clear Cache
```bash
DELETE /api/cache/clear
```

## Input Validation Rules

### Query Parameters (Drug Names, Org Names, etc.)
- **Max Length**: 200 characters
- **Blocked Characters**: `'`, `"`, `;`, `--`, `/*`, `*/`, `xp_`, `sp_`
- **Behavior**: Invalid queries return empty results (status 200)

### PBS Codes
- **Format**: Alphanumeric only
- **Max Length**: 10 characters
- **Normalization**: Converted to UPPERCASE
- **Validation Failure**: Returns HTTP 400

**Examples**:
- ✅ Valid: `10582Y`, `12022R`, `14709E`
- ❌ Invalid: `12345678901` (too long), `CODE-123` (contains dash)

### Schedule Codes
- **Format**: Alphanumeric only
- **Max Length**: 20 characters
- **Normalization**: Converted to UPPERCASE
- **Minimum Count**: Compare-schedules requires ≥2 valid codes

**Examples**:
- ✅ Valid: `4580`, `4581`, `3571`
- ❌ Invalid: `SCH-4580` (contains dash)

### Limit Parameter
- **Type**: Integer
- **Range**: 1-1000
- **Default**: 100
- **Behavior**: Auto-clamped to valid range
- **Invalid Values**: Integer parsing errors default to 100

## Date Formats Supported

The API normalizes all dates to **YYYY-MM-DD** format:

- ✅ `2025-02-01` (ISO 8601)
- ✅ `01/02/2025` (DD/MM/YYYY)
- ✅ `2025/02/01` (YYYY/MM/DD)
- ✅ `01-02-2025` (DD-MM-YYYY)

**Note**: Dates from PBS API are automatically converted

## Error Handling

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Query accepted and processed |
| 400 | Bad Request | Invalid PBS code format |
| 404 | Not Found | Endpoint doesn't exist |
| 500 | Server Error | PBS API unavailable |

### Error Response Format

```json
{
  "error": "Invalid PBS code"
}
```

## Security Features

### SQL Injection Prevention
- All queries validated against dangerous characters
- Maximum query length enforced (200 chars)
- Failed validation returns empty results

### Input Bounds
- PBS codes: max 10 characters
- Schedule codes: max 20 characters
- Query strings: max 200 characters
- Limit parameter: clamped to [1, 1000]

### Type Safety
- All parameters type-checked before processing
- Null/empty values handled gracefully
- Safe defaults for missing data

## Performance Tips

1. **Use Specific Queries**: "paracetamol" instead of "para"
2. **Check Cache Stats**: `/api/cache/stats` shows what's cached
3. **Batch Operations**: Limit multiple requests if possible
4. **Schedule Codes**: Pre-validate schedule codes before compare

## Debugging

### Enable Verbose Output
Server logs HTTP requests and CSV operations:

```
✓ items cached (14598 rows)
CSV headers: li_item_id, drug_name, li_drug_name, li_form...
127.0.0.1 - - [18/Jan/2026 01:21:16] "GET /api/search... HTTP/1.1" 200
```

### Common Issues

**Slow Response?**
- First request to an endpoint caches data (~1-2 minutes)
- Subsequent requests use cache (instant)
- Check `/api/cache/stats` to verify caching

**Empty Results?**
- Check query spelling
- Verify parameters aren't exceeding limits
- Some drugs may not have data for requested schedule

**400 Bad Request?**
- Verify PBS/schedule codes contain only alphanumeric characters
- Check code length (PBS: ≤10 chars, Schedule: ≤20 chars)
- For compare-schedules, ensure ≥2 valid codes provided

## Frontend Integration

The included `index.html` provides a web interface with 8 tabs:
1. Search Earliest Listing
2. Search Incidents
3. Item Price History
4. Item Profile
5. ATC Hierarchy
6. Manufacturer Portfolio
7. Compare Schedules
8. Recent Changes

**Access**: Open `http://localhost:8000` in browser

## API Evolution

**Latest Improvements** (January 18, 2026):
- ✅ Defensive field access (`safe_get()`)
- ✅ Flexible date parsing
- ✅ SQL injection prevention
- ✅ Input validation on all endpoints
- ✅ CSV header validation and logging
- ✅ Limit parameter clamping
- ✅ Type-safe error handling

## Support

For issues or questions:
1. Check server logs for error messages
2. Verify input parameters match validation rules
3. Test with `/api/cache/stats` to verify data availability
4. Check PBS API rate limiting (⚠ messages in logs)

---
**Last Updated**: January 18, 2026
**API Version**: v3 Enhanced with Defensive Programming

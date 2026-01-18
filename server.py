#!/usr/bin/env python3
"""
Enhanced PBS API server with caching, data joining, and advanced search endpoints.
Run this script and open http://localhost:8000 in your browser.
"""

import http.server
import socketserver
import urllib.request
import urllib.error
import urllib.parse
import os
import json
import csv
import io
import time
import re
import signal
import sys
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Optional

PORT = 8000
API_BASE = 'https://data-api.health.gov.au/pbs/api/v3/'
SUBSCRIPTION_KEY = '2384af7c667342ceb5a736fe29f1dc6b'

# Rate limiting: Wait time between API requests to avoid 429s
API_REQUEST_DELAY = 2  # seconds between requests

# ============================================================================
# In-Memory Cache Layer
# ============================================================================

class DataCache:
    """In-memory cache with TTL support for PBS API data."""
    
    def __init__(self, default_ttl: int = 3600):  # 1 hour default TTL
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached data if not expired."""
        if key in self._cache:
            entry = self._cache[key]
            if time.time() < entry['expires']:
                return entry['data']
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """Cache data with optional custom TTL."""
        self._cache[key] = {
            'data': data,
            'expires': time.time() + (ttl or self._default_ttl),
            'cached_at': time.time()
        }
    
    def clear(self, key: Optional[str] = None) -> None:
        """Clear specific key or entire cache."""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        now = time.time()
        return {
            'total_keys': len(self._cache),
            'keys': list(self._cache.keys()),
            'entries': {
                k: {
                    'cached_at': datetime.fromtimestamp(v['cached_at']).isoformat(),
                    'expires_in_seconds': max(0, int(v['expires'] - now)),
                    'row_count': len(v['data']) if isinstance(v['data'], list) else 'N/A'
                }
                for k, v in self._cache.items()
            }
        }

# Global cache instance
cache = DataCache(default_ttl=86400)  # 24 hour default TTL

# ============================================================================
# API Fetching Utilities
# ============================================================================

# Track last request time for rate limiting
_last_request_time = 0
_rate_limit_lock = None

def respect_rate_limit():
    """Wait if necessary to respect API rate limits."""
    global _last_request_time
    time_since_last = time.time() - _last_request_time
    if time_since_last < API_REQUEST_DELAY:
        wait_time = API_REQUEST_DELAY - time_since_last
        print(f"⏱ Rate limiting: waiting {wait_time:.1f}s...")
        time.sleep(wait_time)
    _last_request_time = time.time()

def fetch_api_csv(endpoint: str, params: Optional[Dict[str, str]] = None, retries: int = 3, timeout: int = 120) -> str:
    """Fetch CSV data from PBS API with retry logic and rate limiting."""
    url = API_BASE + endpoint
    if params:
        url += '?' + urllib.parse.urlencode(params)
    
    last_error = None
    for attempt in range(retries):
        try:
            # Respect rate limits before making request
            respect_rate_limit()
            
            print(f"Fetching {endpoint} (attempt {attempt + 1}/{retries}, timeout={timeout}s)...")
            req = urllib.request.Request(url, headers={
                'Accept': 'text/csv',
                'subscription-key': SUBSCRIPTION_KEY
            })
            
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = response.read().decode('utf-8')
                if attempt > 0:
                    print(f"✓ {endpoint} fetched successfully on retry {attempt}")
                return data
                
        except urllib.error.HTTPError as e:
            # Handle rate limiting specifically
            if e.code == 429:
                # Rate limited - wait longer and retry
                last_error = e
                wait_time = 60 * (attempt + 1)  # 60s, 120s, 180s
                print(f"⚠ Rate limited (429). Waiting {wait_time}s before retry {attempt + 1}/{retries}...")
                time.sleep(wait_time)
            else:
                # Other HTTP errors
                last_error = e
                if attempt < retries - 1:
                    wait_time = 5 * (attempt + 1)
                    print(f"⚠ {endpoint} failed: HTTP {e.code}... Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"✗ {endpoint} failed with HTTP {e.code}")
                    
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_error = e
            if attempt < retries - 1:
                wait_time = 5 * (attempt + 1)
                print(f"⚠ {endpoint} failed: {str(e)[:100]}... Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"✗ {endpoint} failed after {retries} attempts")
    
    raise last_error or Exception(f"Failed to fetch {endpoint} after {retries} retries")

def fetch_api_json(endpoint: str, params: Optional[Dict[str, str]] = None) -> Any:
    """Fetch JSON data from PBS API."""
    url = API_BASE + endpoint
    if params:
        url += '?' + urllib.parse.urlencode(params)
    
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'subscription-key': SUBSCRIPTION_KEY
    })
    
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode('utf-8'))

def parse_csv_to_list(csv_text: str) -> List[Dict[str, str]]:
    """Parse CSV text into list of dictionaries with validation."""
    if not csv_text.strip():
        return []
    
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None or len(reader.fieldnames) == 0:
        print(f"⚠ CSV has no headers, skipping")
        return []
    
    print(f"  CSV headers: {', '.join(reader.fieldnames[:5])}{'...' if len(reader.fieldnames) > 5 else ''}")
    
    data = []
    for row in reader:
        # Skip empty rows
        if any(v for v in row.values() if v and v.strip()):
            data.append(row)
    
    return data

def safe_get(obj: Dict[str, Any], *keys, default: Any = None) -> Any:
    """Safely get nested values with fallback to multiple possible keys."""
    if not obj:
        return default
    for key in keys:
        if isinstance(obj, dict) and key in obj:
            val = obj[key]
            if val and (isinstance(val, str) and val.strip() or not isinstance(val, str)):
                return val
    return default

def parse_date(date_str: Optional[str]) -> str:
    """Parse various date formats from PBS API with fallbacks."""
    if not date_str or not isinstance(date_str, str) or not date_str.strip():
        return ""
    
    date_str = date_str.strip()
    
    # Try common formats
    formats = [
        "%Y-%m-%d",      # 2024-01-15
        "%d/%m/%Y",      # 15/01/2024
        "%Y/%m/%d",      # 2024/01/15
        "%d-%m-%Y",      # 15-01-2024
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If none match, return as-is (might be partial or special format)
    return date_str

def validate_schedule_code(code: Optional[str]) -> str:
    """Validate and clean a schedule code."""
    if not code or not isinstance(code, str):
        return ""
    code = code.strip().upper()
    # Schedule codes should be alphanumeric, max 20 chars
    if not code or len(code) > 20 or not code.replace(' ', '').isalnum():
        return ""
    return code

def validate_pbs_code(code: Optional[str]) -> str:
    """Validate and clean a PBS code."""
    if not code or not isinstance(code, str):
        return ""
    code = code.strip().upper()
    # PBS codes are typically numeric or alphanumeric, max 10 chars
    if not code or len(code) > 10:
        return ""
    return code

def validate_query(query: Optional[str], max_length: int = 200) -> str:
    """Validate and clean a search query."""
    if not query or not isinstance(query, str):
        return ""
    query = query.strip()
    # Prevent very long queries
    if len(query) > max_length:
        query = query[:max_length]
    # Basic SQL injection prevention - reject queries with suspicious chars
    dangerous = ["'", '"', ";", "--", "/*", "*/", "xp_", "sp_"]
    for danger in dangerous:
        if danger in query:
            return ""
    return query

def fetch_and_cache(endpoint: str, params: Optional[Dict[str, str]] = None, 
                    cache_key: Optional[str] = None, timeout: int = 120) -> List[Dict[str, str]]:
    """Fetch data from API with caching support."""
    key = cache_key or f"{endpoint}:{json.dumps(params or {}, sort_keys=True)}"
    
    cached = cache.get(key)
    if cached is not None:
        print(f"✓ {endpoint} loaded from cache")
        return cached
    
    csv_text = fetch_api_csv(endpoint, params, timeout=timeout)
    data = parse_csv_to_list(csv_text)
    cache.set(key, data)
    print(f"✓ {endpoint} cached ({len(data)} rows)")
    return data

# ============================================================================
# Data Loading Functions
# ============================================================================

def load_schedules() -> List[Dict[str, str]]:
    """Load all schedules."""
    return fetch_and_cache('schedules', {'limit': '1000'}, 'schedules')

def load_items(schedule_code: Optional[str] = None) -> List[Dict[str, str]]:
    """Load items, optionally filtered by schedule."""
    params = {'limit': '200000'}
    if schedule_code:
        params['schedule_code'] = schedule_code
    cache_key = f"items:{schedule_code or 'all'}"
    return fetch_and_cache('items', params, cache_key)

def load_organisations() -> List[Dict[str, str]]:
    """Load all organisations."""
    return fetch_and_cache('organisations', {'limit': '10000'}, 'organisations')

def load_atc_codes() -> List[Dict[str, str]]:
    """Load all ATC codes."""
    return fetch_and_cache('atc-codes', {'limit': '50000'}, 'atc-codes')

def load_item_atc_relationships(schedule_code: Optional[str] = None) -> List[Dict[str, str]]:
    """Load item-ATC relationships."""
    params = {'limit': '500000'}
    if schedule_code:
        params['schedule_code'] = schedule_code
    cache_key = f"item-atc-rel:{schedule_code or 'all'}"
    return fetch_and_cache('item-atc-relationships', params, cache_key)

def load_item_org_relationships(schedule_code: Optional[str] = None) -> List[Dict[str, str]]:
    """Load item-organisation relationships."""
    params = {'limit': '500000'}
    if schedule_code:
        params['schedule_code'] = schedule_code
    cache_key = f"item-org-rel:{schedule_code or 'all'}"
    return fetch_and_cache('item-organisation-relationships', params, cache_key)

def load_restrictions(schedule_code: Optional[str] = None) -> List[Dict[str, str]]:
    """Load restrictions."""
    params = {'limit': '100000'}
    if schedule_code:
        params['schedule_code'] = schedule_code
    cache_key = f"restrictions:{schedule_code or 'all'}"
    return fetch_and_cache('restrictions', params, cache_key)

def load_item_restriction_relationships(schedule_code: Optional[str] = None) -> List[Dict[str, str]]:
    """Load item-restriction relationships."""
    params = {'limit': '500000'}
    if schedule_code:
        params['schedule_code'] = schedule_code
    cache_key = f"item-restr-rel:{schedule_code or 'all'}"
    return fetch_and_cache('item-restriction-relationships', params, cache_key)

def load_summary_of_changes() -> List[Dict[str, str]]:
    """Load summary of changes (for incident numbers)."""
    # Note: summary-of-changes can be very large, limit to 50000 to avoid timeouts
    return fetch_and_cache('summary-of-changes', {'limit': '50000'}, 'summary-of-changes', timeout=180)

def load_item_pricing_events(schedule_code: Optional[str] = None) -> List[Dict[str, str]]:
    """Load item pricing events."""
    params = {'limit': '500000'}
    if schedule_code:
        params['schedule_code'] = schedule_code
    cache_key = f"item-pricing-events:{schedule_code or 'all'}"
    return fetch_and_cache('item-pricing-events', params, cache_key, timeout=180)

# ============================================================================
# Search and Join Functions
# ============================================================================

def search_earliest_listing(query: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Find the earliest listing date for PBS medicines.
    Queries ALL schedules to find when each medicine was first ever listed on PBS.
    """
    schedules = load_schedules()
    schedule_map = {}
    for s in schedules:
        code = safe_get(s, 'schedule_code', default='')
        if code:
            schedule_map[code] = s
    
    # Get items from ALL schedules to find true historical earliest listing
    # Note: This may take a while due to rate limiting (2s between requests)
    all_items = []
    print(f"Searching earliest listing across {len(schedules)} schedules (may take 1-2 min)...")
    for i, schedule in enumerate(schedules):
        schedule_code = safe_get(schedule, 'schedule_code', default='')
        if schedule_code:
            try:
                schedule_items = load_items(schedule_code)
                all_items.extend(schedule_items)
                print(f"  [{i+1}/{len(schedules)}] ✓ Schedule {schedule_code}: {len(schedule_items)} items")
            except Exception as e:
                print(f"  [{i+1}/{len(schedules)}] ✗ Schedule {schedule_code}: {str(e)[:100]}")
                # Continue with other schedules
                continue
    
    print(f"Total items collected: {len(all_items)}")
    
    # Group by drug identifier (li_drug_name or drug_name)
    drug_listings: Dict[str, Dict[str, Any]] = {}
    
    for item in all_items:
        # Try multiple fields for drug identification with safe_get
        drug_name = safe_get(item, 'li_drug_name', 'drug_name', 'mp_pt', default='')
        pbs_code = safe_get(item, 'pbs_code', default='')
        schedule_code = safe_get(item, 'schedule_code', default='')
        
        if not drug_name:
            continue
        
        # Get effective date from schedule
        schedule_info = schedule_map.get(schedule_code, {})
        effective_date = safe_get(schedule_info, 'effective_date', default='')
        
        # Use listing date from item if available, otherwise schedule effective date
        listing_date = safe_get(item, 'listing_date', default='') or effective_date
        listing_date = parse_date(listing_date)
        
        # Create a key for grouping (normalized drug name)
        drug_key = drug_name.lower().strip()
        
        if drug_key not in drug_listings:
            drug_listings[drug_key] = {
                'drug_name': drug_name,
                'earliest_pbs_code': pbs_code,
                'earliest_listing_date': listing_date,
                'earliest_schedule_code': schedule_code,
                'schedule_name': safe_get(schedule_info, 'schedule_name', default=''),
                'all_pbs_codes': [pbs_code] if pbs_code else [],
                'all_schedules': [schedule_code] if schedule_code else []
            }
        else:
            existing = drug_listings[drug_key]
            if pbs_code and pbs_code not in existing['all_pbs_codes']:
                existing['all_pbs_codes'].append(pbs_code)
            if schedule_code and schedule_code not in existing['all_schedules']:
                existing['all_schedules'].append(schedule_code)
            
            # Update if this listing is earlier (better logic for missing dates)
            if listing_date:
                if not existing['earliest_listing_date']:
                    existing['earliest_listing_date'] = listing_date
                    existing['earliest_pbs_code'] = pbs_code
                    existing['earliest_schedule_code'] = schedule_code
                    existing['schedule_name'] = safe_get(schedule_info, 'schedule_name', default='')
                elif listing_date < existing['earliest_listing_date']:
                    existing['earliest_listing_date'] = listing_date
                    existing['earliest_pbs_code'] = pbs_code
                    existing['earliest_schedule_code'] = schedule_code
                    existing['schedule_name'] = safe_get(schedule_info, 'schedule_name', default='')
    
    results = list(drug_listings.values())
    
    # Filter by query if provided
    if query and query.strip():
        query_lower = query.lower().strip()
        results = [r for r in results if query_lower in r['drug_name'].lower()]
    
    # Sort by earliest listing date
    results.sort(key=lambda x: x.get('earliest_listing_date', 'ZZZZ'))
    
    return results

def search_incidents(query: Optional[str] = None, incident_number: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search for incident numbers associated with PBS drugs.
    Supports bidirectional search: drug name -> incidents, incident number -> drugs.
    """
    changes = load_summary_of_changes()
    items = load_items()
    
    # Create item lookup by PBS code
    item_map = {}
    for item in items:
        pbs_code = safe_get(item, 'pbs_code', default='')
        if pbs_code:
            if pbs_code not in item_map:
                item_map[pbs_code] = item
    
    results = []
    
    for change in changes:
        change_incident = safe_get(change, 'incident_number', 'change_id', default='')
        pbs_code = safe_get(change, 'pbs_code', 'item_code', default='')
        
        # Get item details if available
        item_info = item_map.get(pbs_code, {})
        drug_name = safe_get(item_info, 'li_drug_name', 'drug_name', 'mp_pt', default='') or \
                    safe_get(change, 'drug_name', default='')
        
        change_date = safe_get(change, 'change_date', 'effective_date', default='')
        change_date = parse_date(change_date)
        
        result = {
            'incident_number': change_incident,
            'pbs_code': pbs_code,
            'drug_name': drug_name,
            'change_type': safe_get(change, 'change_type', default=''),
            'change_date': change_date,
            'description': safe_get(change, 'description', 'change_description', default=''),
            'schedule_code': safe_get(change, 'schedule_code', default='')
        }
        
        # Apply filters
        if incident_number:
            if incident_number.lower() not in str(change_incident).lower():
                continue
        
        if query:
            query_lower = query.lower().strip()
            if not (query_lower in drug_name.lower() or 
                    query_lower in pbs_code.lower() or
                    query_lower in result.get('description', '').lower()):
                continue
        
        results.append(result)
    
    # Sort by date descending
    results.sort(key=lambda x: x.get('change_date', ''), reverse=True)
    
    return results

def get_item_price_history(pbs_code: str) -> List[Dict[str, Any]]:
    """Get price history for a specific PBS item."""
    if not pbs_code or not isinstance(pbs_code, str):
        return []
    
    pbs_code = pbs_code.strip().upper()
    events = load_item_pricing_events()
    
    # Filter to specific item
    item_events = [e for e in events if safe_get(e, 'pbs_code', default='').upper() == pbs_code]
    
    # Sort by date
    item_events.sort(key=lambda x: parse_date(safe_get(x, 'effective_date', 'event_date', default='')))
    
    return item_events

def get_item_full_profile(pbs_code: str, schedule_code: Optional[str] = None) -> Dict[str, Any]:
    """Get complete profile for a PBS item including all related data."""
    if not pbs_code or not isinstance(pbs_code, str):
        return {'error': 'Invalid PBS code'}
    
    pbs_code = pbs_code.strip().upper()
    items = load_items(schedule_code)
    item_atc = load_item_atc_relationships(schedule_code)
    item_org = load_item_org_relationships(schedule_code)
    item_restr = load_item_restriction_relationships(schedule_code)
    organisations = load_organisations()
    atc_codes = load_atc_codes()
    restrictions = load_restrictions(schedule_code)
    
    # Find the item
    item = None
    for i in items:
        if safe_get(i, 'pbs_code', default='').upper() == pbs_code:
            item = i
            break
    
    if not item:
        return {'error': 'Item not found', 'pbs_code': pbs_code}
    
    # Build lookup maps
    org_map = {safe_get(o, 'organisation_code', default=''): o for o in organisations}
    atc_map = {safe_get(a, 'atc_code', default=''): a for a in atc_codes}
    restr_map = {safe_get(r, 'restriction_code', default=''): r for r in restrictions}
    
    # Get related ATC codes
    related_atc = []
    for rel in item_atc:
        if safe_get(rel, 'pbs_code', default='').upper() == pbs_code:
            atc_code = safe_get(rel, 'atc_code', default='')
            if atc_code:
                atc_info = atc_map.get(atc_code, {})
                related_atc.append({
                    'atc_code': atc_code,
                    'atc_name': safe_get(atc_info, 'atc_name', default=''),
                    'atc_level': safe_get(atc_info, 'atc_level', default='')
                })
    
    # Get related organisations
    related_orgs = []
    for rel in item_org:
        if safe_get(rel, 'pbs_code', default='').upper() == pbs_code:
            org_code = safe_get(rel, 'organisation_code', default='')
            if org_code:
                org_info = org_map.get(org_code, {})
                related_orgs.append({
                    'organisation_code': org_code,
                    'organisation_name': safe_get(org_info, 'organisation_name', default=''),
                    'relationship_type': safe_get(rel, 'relationship_type', default='')
                })
    
    # Get related restrictions
    related_restrictions = []
    for rel in item_restr:
        if safe_get(rel, 'pbs_code', default='').upper() == pbs_code:
            restr_code = safe_get(rel, 'restriction_code', default='')
            if restr_code:
                restr_info = restr_map.get(restr_code, {})
                related_restrictions.append({
                    'restriction_code': restr_code,
                    'restriction_text': safe_get(restr_info, 'restriction_text', default=''),
                    'authority_required': safe_get(restr_info, 'authority_required', default='')
                })
    
    return {
        'item': item,
        'atc_codes': related_atc,
        'organisations': related_orgs,
        'restrictions': related_restrictions
    }

def get_atc_hierarchy() -> Dict[str, Any]:
    """Get ATC codes organized hierarchically."""
    atc_codes = load_atc_codes()
    
    # Organize by level with safe field access
    hierarchy = defaultdict(list)
    for atc in atc_codes:
        level = safe_get(atc, 'atc_level', default='unknown')
        hierarchy[level].append(atc)
    
    return {
        'levels': dict(hierarchy),
        'total_codes': len(atc_codes)
    }

def get_manufacturer_portfolio(org_code: Optional[str] = None, org_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all items for a manufacturer/organisation."""
    organisations = load_organisations()
    item_org = load_item_org_relationships()
    items = load_items()
    
    # Create item lookup
    item_map = {safe_get(i, 'pbs_code', default=''): i for i in items}
    
    # Filter organisations if query provided
    target_orgs = organisations
    if org_code:
        target_orgs = [o for o in organisations if org_code.lower() in safe_get(o, 'organisation_code', default='').lower()]
    elif org_name:
        target_orgs = [o for o in organisations if org_name.lower() in safe_get(o, 'organisation_name', default='').lower()]
    
    results = []
    for org in target_orgs:
        org_code_val = safe_get(org, 'organisation_code', default='')
        if not org_code_val:
            continue
        
        # Find all items for this org
        org_items = []
        for rel in item_org:
            if safe_get(rel, 'organisation_code', default='') == org_code_val:
                pbs_code = safe_get(rel, 'pbs_code', default='')
                item_info = item_map.get(pbs_code, {})
                org_items.append({
                    'pbs_code': pbs_code,
                    'drug_name': safe_get(item_info, 'li_drug_name', 'drug_name', default=''),
                    'brand_name': safe_get(item_info, 'brand_name', default=''),
                    'relationship_type': safe_get(rel, 'relationship_type', default='')
                })
        
        results.append({
            'organisation': org,
            'items': org_items,
            'item_count': len(org_items)
        })
    
    return results

def compare_schedules(schedule_codes: List[str]) -> Dict[str, Any]:
    """Compare items across multiple schedules."""
    if not schedule_codes or len(schedule_codes) < 2:
        return {'error': 'At least 2 schedule codes required'}
    
    # Validate and clean schedule codes
    schedule_codes = [c.strip() for c in schedule_codes if c and isinstance(c, str)]
    if len(schedule_codes) < 2:
        return {'error': 'At least 2 valid schedule codes required'}
    
    schedule_items = {}
    for code in schedule_codes:
        items = load_items(code)
        schedule_items[code] = {safe_get(i, 'pbs_code', default=''): i for i in items if safe_get(i, 'pbs_code', default='')}
    
    # Find differences
    all_codes = set()
    for items in schedule_items.values():
        all_codes.update(items.keys())
    
    comparison = {
        'schedules': schedule_codes,
        'total_unique_items': len(all_codes),
        'items_in_all': [],
        'items_added': defaultdict(list),
        'items_removed': defaultdict(list)
    }
    
    for pbs_code in all_codes:
        present_in = [code for code in schedule_codes if pbs_code in schedule_items[code]]
        
        if len(present_in) == len(schedule_codes):
            comparison['items_in_all'].append(pbs_code)
        else:
            for i, code in enumerate(schedule_codes[1:], 1):
                prev_code = schedule_codes[i-1]
                if pbs_code in schedule_items[code] and pbs_code not in schedule_items[prev_code]:
                    item_info = schedule_items[code][pbs_code]
                    comparison['items_added'][code].append({
                        'pbs_code': pbs_code,
                        'drug_name': safe_get(item_info, 'li_drug_name', 'drug_name', default='')
                    })
                elif pbs_code in schedule_items[prev_code] and pbs_code not in schedule_items[code]:
                    item_info = schedule_items[prev_code][pbs_code]
                    comparison['items_removed'][code].append({
                        'pbs_code': pbs_code,
                        'drug_name': safe_get(item_info, 'li_drug_name', 'drug_name', default='')
                    })
    
    comparison['items_added'] = dict(comparison['items_added'])
    comparison['items_removed'] = dict(comparison['items_removed'])
    
    return comparison

def get_recent_changes(limit: int = 100, change_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get recent PBS changes for alerts/feed."""
    limit = max(1, min(limit, 1000))  # Clamp between 1 and 1000
    
    changes = load_summary_of_changes()
    items = load_items()
    
    # Create item lookup
    item_map = {safe_get(i, 'pbs_code', default=''): i for i in items}
    
    # Filter by change type if specified
    if change_type and isinstance(change_type, str):
        change_type = change_type.strip().lower()
        changes = [c for c in changes if change_type in safe_get(c, 'change_type', default='').lower()]
    
    # Sort by date (newest first) and take limit
    changes.sort(key=lambda x: parse_date(safe_get(x, 'change_date', 'effective_date', default='')), reverse=True)
    
    # Enrich with item info
    results = []
    for change in changes[:limit]:
        pbs_code = safe_get(change, 'pbs_code', 'item_code', default='')
        item_info = item_map.get(pbs_code, {})
        
        results.append({
            'pbs_code': pbs_code,
            'drug_name': safe_get(item_info, 'li_drug_name', 'drug_name', default=''),
            'brand_name': safe_get(item_info, 'brand_name', default=''),
            'change_type': safe_get(change, 'change_type', default=''),
            'change_date': parse_date(safe_get(change, 'change_date', 'effective_date', default='')),
            'description': safe_get(change, 'description', 'change_description', default=''),
            'schedule_code': safe_get(change, 'schedule_code', default='')
        })
    
    return results

# ============================================================================
# HTTP Request Handler
# ============================================================================

class Handler(http.server.SimpleHTTPRequestHandler):
    def send_json_response(self, data: Any, status: int = 200) -> None:
        """Send JSON response with proper headers."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))
    
    def parse_query_params(self) -> Dict[str, str]:
        """Parse query parameters from URL."""
        parsed = urllib.parse.urlparse(self.path)
        return dict(urllib.parse.parse_qsl(parsed.query))
    
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        params = self.parse_query_params()
        
        try:
            # ================================================================
            # Enhanced API Endpoints
            # ================================================================
            
            # Cache management
            if path == '/api/cache/stats':
                self.send_json_response(cache.get_stats())
                return
            
            if path == '/api/cache/clear':
                key = params.get('key')
                cache.clear(key)
                self.send_json_response({'status': 'cleared', 'key': key or 'all'})
                return
            
            # Earliest listing search
            if path == '/api/search/earliest-listing':
                query = validate_query(params.get('query', params.get('q', '')))
                results = search_earliest_listing(query if query else None)
                self.send_json_response({
                    'count': len(results),
                    'query': query,
                    'results': results
                })
                return
            
            # Incident number search
            if path == '/api/search/incidents':
                query = validate_query(params.get('query', params.get('q', '')))
                incident = validate_query(params.get('incident_number', params.get('incident', '')), max_length=50)
                results = search_incidents(
                    query=query if query else None,
                    incident_number=incident if incident else None
                )
                self.send_json_response({
                    'count': len(results),
                    'query': query,
                    'incident_number': incident,
                    'results': results
                })
                return
            
            # Item price history
            if path.startswith('/api/item-price-history/'):
                pbs_code = validate_pbs_code(path.split('/')[-1])
                if not pbs_code:
                    self.send_json_response({'error': 'Invalid PBS code'}, status=400)
                    return
                results = get_item_price_history(pbs_code)
                self.send_json_response({
                    'pbs_code': pbs_code,
                    'count': len(results),
                    'events': results
                })
                return
            
            # Item full profile
            if path.startswith('/api/item-profile/'):
                pbs_code = validate_pbs_code(path.split('/')[-1])
                if not pbs_code:
                    self.send_json_response({'error': 'Invalid PBS code'}, status=400)
                    return
                schedule_code = validate_schedule_code(params.get('schedule_code', ''))
                result = get_item_full_profile(pbs_code, schedule_code if schedule_code else None)
                self.send_json_response(result)
                return
            
            # ATC hierarchy
            if path == '/api/atc-hierarchy':
                result = get_atc_hierarchy()
                self.send_json_response(result)
                return
            
            # Manufacturer portfolio
            if path == '/api/manufacturer-portfolio':
                org_code = params.get('org_code')
                org_name = validate_query(params.get('org_name', params.get('query', params.get('q', ''))))
                results = get_manufacturer_portfolio(
                    org_code=org_code.strip() if org_code and isinstance(org_code, str) else None,
                    org_name=org_name if org_name else None
                )
                self.send_json_response({
                    'count': len(results),
                    'results': results
                })
                return
            
            # Schedule comparison
            if path == '/api/compare-schedules':
                codes = params.get('schedules', '').split(',')
                codes = [validate_schedule_code(c) for c in codes if c.strip()]
                if not codes or len(codes) < 2:
                    self.send_json_response({'error': 'At least 2 valid schedule codes required'}, status=400)
                    return
                result = compare_schedules(codes)
                self.send_json_response(result)
                return
            
            # Recent changes feed
            if path == '/api/recent-changes':
                try:
                    limit = int(params.get('limit', '100'))
                    limit = max(1, min(limit, 1000))  # Clamp between 1 and 1000
                except (ValueError, TypeError):
                    limit = 100
                change_type = validate_query(params.get('change_type', ''), max_length=50) if params.get('change_type') else None
                results = get_recent_changes(limit, change_type)
                self.send_json_response({
                    'count': len(results),
                    'limit': limit,
                    'results': results
                })
                return
            
            # Schedules list (JSON)
            if path == '/api/schedules-list':
                schedules = load_schedules()
                self.send_json_response({
                    'count': len(schedules),
                    'schedules': schedules
                })
                return
            
            # ================================================================
            # Original Proxy Endpoint (CSV)
            # ================================================================
            
            if path.startswith('/api/'):
                api_path = path[5:]  # Remove /api/
                url = API_BASE + api_path
                
                if params:
                    url += '?' + urllib.parse.urlencode(params)
                
                req = urllib.request.Request(url, headers={
                    'Accept': 'text/csv',
                    'subscription-key': SUBSCRIPTION_KEY
                })
                
                with urllib.request.urlopen(req, timeout=60) as response:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/csv')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(response.read())
                return
            
            # ================================================================
            # Static Files
            # ================================================================
            
            super().do_GET()
            
        except Exception as e:
            print(f"Error handling {self.path}: {e}")
            import traceback
            traceback.print_exc()
            
            # Determine appropriate error message based on error type
            if isinstance(e, TimeoutError) or 'timeout' in str(e).lower():
                error_msg = "PBS API request timed out. The API may be slow or unavailable. Please try again."
                status = 504
            elif isinstance(e, urllib.error.URLError):
                error_msg = f"Network error: {str(e)}"
                status = 503
            else:
                error_msg = str(e)
                status = 500
            
            self.send_json_response({
                'error': error_msg,
                'path': self.path,
                'timestamp': datetime.now().isoformat()
            }, status=status)
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

# ============================================================================
# Server Startup
# ============================================================================

# ============================================================================
# Server Startup
# ============================================================================

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Shutting down PBS API Server...                             ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    sys.exit(0)

if __name__ == '__main__':
    os.chdir('/Users/djcal/GIT/PBS')
    
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal_handler)
    
    # Allow address reuse
    socketserver.TCPServer.allow_reuse_address = True
    
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"╔══════════════════════════════════════════════════════════════╗")
            print(f"║  PBS API Server - Enhanced Edition                           ║")
            print(f"╠══════════════════════════════════════════════════════════════╣")
            print(f"║  Server running at: http://localhost:{PORT}                    ║")
            print(f"╠══════════════════════════════════════════════════════════════╣")
            print(f"║  Enhanced Endpoints:                                         ║")
            print(f"║    /api/search/earliest-listing?q=<drug>                     ║")
            print(f"║    /api/search/incidents?q=<drug>&incident=<num>             ║")
            print(f"║    /api/item-price-history/<pbs_code>                        ║")
            print(f"║    /api/item-profile/<pbs_code>                              ║")
            print(f"║    /api/atc-hierarchy                                        ║")
            print(f"║    /api/manufacturer-portfolio?org_name=<name>               ║")
            print(f"║    /api/compare-schedules?schedules=<code1>,<code2>          ║")
            print(f"║    /api/recent-changes?limit=100                             ║")
            print(f"║    /api/cache/stats                                          ║")
            print(f"║    /api/cache/clear                                          ║")
            print(f"╠══════════════════════════════════════════════════════════════╣")
            print(f"║  Press Ctrl+C to stop the server                             ║")
            print(f"╚══════════════════════════════════════════════════════════════╝")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n╔══════════════════════════════════════════════════════════════╗")
        print("║  Shutting down PBS API Server...                             ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        sys.exit(0)
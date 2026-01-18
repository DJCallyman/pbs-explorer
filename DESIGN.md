# PBS Explorer - System Design & Implementation Guide

## 1. Overview

PBS Explorer is a comprehensive data exploration platform for the Australian Pharmaceutical Benefits Scheme (PBS). It provides search, filtering, and reporting capabilities for PBS medicines, pricing, restrictions, and related entities.

**Key Features:**
- Advanced search and filtering across 100,000+ PBS items
- Real-time data synchronization from PBS API
- Comprehensive database schema for medicines, restrictions, pricing, and classifications
- RESTful API with 40+ endpoints
- Web UI with HTMX for dynamic interactions
- Reporting and analytics capabilities
- Admin dashboard for data management

## 2. System Architecture

### 2.1 Architecture Diagram

```
┌─────────────────────┐
│   Web Browser UI    │
│  (HTMX + Tailwind)  │
└──────────┬──────────┘
           │ HTTP/HTTPS
           ▼
┌─────────────────────────────────┐
│   Application Layer             │
│  ┌──────────────────────────┐   │
│  │  API (FastAPI Backend)   │   │
│  └──────────┬───────────────┘   │
│             │                    │
│  ┌──────────▼──────────┐        │
│  │  Redis Cache (Opt)  │        │
│  └─────────────────────┘        │
└──────────┬──────────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐   ┌──────────────┐
│ SQLite/ │   │  External    │
│ Postgre-│   │  PBS API     │
│ SQL DB  │   └──────────────┘
└─────────┘
    ▲
    │ Background Service
    │
┌───┴──────────────────┐
│ Data Sync Service    │
│  (Python asyncio)    │
└──────────────────────┘
```

### 2.2 Component Overview

| Component | Description | Technology |
|-----------|-------------|------------|
| **Web UI** | User-friendly interface for data exploration | HTMX + Tailwind CSS |
| **API Layer** | RESTful API for data access and filtering | FastAPI |
| **Data Sync** | Background service for PBS data synchronization | Python asyncio |
| **Database** | Local cache of PBS data | SQLite/PostgreSQL |
| **Cache Layer** | Optional Redis for performance optimization | Redis |

## 3. Core API Endpoints

### 3.1 Search and Discovery

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/items` | GET | Search and filter PBS items with advanced criteria |
| `/api/v1/items/{li_item_id}` | GET | Get detailed item information with all relationships |
| `/api/v1/items/{li_item_id}/restrictions` | GET | Get restrictions for a specific item |
| `/api/v1/items/{li_item_id}/atc-codes` | GET | Get ATC classifications for an item |
| `/api/v1/items/{li_item_id}/pricing` | GET | Get pricing information for an item |
| `/api/v1/items/{li_item_id}/manufacturer` | GET | Get manufacturer information for an item |
| `/api/v1/restrictions` | GET | Search and filter restrictions |
| `/api/v1/restrictions/{res_code}` | GET | Get detailed restriction information |
| `/api/v1/atc-codes` | GET | Browse ATC classification hierarchy |
| `/api/v1/organisations` | GET | Search manufacturers and organisations |
| `/api/v1/programs` | GET | List PBS programs |
| `/api/v1/schedules` | GET | List available schedules |

### 3.2 Specialized Queries

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/search/earliest-listing` | GET | Find earliest listing of a medicine |
| `/api/v1/search/by-drug-name` | GET | Search items by drug name (fuzzy search) |
| `/api/v1/search/by-brand` | GET | Search items by brand name |
| `/api/v1/search/by-atc` | GET | Search items by ATC code or description |
| `/api/v1/search/by-indication` | GET | Search items by indication/condition |
| `/api/v1/search/by-restriction` | GET | Search items by restriction number |
| `/api/v1/search/therapeutic-groups` | GET | Browse therapeutic groups |
| `/api/v1/search/therapeutic-group/{id}/items` | GET | Get items in a therapeutic group |

### 3.3 Reporting and Analytics

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/reports/items-by-program` | GET | Count items by program |
| `/api/v1/reports/items-by-benefit-type` | GET | Count items by benefit type |
| `/api/v1/reports/items-by-atc-level` | GET | Count items by ATC classification level |
| `/api/v1/reports/new-listings` | GET | Get newly listed items in a date range |
| `/api/v1/reports/delisted-items` | GET | Get delisted items in a date range |
| `/api/v1/reports/price-changes` | GET | Get items with price changes between schedules |
| `/api/v1/reports/restriction-changes` | GET | Get items with restriction changes |
| `/api/v1/reports/manufacturer-summary` | GET | Summary by manufacturer |
| `/api/v1/reports/continued-dispensing` | GET | Items eligible for continued dispensing |
| `/api/v1/reports/60-day-prescriptions` | GET | Items eligible for 60-day prescriptions |

### 3.4 Data Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/admin/sync/status` | GET | Get data synchronization status |
| `/api/v1/admin/sync/trigger` | POST | Trigger manual data sync |
| `/api/v1/admin/sync/latest` | POST | Sync to latest schedule only |
| `/api/v1/admin/cache/clear` | POST | Clear cache (if using Redis) |
| `/api/v1/admin/config` | GET | Get current configuration |
| `/api/v1/admin/config` | PUT | Update configuration |

## 4. Web UI Pages

### Core Pages
- **Home (`/`)** - Dashboard with quick search and stats
- **Search (`/search`)** - Advanced search with filters
- **Browse (`/browse/atc`, `/browse/programs`, `/browse/manufacturers`)** - Category browsing
- **Item Detail (`/item/{li_item_id}`)** - Complete item information with tabs
- **Reports (`/reports`)** - Reporting and analytics
- **Admin (`/admin`)** - Sync status and configuration

### Page Descriptions

#### Home Page
- Quick search bar for immediate searches
- Quick statistics (total items, latest schedule, last sync time)
- Quick links to popular searches
- Recent activity feed

#### Search Page
- Advanced search form with multiple filter options
- Results table with sortable columns
- Pagination controls
- Export options (CSV, JSON, PDF)
- Save search functionality for frequently used queries

#### Item Detail Page
- Complete item information display
- Related data tabs:
  - Overview (basic info, pricing, manufacturer)
  - Restrictions (all associated restrictions)
  - ATC Classifications (anatomical codes)
  - Pricing (historical pricing information)
  - Manufacturer (organization details)
  - Prescribing Texts (guidelines)
  - Indications (approved uses)
- Historical data from previous schedules
- Comparison with similar items

#### Browse Pages
- **ATC Hierarchy** - Hierarchical tree view with expandable/collapsible levels
- **Programs** - List of PBS programs with item counts
- **Manufacturers** - Organization details with contact information
- **Therapeutic Groups** - Therapeutic classifications with pricing comparisons

#### Reports Page
- Report catalog with descriptions
- Report generation interface
- Scheduled reports configuration
- Export options and scheduling

#### Admin Page
- Data synchronization status and controls
- Configuration management interface
- Activity logs and audit trails
- System health metrics

### UI Components

#### Search Form Component
```html
<div class="search-form">
  <input type="text" name="drug_name" placeholder="Drug name">
  <input type="text" name="brand_name" placeholder="Brand name">
  <select name="program_code">
    <option value="">All Programs</option>
    <option value="GE">General Schedule</option>
    <option value="RP">Repatriation</option>
  </select>
  <select name="benefit_type_code">
    <option value="">All Benefit Types</option>
    <option value="U">Unrestricted</option>
    <option value="R">Restricted</option>
    <option value="A">Authority Required</option>
    <option value="S">Streamlined</option>
  </select>
  <select name="atc_level">
    <option value="">All ATC Levels</option>
    <option value="1">Level 1 (Anatomical Group)</option>
    <option value="2">Level 2 (Therapeutic Subgroup)</option>
    <option value="3">Level 3 (Pharmacological Subgroup)</option>
    <option value="4">Level 4 (Chemical Subgroup)</option>
    <option value="5">Level 5 (Chemical Substance)</option>
  </select>
  <input type="date" name="first_listed_date_from" placeholder="Listed from">
  <input type="date" name="first_listed_date_to" placeholder="Listed to">
  <button type="submit">Search</button>
  <button type="reset">Clear</button>
</div>
```

#### Results Table Component
```html
<table class="results-table">
  <thead>
    <tr>
      <th sortable="drug_name">Drug Name</th>
      <th sortable="brand_name">Brand</th>
      <th sortable="pbs_code">PBS Code</th>
      <th sortable="program_code">Program</th>
      <th sortable="benefit_type_code">Benefit Type</th>
      <th sortable="determined_price">Price</th>
      <th sortable="first_listed_date">First Listed</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
    <!-- Results rendered here -->
  </tbody>
</table>
<div class="pagination">
  <button hx-get="/api/v1/items?page=prev" hx-target="tbody">Previous</button>
  <span>Page 1 of 10</span>
  <button hx-get="/api/v1/items?page=next" hx-target="tbody">Next</button>
</div>
```

#### Item Detail Component
```html
<div class="item-detail">
  <h1>{{ drug_name }} - {{ brand_name }}</h1>
  <div class="tabs">
    <button class="tab active" data-tab="overview">Overview</button>
    <button class="tab" data-tab="restrictions">Restrictions</button>
    <button class="tab" data-tab="atc">ATC Codes</button>
    <button class="tab" data-tab="pricing">Pricing</button>
    <button class="tab" data-tab="manufacturer">Manufacturer</button>
  </div>
  <div class="tab-content" id="overview">
    <!-- Overview content -->
  </div>
  <div class="tab-content hidden" id="restrictions">
    <!-- Restrictions content -->
  </div>
  <!-- Additional tabs -->
</div>
```

## 6. Core Features Implementation

### 6.1 Feature: Earliest Listing Search

Find the earliest listing date of a medicine across all historical schedules.

**API Endpoint:**
```
GET /api/v1/search/earliest-listing?drug_name=Aspirin&li_drug_name=&brand_name=
```

**Implementation Logic:**
```python
async def find_earliest_listing(
    drug_name: str,
    li_drug_name: Optional[str] = None,
    brand_name: Optional[str] = None,
):
    """Find the earliest listing of a PBS medicine."""
    
    # Build flexible query
    query = select(Item).where(
        or_(
            Item.drug_name.ilike(f"%{drug_name}%"),
            Item.li_drug_name.ilike(f"%{drug_name}%"),
        )
    )
    
    if li_drug_name:
        query = query.where(Item.li_drug_name.ilike(f"%{li_drug_name}%"))
    
    if brand_name:
        query = query.where(Item.brand_name.ilike(f"%{brand_name}%"))
    
    # Order by first_listed_date ascending
    query = query.order_by(Item.first_listed_date.asc())
    
    # Get the earliest result
    result = await db.execute(query.limit(1))
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="No matching medicine found")
    
    return await get_item_detail(item.li_item_id)
```

**UI Component:**
```html
<div class="earliest-listing-search">
  <h2>Find Earliest Listing</h2>
  <form hx-get="/api/v1/search/earliest-listing" hx-target="#result">
    <div class="form-group">
      <label>Drug Name *</label>
      <input type="text" name="drug_name" required>
    </div>
    <div class="form-group">
      <label>Legal Drug Name (optional)</label>
      <input type="text" name="li_drug_name">
    </div>
    <div class="form-group">
      <label>Brand Name (optional)</label>
      <input type="text" name="brand_name">
    </div>
    <button type="submit">Search</button>
  </form>
  <div id="result"></div>
</div>
```

### 6.2 Feature: Advanced Filtering

Comprehensive search with multiple filter criteria supporting:
- Schedule and program filtering
- Benefit type classification
- Date range filtering
- ATC code hierarchies
- Manufacturer/organization filtering
- Boolean flag filters (extemporaneous, continued dispensing, etc.)
- Pagination and sorting

**Sample Request:**
```
GET /api/v1/items?drug_name=Paracetamol&benefit_type_code=U&program_code=GE
    &first_listed_date_from=2020-01-01&limit=50&sort=desc&sort_fields=determined_price
```

**Response Format:**
```json
{
  "data": [
    {
      "li_item_id": "123456",
      "drug_name": "Paracetamol",
      "brand_name": "Panadol",
      "pbs_code": "5678",
      "program_code": "GE",
      "benefit_type_code": "U",
      "determined_price": 5.50,
      "first_listed_date": "2010-01-01",
      "restrictions": [...],
      "atc_codes": [...],
      "pricing": {...},
      "manufacturer": {...}
    }
  ],
  "_meta": {
    "total_records": 5000,
    "page": 1,
    "limit": 50,
    "total_pages": 100
  }
}
```

### 6.3 Feature: Historical Price Tracking

Track price changes across different PBS schedules:

**API Endpoint:**
```
GET /api/v1/reports/price-changes?schedule_code_from=3920&schedule_code_to=3923
```

**Features:**
- Compare pricing between schedules
- Identify new items
- Identify delisted items
- Calculate price increases/decreases
- Generate pricing reports

### 6.4 Feature: Restriction Analysis

Comprehensive restriction management and analysis:

**Features:**
- Search restrictions by code or text
- Find all items with specific restrictions
- Compare restriction criteria across items
- Authority method filtering
- Treatment phase analysis

### 6.5 Feature: Therapeutic Group Navigation

Browse and analyze items by therapeutic classification:

**API Endpoint:**
```
GET /api/v1/search/therapeutic-groups
GET /api/v1/search/therapeutic-group/{id}/items
```

**Features:**
- Hierarchical therapeutic group browsing
- Item count per group
- Price comparison within groups
- Alternative medicine identification

### 6.6 Feature: Manufacturer Analysis

Track and analyze medicine suppliers:

**Features:**
- List all manufacturers with contact details
- Find items by manufacturer
- Count items per manufacturer
- Organization information (ABN, address, phone)

---



### 5.1 Standard Filtering Parameters

Available for most endpoints:

```yaml
# Schedule and Program Filters
schedule_code: string[]          # Filter by schedule code(s)
program_code: string[]           # Filter by program code(s) - e.g., GE, RP
benefit_type_code: string[]      # Filter by benefit type - U/R/A/S
formulary: string[]              # Filter by formulary - F1/F2/CDL

# Item Name Filters
drug_name: string[]              # Filter by drug name (partial match)
brand_name: string[]             # Filter by brand name (partial match)
li_drug_name: string[]           # Filter by legal drug name
pbs_code: string[]               # Filter by PBS code(s)

# Classification Filters
atc_code: string[]               # Filter by ATC code(s)
atc_level: integer[]             # Filter by ATC level (1-5)
therapeutic_group_id: string[]   # Filter by therapeutic group

# Organization Filters
organisation_id: integer[]       # Filter by manufacturer ID
manufacturer_code: string[]      # Filter by manufacturer code

# Date Range Filters
first_listed_date_from: date     # Items listed on or after
first_listed_date_to: date       # Items listed on or before
non_effective_date_from: date    # Items delisted on or after
non_effective_date_to: date      # Items delisted on or before

# Boolean Flags
extemporaneous_indicator: boolean
continued_dispensing_flag: boolean
supply_only_indicator: boolean
section100_only_indicator: boolean
doctors_bag_only_indicator: boolean
policy_applied_imdq60_flag: boolean
policy_applied_indig_phar_flag: boolean

# Pagination and Sorting
page: integer                    # Page number (default: 1)
limit: integer                   # Results per page (default: 50, max: 1000)
sort: string                     # Sort direction (asc/desc)
sort_fields: string              # Comma-separated fields to sort by

# Response Options
fields: string                   # Comma-separated fields to return
include: string[]                # Include related data (restrictions, atc, pricing, manufacturer, etc.)
```

### 5.2 Specialized Query Parameters

**Earliest Listing Search:**
```yaml
drug_name: string                # Drug name to search (required)
li_drug_name: string             # Legal drug name (optional)
brand_name: string               # Brand name (optional)
```

**Fuzzy Search:**
```yaml
q: string                        # Search query (required)
search_fields: string[]          # Fields to search (default: drug_name,brand_name)
fuzziness: integer               # Levenshtein distance (default: 2)
```

## 7. Data Synchronization Strategy

### 7.1 Sync Architecture

The data synchronization system ensures PBS Explorer stays up-to-date with the latest PBS data:

```
┌─────────────────────┐
│  PBS Explorer       │
│  Server Startup     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────┐
│  Data Sync Service              │
│  - Check latest schedule        │
│  - Compare with local data      │
│  - Fetch new/updated data       │
│  - Insert/update database       │
│  - Invalidate cache             │
└──────────┬──────────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
 ┌─────┐    ┌──────────────┐
 │Local│    │External PBS  │
 │DB   │    │API           │
 └─────┘    └──────────────┘
```

### 7.2 Sync Process

#### Startup Check
On server startup, the sync service:
1. Retrieves the latest schedule code from the local database
2. Fetches the latest schedule from the PBS API
3. Compares schedule codes to detect new data
4. Optionally checks data age (refresh if > 30 days old)
5. Triggers full sync if needed

#### Sync Execution
Full sync follows a strict dependency order:
1. Schedules (base reference)
2. Programs, Organisations, Containers
3. ATC Codes, Dispensing Rules, Criteria, Parameters
4. Prescribing Texts, Indications, Copayments, Fees
5. Restrictions, Items
6. All relationship tables (item_atc_relationship, item_restriction_relationship, etc.)
7. Additional data (pricing events, AMT items, extemporaneous preparations, etc.)

#### Sync Workflow
```
For each PBS API endpoint:
1. Fetch data with pagination (limit: 100,000 per request)
2. Parse CSV/JSON response
3. Validate data against schema
4. Upsert into database (insert if new, update if exists)
5. Create/update indexes
6. Log sync progress and any errors
7. Invalidate affected cache keys
8. Update last_sync_timestamp
```

### 7.3 Configuration Options

```yaml
# config.yaml
pbs:
  api_base_url: "https://data-api.health.gov.au/pbs/api/v3"
  subscription_key: "YOUR_API_KEY"
  
sync:
  # Sync behavior
  check_on_startup: true
  force_refresh_on_startup: false
  auto_sync_enabled: true
  auto_sync_interval_hours: 24
  
  # Data freshness
  max_data_age_days: 30
  sync_latest_only: false
  
  # Performance
  batch_size: 1000
  max_concurrent_requests: 5
  
  # Cache
  use_cache: false
  cache_ttl_seconds: 3600

database:
  type: "sqlite"  # or "postgresql"
  path: "pbs_data.db"
  
  # PostgreSQL settings (if type is postgresql)
  host: "localhost"
  port: 5432
  database: "pbs_explorer"
  username: "pbs_user"
  password: "secure_password"

server:
  host: "0.0.0.0"
  port: 8000
  debug: false
  
  # CORS configuration
  allow_origins: ["*"]
  allow_credentials: true
  allow_methods: ["GET", "POST", "PUT"]
  allow_headers: ["*"]

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

## 7.4 Sync Endpoints

All 35+ PBS API endpoints are synced:

**Core Data:**
- /schedules, /programs, /organisations, /containers
- /atc-codes, /dispensing-rules, /criteria, /parameters
- /indications, /copayments, /fees

**Items & Restrictions:**
- /items, /restrictions, /prescribing-texts

**Relationships:**
- /item-atc-relationships, /item-organisation-relationships
- /item-restriction-relationships, /item-dispensing-rule-relationships
- /item-prescribing-text-relationships, /restriction-prescribing-text-relationships
- /criteria-parameter-relationships, /container-organisation-relationships

**Additional Data:**
- /item-pricing-events, /amt-items, /extemporaneous-preparations
- /extemporaneous-ingredients, /extemporaneous-tariffs
- /standard-formula-preparations, /markup-bands, /prescribers
- /summary-of-changes

## 9. Implementation Phases

### Phase 1: Project Setup (Week 1-2)
- Configure FastAPI application structure
- Set up SQLite database with initial schema
- Create SQLAlchemy models for all tables
- Implement configuration management (YAML/environment)
- Set up logging and error handling

### Phase 2: Data Synchronization (Weeks 3-4)
- Implement PBS API client wrapper
- Implement full data sync service
- Create sync status tracking and logging
- Implement startup sync check
- Add manual sync trigger endpoints
- Test with real PBS API data

### Phase 3: Core API Endpoints (Week 5-6)
- Implement `/api/v1/items` search endpoint with filtering
- Implement `/api/v1/items/{id}` detail endpoint
- Implement `/api/v1/restrictions` endpoints
- Implement `/api/v1/atc-codes` endpoints
- Implement `/api/v1/organisations` endpoints
- Implement `/api/v1/schedules` endpoints

### Phase 4: Specialized Queries (Week 7-8)
- Implement earliest listing search
- Implement fuzzy search by drug name
- Implement ATC-based search
- Implement indication-based search
- Implement therapeutic group search
- Implement manufacturer-based search

### Phase 5: Web UI - Basic (Week 9-10)
- Set up HTMX + Tailwind CSS frontend
- Create base layout and navigation
- Implement home page with stats
- Implement search page with form
- Implement results table with sorting
- Implement pagination

### Phase 6: Web UI - Advanced (Week 11-12)
- Implement item detail page with tabs
- Implement browse pages (ATC, Programs, Manufacturers)
- Implement tabbed interface for related data
- Add export functionality (CSV, JSON, PDF)
- Implement responsive mobile design

### Phase 7: Reporting (Week 13-14)
- Implement reporting endpoints
- Implement report catalog
- Add export options
- Create report templates
- Implement scheduled reports

### Phase 8: Admin Features (Week 15-16)
- Implement sync status dashboard
- Implement configuration management UI
- Add activity logging and audit trails
- Implement system health monitoring
- Add admin authentication/authorization

### Phase 9: Optimization (Week 17-18)
- Add comprehensive database indexes
- Implement query optimization
- Add Redis caching layer (optional)
- Implement rate limiting
- Performance testing and profiling

### Phase 10: Documentation & Deployment (Week 19-20)
- Write comprehensive API documentation
- Create user guide and tutorials
- Write deployment guide
- Create Docker image and compose file
- Test deployment scenarios
- Final QA and bug fixes

## 10. Deployment

### Local Development
```bash
# Clone and setup
git clone https://github.com/yourusername/pbs-explorer.git
cd pbs-explorer

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run initial sync
python -m tasks.sync

# Start server
python main.py
```

### Configuration (config.yaml)
```yaml
pbs:
  api_base_url: "https://data-api.health.gov.au/pbs/api/v3"
  subscription_key: "YOUR_API_KEY"

database:
  type: "sqlite"
  path: "pbs_data.db"

server:
  host: "0.0.0.0"
  port: 8000
  debug: false
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
```

## 8. Database Schema

### 8.1 Entity Relationship Diagram

Core tables and their relationships:
- **SCHEDULE** - PBS schedules/pricing periods
- **ITEM** - Medicines/products (100+ columns for comprehensive data)
- **RESTRICTION** - Prescribing restrictions
- **ATC_CODE** - Anatomical Therapeutic Chemical classifications
- **ORGANISATION** - Manufacturers and suppliers
- **INDICATION** - Approved indications for items
- **PRESCRIBING_TEXT** - Prescribing guidelines
- **COPAYMENT** - Patient copayment amounts
- **FEE** - Dispensing fees and charges
- **CONTAINER** - Packaging/container details
- Relationship tables for many-to-many mappings (ITEM_ATC_RELATIONSHIP, ITEM_RESTRICTION_RELATIONSHIP, etc.)

### 8.2 Core Tables - SQL Definitions

#### SCHEDULE
```sql
CREATE TABLE schedule (
    schedule_code VARCHAR(20) PRIMARY KEY,
    effective_date DATE,
    effective_month VARCHAR(20),
    effective_year INTEGER,
    start_tsp TIMESTAMP,
    revision_number INTEGER,
    publication_status VARCHAR(20),
    last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### ITEM (Core Medicine Data)
```sql
CREATE TABLE item (
    li_item_id VARCHAR(100) PRIMARY KEY,
    schedule_code VARCHAR(20) REFERENCES schedule(schedule_code),
    drug_name VARCHAR(500),
    li_drug_name VARCHAR(500),
    li_form VARCHAR(500),
    schedule_form VARCHAR(500),
    brand_name VARCHAR(500),
    program_code VARCHAR(10),
    pbs_code VARCHAR(20),
    benefit_type_code CHAR(1),
    caution_indicator CHAR(1),
    note_indicator CHAR(1),
    manner_of_administration VARCHAR(100),
    moa_preferred_term VARCHAR(100),
    maximum_prescribable_pack INTEGER,
    maximum_quantity_units VARCHAR(50),
    number_of_repeats INTEGER,
    organisation_id INTEGER,
    manufacturer_code VARCHAR(20),
    pack_size INTEGER,
    pricing_quantity INTEGER,
    pack_not_to_be_broken_ind CHAR(1),
    claimed_price DECIMAL(10,2),
    determined_price DECIMAL(10,2),
    determined_qty CHAR(1),
    safety_net_resupply_rule_days INTEGER,
    safety_net_resup_rule_cnt_ind CHAR(1),
    extemporaneous_indicator CHAR(1),
    extemporaneous_standard VARCHAR(100),
    doctors_bag_group_id VARCHAR(50),
    section100_only_indicator CHAR(1),
    doctors_bag_only_indicator CHAR(1),
    brand_substitution_group_id VARCHAR(50),
    brand_substitution_group_code VARCHAR(10),
    continued_dispensing_emergency CHAR(1),
    continued_dispensing_flag CHAR(1),
    supply_only_indicator CHAR(1),
    supply_only_date DATE,
    non_effective_date DATE,
    originator_brand_indicator CHAR(1),
    paper_med_chart_eligible_ind CHAR(1),
    elect_med_chart_eligible_ind CHAR(1),
    hsptl_med_chart_eligible_ind CHAR(1),
    paper_med_chart_duration INTEGER,
    elect_med_chart_duration INTEGER,
    hsptl_chart_acute_duration INTEGER,
    hsptl_chart_sub_acute_duration INTEGER,
    hsptl_chart_chronic_duration INTEGER,
    pack_content INTEGER,
    vial_content VARCHAR(50),
    infusible_indicator CHAR(1),
    unit_of_measure VARCHAR(50),
    maximum_amount VARCHAR(50),
    formulary VARCHAR(10),
    water_added_ind CHAR(1),
    section_19a_expiry_date DATE,
    container_fee_type VARCHAR(50),
    policy_applied_bio_sim_up_flag CHAR(1),
    policy_applied_imdq60_flag CHAR(1),
    policy_applied_imdq60_base_flag CHAR(1),
    policy_applied_indig_phar_flag CHAR(1),
    therapeutic_exemption_indicator CHAR(1),
    premium_exemption_group_id VARCHAR(50),
    doctors_bag_group_title VARCHAR(200),
    therapeutic_group_id VARCHAR(50),
    therapeutic_group_title VARCHAR(200),
    advanced_notice_date DATE,
    supply_only_end_date DATE,
    first_listed_date DATE,
    legal_unar_ind CHAR(1),
    legal_car_ind CHAR(1),
    proportional_price DECIMAL(10,2),
    li_substitution_group_id VARCHAR(50),
    innovator_indicator CHAR(1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indexes
CREATE INDEX idx_item_schedule_code ON item(schedule_code);
CREATE INDEX idx_item_drug_name ON item(drug_name);
CREATE INDEX idx_item_brand_name ON item(brand_name);
CREATE INDEX idx_item_pbs_code ON item(pbs_code);
CREATE INDEX idx_item_program_code ON item(program_code);
CREATE INDEX idx_item_benefit_type_code ON item(benefit_type_code);
CREATE INDEX idx_item_first_listed_date ON item(first_listed_date);
CREATE INDEX idx_item_non_effective_date ON item(non_effective_date);
```

#### RESTRICTION
```sql
CREATE TABLE restriction (
    res_code VARCHAR(100) PRIMARY KEY,
    schedule_code VARCHAR(20) REFERENCES schedule(schedule_code),
    restriction_number INTEGER,
    treatment_of_code INTEGER,
    authority_method VARCHAR(50),
    treatment_phase VARCHAR(100),
    note_indicator CHAR(1),
    caution_indicator CHAR(1),
    complex_authority_rqrd_ind CHAR(1),
    assessment_type_code VARCHAR(50),
    criteria_relationship VARCHAR(10),
    variation_rule_applied CHAR(1),
    first_listing_date DATE,
    written_authority_required CHAR(1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_restriction_schedule_code ON restriction(schedule_code);
CREATE INDEX idx_restriction_number ON restriction(restriction_number);
```

#### ATC_CODE
```sql
CREATE TABLE atc_code (
    atc_code VARCHAR(20) PRIMARY KEY,
    atc_description VARCHAR(500),
    atc_level INTEGER,
    atc_parent_code VARCHAR(20),
    schedule_code VARCHAR(20) REFERENCES schedule(schedule_code),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_atc_schedule_code ON atc_code(schedule_code);
CREATE INDEX idx_atc_level ON atc_code(atc_level);
```

#### ORGANISATION
```sql
CREATE TABLE organisation (
    organisation_id INTEGER PRIMARY KEY,
    name VARCHAR(500),
    abn VARCHAR(20),
    street_address VARCHAR(500),
    city VARCHAR(200),
    state VARCHAR(100),
    postcode VARCHAR(20),
    telephone_number VARCHAR(50),
    facsimile_number VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### PRESCRIBING_TEXT
```sql
CREATE TABLE prescribing_text (
    prescribing_txt_id INTEGER PRIMARY KEY,
    prescribing_txt TEXT,
    prescribing_type VARCHAR(100),
    complex_authority_rqrd_ind CHAR(1),
    assessment_type_code VARCHAR(50),
    apply_to_increase_mq_flag CHAR(1),
    apply_to_increase_nr_flag CHAR(1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### INDICATION
```sql
CREATE TABLE indication (
    indication_prescribing_txt_id INTEGER PRIMARY KEY,
    condition VARCHAR(500),
    episodicity VARCHAR(100),
    severity VARCHAR(100),
    schedule_code VARCHAR(20) REFERENCES schedule(schedule_code),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### COPAYMENT
```sql
CREATE TABLE copayment (
    id SERIAL PRIMARY KEY,
    schedule_code VARCHAR(20) REFERENCES schedule(schedule_code),
    general DECIMAL(10,2),
    concessional DECIMAL(10,2),
    safety_net_general DECIMAL(10,2),
    safety_net_concessional DECIMAL(10,2),
    safety_net_card_issue DECIMAL(10,2),
    increased_discount_limit DECIMAL(10,2),
    safety_net_ctg_contribution DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### FEE
```sql
CREATE TABLE fee (
    id SERIAL PRIMARY KEY,
    schedule_code VARCHAR(20) REFERENCES schedule(schedule_code),
    program_code VARCHAR(10),
    dispensing_fee_ready_prepared DECIMAL(10,2),
    dispensing_fee_dangerous_drug DECIMAL(10,2),
    dispensing_fee_extra DECIMAL(10,2),
    dispensing_fee_extemporaneous DECIMAL(10,2),
    safety_net_recording_fee_ep DECIMAL(10,2),
    safety_net_recording_fee_rp DECIMAL(10,2),
    dispensing_fee_water_added DECIMAL(10,2),
    container_fee_injectable DECIMAL(10,2),
    container_fee_other DECIMAL(10,2),
    gnrl_copay_discount_general DECIMAL(10,2),
    gnrl_copay_discount_hospital DECIMAL(10,2),
    con_copay_discount_general DECIMAL(10,2),
    con_copay_discount_hospital DECIMAL(10,2),
    efc_diluent_fee DECIMAL(10,2),
    efc_preparation_fee DECIMAL(10,2),
    efc_distribution_fee DECIMAL(10,2),
    acss_imdq60_payment DECIMAL(10,2),
    acss_payment DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 8.3 Relationship Tables

#### ITEM_ATC_RELATIONSHIP
```sql
CREATE TABLE item_atc_relationship (
    li_item_id VARCHAR(100) REFERENCES item(li_item_id),
    atc_code VARCHAR(20) REFERENCES atc_code(atc_code),
    atc_priority_pct INTEGER,
    schedule_code VARCHAR(20),
    PRIMARY KEY (li_item_id, atc_code, schedule_code)
);
```

#### ITEM_RESTRICTION_RELATIONSHIP
```sql
CREATE TABLE item_restriction_relationship (
    li_item_id VARCHAR(100) REFERENCES item(li_item_id),
    res_code VARCHAR(100) REFERENCES restriction(res_code),
    res_position INTEGER,
    schedule_code VARCHAR(20),
    PRIMARY KEY (li_item_id, res_code, schedule_code)
);
```

#### ITEM_ORGANISATION_RELATIONSHIP
```sql
CREATE TABLE item_organisation_relationship (
    li_item_id VARCHAR(100) REFERENCES item(li_item_id),
    organisation_id INTEGER REFERENCES organisation(organisation_id),
    schedule_code VARCHAR(20),
    PRIMARY KEY (li_item_id, organisation_id, schedule_code)
);
```

### 8.4 Additional Reference Tables

Other important tables included in the schema:
- **CONTAINER** - Packaging/container details
- **DISPENSING_RULE** - Rules for item dispensing
- **CRITERIA** - Restriction criteria
- **PARAMETER** - Criteria parameters
- **AMT_ITEM** - Australian Medicines Terminology items
- **EXTEMPORANEOUS_PREPARATION** - Compounded preparations
- **EXTEMPORANEOUS_INGREDIENT** - Ingredients in preparations
- **STANDARD_FORMULA_PREPARATION** - Standard formula preparations
- **MARKUP_BAND** - Pricing markup bands
- **PRESCRIBER** - Authorized prescribers
- Additional relationship tables for all the above entities

## 9. Additional Resources

- API Documentation: `/docs`
- OpenAPI Spec: `/openapi.json`
- PBS API: https://data-api.health.gov.au/pbs/api/v3

## 11. Implementation Checklist (Executable Plan)

This section converts the design into actionable, build-ready tasks and concrete artifacts.

### 11.1 Target Repository Layout

```text
pbs-explorer/
  __init__.py
  main.py
  config.py
  api/
    __init__.py
    deps.py
    routers/
      items.py
      restrictions.py
      organisations.py
      atc_codes.py
      schedules.py
      reports.py
      admin.py
    schemas/
      items.py
      restrictions.py
      organisations.py
      atc_codes.py
      schedules.py
      reports.py
      admin.py
  db/
    __init__.py
    session.py
    base.py
    models/
      schedule.py
      item.py
      restriction.py
      atc_code.py
      organisation.py
      indication.py
      prescribing_text.py
      copayment.py
      fee.py
      relationships.py
  services/
    __init__.py
    sync/
      __init__.py
      client.py
      parser.py
      upsert.py
      orchestrator.py
      status.py
  web/
    __init__.py
    templates/
      base.html
      home.html
      search.html
      browse.html
      item_detail.html
      reports.html
      admin.html
    static/
      app.css
      app.js
  tasks/
    __init__.py
    sync.py
  tests/
    __init__.py
    api/
    services/
    db/
```

### 11.2 Data Layer Implementation Checklist

- [ ] Implement SQLAlchemy Base, engine, and session management.
- [ ] Implement core models for schedule, item, restriction, atc_code, organisation, indication, prescribing_text, copayment, fee.
- [ ] Implement relationship tables and indexes.
- [ ] Add migrations or schema bootstrap for SQLite and PostgreSQL.
- [ ] Add seed and sanity checks for schedules and reference data.

### 11.3 Data Sync Service Checklist

- [ ] PBS API client with subscription-key header and configurable base URL.
- [ ] Robust CSV and JSON parsing with schema validation.
- [ ] Upsert logic by primary keys with conflict handling.
- [ ] Sync orchestration with dependency ordering and checkpoints.
- [ ] Sync status tracking and progress logging.
- [ ] Cache invalidation and data freshness tracking.

### 11.4 API Layer Checklist

- [ ] Pydantic schemas for requests and responses.
- [ ] Filter parser for query parameters (including arrays, ranges, and booleans).
- [ ] Pagination and sorting with consistent metadata.
- [ ] Routers for items, restrictions, organisations, atc codes, schedules, reports, admin.
- [ ] Relationship includes for item detail expansion.
- [ ] Consistent error handling and validation messages.

### 11.5 Web UI Checklist

- [ ] Base layout, navigation, and shared components.
- [ ] Search page with advanced filters and HTMX-driven results.
- [ ] Item detail page with tabbed related data sections.
- [ ] Browse pages for ATC, programs, manufacturers, therapeutic groups.
- [ ] Reports catalog and generation UI.
- [ ] Admin dashboard for sync status and configuration.
- [ ] Responsive styles and accessibility checks.

### 11.6 Reporting and Analytics Checklist

- [ ] Implement report queries for program counts, benefit types, ATC levels.
- [ ] Implement change reports between schedules (price, restriction, listing status).
- [ ] Export formats for CSV and JSON.

### 11.7 Quality, Testing, and Operations Checklist

- [ ] Unit tests for filter parsing, model validation, and sync utilities.
- [ ] Integration tests for core endpoints and sync workflows.
- [ ] Data integrity checks and schema consistency tests.
- [ ] Structured logging with correlation IDs.
- [ ] Configuration validation and environment overrides.
- [ ] Performance baselines and query profiling.

### 11.8 Milestone Acceptance Criteria

- [ ] Phase 2 complete when a full sync completes end-to-end with no validation errors.
- [ ] Phase 3 complete when core endpoints return paginated results with filters.
- [ ] Phase 5 complete when search UI renders results and item detail pages load.
- [ ] Phase 7 complete when reports run and export successfully.
- [ ] Phase 8 complete when admin sync controls and audit logs are available.

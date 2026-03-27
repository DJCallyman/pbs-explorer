# Saved Reports

Saved reports are currently file-backed.

Manifest path:

`data/saved_reports/manifest.json`

Each report gets:

- a human-friendly entry on `/saved-reports`
- a stable chart CSV URL at `/web/saved-reports/<slug>.csv`
- a JSON metadata URL at `/web/saved-reports/<slug>.json`

## Example

```json
{
  "reports": [
    {
      "slug": "cemiplimab-nsclc-state-12m",
      "name": "Cemiplimab NSCLC State 12M",
      "description": "Monthly services by state for the current tracked NSCLC item codes.",
      "source_type": "search_based",
      "search": {
        "drug_name": "cemiplimab",
        "indication": "NSCLC",
        "schedule_mode": "all"
      },
      "report": {
        "var": "SERVICES",
        "rpt_fmt": "2",
        "window": {
          "type": "rolling_months",
          "months": 12
        }
      }
    }
  ]
}
```

## Source Types

`search_based`
- resolves item codes from the PBS Explorer search filters each time

`fixed_codes`
- uses a fixed list of PBS codes

Example:

```json
{
  "slug": "nivolumab-fixed-state-12m",
  "name": "Nivolumab Fixed Codes State 12M",
  "source_type": "fixed_codes",
  "codes": ["10745M", "10748Q"],
  "report": {
    "var": "SERVICES",
    "rpt_fmt": "2",
    "window": {
      "type": "rolling_months",
      "months": 12
    }
  }
}
```

## Window Types

`rolling_months`
- counts back from the configured Medicare end month

`since_first_listing`
- starts from the first PBS listing date among the resolved codes

`explicit`
- use fixed `start_date` and `end_date` in `YYYYMM`

from __future__ import annotations

from db.models import (
    ATCCode,
    BaseReference,
    Copayment,
    Fee,
    Indication,
    Item,
    Organisation,
    PrescribingText,
    Restriction,
    Schedule,
)

SYNC_PLAN = {
    "schedules": {"model": Schedule, "key_fields": ["schedule_code"]},
    "programs": {"model": BaseReference, "key_fields": ["id"], "extra_fields": {"endpoint": "programs"}},
    "organisations": {"model": Organisation, "key_fields": ["organisation_id"]},
    "containers": {"model": BaseReference, "key_fields": ["id"], "extra_fields": {"endpoint": "containers"}},
    "atc-codes": {"model": ATCCode, "key_fields": ["atc_code"]},
    "dispensing-rules": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "dispensing-rules"},
    },
    "criteria": {"model": BaseReference, "key_fields": ["id"], "extra_fields": {"endpoint": "criteria"}},
    "parameters": {"model": BaseReference, "key_fields": ["id"], "extra_fields": {"endpoint": "parameters"}},
    "prescribing-texts": {"model": PrescribingText, "key_fields": ["prescribing_txt_id"]},
    "indications": {"model": Indication, "key_fields": ["indication_prescribing_txt_id"]},
    "copayments": {"model": Copayment, "key_fields": ["id"]},
    "fees": {"model": Fee, "key_fields": ["id"]},
    "restrictions": {"model": Restriction, "key_fields": ["res_code"]},
    "items": {"model": Item, "key_fields": ["li_item_id"]},
    "item-atc-relationships": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "item-atc-relationships"},
    },
    "item-organisation-relationships": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "item-organisation-relationships"},
    },
    "item-restriction-relationships": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "item-restriction-relationships"},
    },
    "item-dispensing-rule-relationships": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "item-dispensing-rule-relationships"},
    },
    "item-prescribing-text-relationships": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "item-prescribing-text-relationships"},
    },
    "restriction-prescribing-text-relationships": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "restriction-prescribing-text-relationships"},
    },
    "criteria-parameter-relationships": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "criteria-parameter-relationships"},
    },
    "container-organisation-relationships": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "container-organisation-relationships"},
    },
    "item-pricing-events": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "item-pricing-events"},
    },
    "amt-items": {"model": BaseReference, "key_fields": ["id"], "extra_fields": {"endpoint": "amt-items"}},
    "extemporaneous-preparations": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "extemporaneous-preparations"},
    },
    "extemporaneous-ingredients": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "extemporaneous-ingredients"},
    },
    "extemporaneous-tariffs": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "extemporaneous-tariffs"},
    },
    "standard-formula-preparations": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "standard-formula-preparations"},
    },
    "markup-bands": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "markup-bands"},
    },
    "prescribers": {"model": BaseReference, "key_fields": ["id"], "extra_fields": {"endpoint": "prescribers"}},
    "summary-of-changes": {
        "model": BaseReference,
        "key_fields": ["id"],
        "extra_fields": {"endpoint": "summary-of-changes"},
    },
}

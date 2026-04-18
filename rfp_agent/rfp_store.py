"""
Simple JSON-file-backed RFP store.
All records are persisted to data/rfps.json relative to the project root.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

DATA_DIR = Path(__file__).parent.parent / "data"
RFP_FILE = DATA_DIR / "rfps.json"

# Lifecycle: draft → published → approved_for_submission → done → archived
# Any status can be archived. published can be pulled back to draft.
VALID_STATUSES = ("draft", "published", "approved_for_submission", "done", "archived")

_TRANSITIONS: Dict[str, List[str]] = {
    "draft":                   ["published", "archived"],
    "published":               ["approved_for_submission", "draft", "archived"],
    "approved_for_submission": ["done", "archived"],
    "done":                    ["archived"],
    "archived":                [],
}

# Legacy mapping: old "approved" → "published" for backward compat with existing data
_LEGACY_STATUS_MAP = {"approved": "published"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _migrate_legacy(records: List[dict]) -> List[dict]:
    """Migrate legacy status values to current lifecycle."""
    changed = False
    for r in records:
        legacy = _LEGACY_STATUS_MAP.get(r.get("status"))
        if legacy:
            r["status"] = legacy
            changed = True
        if "bids" not in r:
            r["bids"] = []
            changed = True
        if "archived_at" not in r:
            r["archived_at"] = None
            changed = True
    return records if not changed else records


def _load() -> List[dict]:
    if not RFP_FILE.exists():
        return []
    try:
        records = json.loads(RFP_FILE.read_text(encoding="utf-8"))
        return _migrate_legacy(records)
    except Exception:
        return []


def _save(records: List[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RFP_FILE.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def create_rfp(
    title: str,
    description: str,
    language: str,
    created_by: str,
    invited_users: List[str],
) -> dict:
    record = {
        "id":              str(uuid.uuid4()),
        "title":           title,
        "description":     description,
        "language":        language if language in ("en", "ar") else "en",
        "created_by":      created_by,
        "invited_users":   invited_users,
        "status":          "draft",
        "assigned_vendor": None,
        "rfp_content":     None,
        "evaluation":      None,
        "risk_heatmap":    None,
        "bids":            [],
        "archived_at":     None,
        "created_at":      _now(),
        "updated_at":      _now(),
    }
    records = _load()
    records.append(record)
    _save(records)
    return record


def list_rfps() -> List[dict]:
    return _load()


def get_rfp(rfp_id: str) -> Optional[dict]:
    for r in _load():
        if r["id"] == rfp_id:
            return r
    return None


def patch_rfp(rfp_id: str, updates: dict) -> Optional[dict]:
    """
    Apply partial updates to an RFP.
    Raises ValueError on invalid status or illegal transition.
    Returns None if rfp_id not found.
    """
    records = _load()
    for i, r in enumerate(records):
        if r["id"] != rfp_id:
            continue

        if "status" in updates:
            new_status = updates["status"]
            # Normalize legacy status
            new_status = _LEGACY_STATUS_MAP.get(new_status, new_status)
            updates["status"] = new_status
            if new_status not in VALID_STATUSES:
                raise ValueError(f"Invalid status '{new_status}'. Must be one of: {VALID_STATUSES}")
            current = r["status"]
            if new_status != current and new_status not in _TRANSITIONS[current]:
                raise ValueError(
                    f"Cannot transition from '{current}' to '{new_status}'. "
                    f"Allowed: {_TRANSITIONS[current] or 'none (terminal state)'}"
                )
            if new_status == "archived":
                r["archived_at"] = _now()

        allowed = {"status", "rfp_content", "assigned_vendor", "invited_users",
                   "evaluation", "risk_heatmap", "bids"}
        for field in allowed:
            if field in updates and updates[field] is not None:
                r[field] = updates[field]

        r["updated_at"] = _now()
        records[i] = r
        _save(records)
        return r

    return None


def delete_rfp(rfp_id: str) -> bool:
    records = _load()
    original_len = len(records)
    records = [r for r in records if r["id"] != rfp_id]
    if len(records) < original_len:
        _save(records)
        return True
    return False


def append_bid(rfp_id: str, bid: dict) -> Optional[dict]:
    """Append a bid record to an RFP's bids list. Returns the updated record."""
    records = _load()
    for i, r in enumerate(records):
        if r["id"] != rfp_id:
            continue
        if "bids" not in r or r["bids"] is None:
            r["bids"] = []
        bid_with_meta = {
            "id":         str(uuid.uuid4()),
            "submitted_at": _now(),
            **bid,
        }
        r["bids"].append(bid_with_meta)
        r["updated_at"] = _now()
        records[i] = r
        _save(records)
        return r
    return None

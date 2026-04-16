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

VALID_STATUSES = ("draft", "approved", "done")

# Which statuses a given status can transition into
_TRANSITIONS: Dict[str, List[str]] = {
    "draft":    ["approved"],
    "approved": ["done"],
    "done":     [],
}


# ── Internal helpers ─────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> List[dict]:
    if not RFP_FILE.exists():
        return []
    try:
        return json.loads(RFP_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(records: List[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RFP_FILE.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── Public API ────────────────────────────────────────────────────────────────

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
    Apply partial updates to an RFP.  Allowed fields:
      status, rfp_content, assigned_vendor, invited_users, evaluation, risk_heatmap

    Raises ValueError on invalid status or illegal transition.
    Returns None if rfp_id not found.
    """
    records = _load()
    for i, r in enumerate(records):
        if r["id"] != rfp_id:
            continue

        # Validate status transition
        if "status" in updates:
            new_status = updates["status"]
            if new_status not in VALID_STATUSES:
                raise ValueError(f"Invalid status '{new_status}'. Must be one of: {VALID_STATUSES}")
            current = r["status"]
            if new_status != current and new_status not in _TRANSITIONS[current]:
                raise ValueError(
                    f"Cannot transition from '{current}' to '{new_status}'. "
                    f"Allowed: {_TRANSITIONS[current] or 'none (terminal state)'}"
                )

        allowed = {"status", "rfp_content", "assigned_vendor", "invited_users", "evaluation", "risk_heatmap"}
        for field in allowed:
            if field in updates and updates[field] is not None:
                r[field] = updates[field]

        r["updated_at"] = _now()
        records[i] = r
        _save(records)
        return r

    return None


def delete_rfp(rfp_id: str) -> bool:
    """
    Delete an RFP from the local store.
    Returns True if found and deleted, False otherwise.
    """
    records = _load()
    original_len = len(records)
    records = [r for r in records if r["id"] != rfp_id]
    if len(records) < original_len:
        _save(records)
        return True
    return False

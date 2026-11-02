"""Human-in-the-loop lexicon learning.

Users submit suggestions (what was said + what it meant). A trusted reviewer
approves or rejects each one. Only approved suggestions become lexicon
entries. Everything is stored in append-only JSON Lines files, so the full
history is auditable.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

from .lexicon import Entry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SuggestionStore:
    def __init__(self, folder: Union[str, Path]):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.suggestions_file = self.folder / "suggestions.jsonl"
        self.reviews_file = self.folder / "reviews.jsonl"

    # ---------- storage ----------
    @staticmethod
    def _read(path: Path) -> List[dict]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @staticmethod
    def _append(path: Path, record: dict) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ---------- workflow ----------
    def submit(self, said: str, meaning: str, clinical_term: str = "",
               language: str = "", department: str = "") -> str:
        """Record a suggestion. Returns its id."""
        if not (said or "").strip() or not (meaning or "").strip():
            raise ValueError("Both what was said and its meaning are required.")
        sid = uuid.uuid4().hex[:10]
        self._append(self.suggestions_file, {
            "id": sid, "time_utc": _now(), "said": said.strip(), "meaning": meaning.strip(),
            "clinical_term": (clinical_term or "").strip(), "language": language, "department": department,
        })
        return sid

    def pending(self) -> List[dict]:
        decided = {r["id"] for r in self._read(self.reviews_file)}
        return [s for s in self._read(self.suggestions_file) if s["id"] not in decided]

    def review(self, suggestion_id: str, approve: bool, reviewer: str,
               phrase: Optional[str] = None, meaning: Optional[str] = None,
               clinical_term: Optional[str] = None, danger: bool = False) -> None:
        """Approve (optionally correcting the wording) or reject a pending suggestion."""
        match = [s for s in self.pending() if s["id"] == suggestion_id]
        if not match:
            raise KeyError(f"No pending suggestion with id {suggestion_id!r}")
        if not (reviewer or "").strip():
            raise ValueError("A reviewer name is required for the audit trail.")
        s = match[0]
        self._append(self.reviews_file, {
            "id": suggestion_id, "time_utc": _now(), "decision": "approved" if approve else "rejected",
            "reviewer": reviewer.strip(),
            "phrase": (phrase or s["said"]).strip(),
            "meaning": (meaning or s["meaning"]).strip(),
            "clinical_term": (clinical_term or s["clinical_term"] or meaning or s["meaning"]).strip(),
            "language": s.get("language", ""), "department": s.get("department", ""),
            "danger": bool(danger),
        })

    def approved_entries(self, language: Optional[str] = None) -> List[Entry]:
        """Approved suggestions as lexicon entries (filter by language if given)."""
        out = []
        for r in self._read(self.reviews_file):
            if r.get("decision") != "approved":
                continue
            if language and r.get("language") not in ("", language):
                continue
            out.append(Entry(phrase=r["phrase"], meaning=r["meaning"], clinical_term=r["clinical_term"],
                             language=r.get("language", ""), department=r.get("department", ""),
                             danger=r.get("danger", False), source="learned"))
        return out

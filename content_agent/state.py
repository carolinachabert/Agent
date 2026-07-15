"""Per-batch pipeline state, persisted as plain files under data/batches/<batch_id>/.

A "batch" is one filming cycle (Karolina films every 2-3 weeks in one session).
Everything the agent produces for that cycle — references, plan, captions,
approval record, schedule receipt — lives in one folder so the whole cycle is
inspectable and diffable in git.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BATCHES_DIR = DATA_DIR / "batches"
INBOX_DIR = DATA_DIR / "inbox"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BatchState:
    batch_id: str

    @property
    def dir(self) -> Path:
        d = BATCHES_DIR / self.batch_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def references_path(self) -> Path:
        return self.dir / "references.md"

    @property
    def plan_path(self) -> Path:
        return self.dir / "plan.md"

    @property
    def captions_path(self) -> Path:
        return self.dir / "captions.md"

    @property
    def approval_path(self) -> Path:
        return self.dir / "APPROVAL.json"

    @property
    def schedule_receipt_path(self) -> Path:
        return self.dir / "schedule_receipt.json"

    def append_reference(self, source: str, note: str) -> None:
        entry = f"- **{_now()}** ({source}): {note}\n"
        with self.references_path.open("a", encoding="utf-8") as f:
            f.write(entry)

    def read_references(self) -> str:
        if not self.references_path.exists():
            return "(no references logged yet)"
        return self.references_path.read_text(encoding="utf-8")

    def save_plan(self, content: str) -> None:
        self.plan_path.write_text(content, encoding="utf-8")

    def read_plan(self) -> str:
        if not self.plan_path.exists():
            raise FileNotFoundError(
                f"No plan.md for batch '{self.batch_id}' yet — run the scan/plan stage first."
            )
        return self.plan_path.read_text(encoding="utf-8")

    def save_captions(self, content: str) -> None:
        self.captions_path.write_text(content, encoding="utf-8")

    def read_captions(self) -> str:
        if not self.captions_path.exists():
            raise FileNotFoundError(
                f"No captions.md for batch '{self.batch_id}' yet — run the captions stage first."
            )
        return self.captions_path.read_text(encoding="utf-8")

    def is_approved(self) -> bool:
        return self.approval_path.exists()

    def approval_record(self) -> dict | None:
        if not self.approval_path.exists():
            return None
        return json.loads(self.approval_path.read_text(encoding="utf-8"))

    def record_approval(self, reviewer: str, note: str = "") -> dict:
        record = {
            "batch_id": self.batch_id,
            "reviewer": reviewer,
            "note": note,
            "approved_at": _now(),
        }
        self.approval_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record

    def revoke_approval(self) -> None:
        if self.approval_path.exists():
            self.approval_path.unlink()

    def record_schedule_receipt(self, receipt: dict) -> None:
        self.schedule_receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")


def list_batches() -> list[str]:
    if not BATCHES_DIR.exists():
        return []
    return sorted(p.name for p in BATCHES_DIR.iterdir() if p.is_dir())

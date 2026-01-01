# Licensed under the MIT License.
# Run summary contract for AXI CLI operations.

"""
Machine-readable run summary for CI/CD integration.

Every multi-item AXI operation MUST emit a run summary that:
- Is machine-readable (JSON)
- Includes explicit counts of all outcomes
- Never hides failures
- Uses status enum with clear semantics
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from axi.version import SCHEMA_VERSION


@dataclass
class FailureEntry:
    """A single failed item with error details."""
    item: str
    error: str


@dataclass
class SkippedEntry:
    """A single skipped item with reason."""
    item: str
    reason: str


@dataclass
class RunSummary:
    """
    Machine-readable summary of an AXI operation.

    Status semantics:
    - success: All items processed without error
    - partial_success: Some items processed, some failed/skipped due to error
    - failure: Zero items processed successfully
    - error: Command failed to execute (config error, etc.)
    """
    command: str
    status: str  # success | partial_success | failure | error
    exit_code: int
    scanned: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    failures: List[FailureEntry] = field(default_factory=list)
    skipped_items: List[SkippedEntry] = field(default_factory=list)
    schema_version: str = field(default_factory=lambda: SCHEMA_VERSION)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "schema_version": self.schema_version,
            "command": self.command,
            "status": self.status,
            "exit_code": self.exit_code,
            "counts": {
                "scanned": self.scanned,
                "processed": self.processed,
                "skipped": self.skipped,
                "failed": self.failed,
            },
            "failures": [{"item": f.item, "error": f.error} for f in self.failures],
            "skipped": [{"item": s.item, "reason": s.reason} for s in self.skipped_items],
            # Timestamps allowed in run summary (not in semantic artifacts)
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @staticmethod
    def now_iso() -> str:
        """Get current time in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def compute_status(cls, processed: int, failed: int) -> str:
        """Compute status from counts."""
        if failed == 0 and processed > 0:
            return "success"
        elif processed > 0 and failed > 0:
            return "partial_success"
        elif processed == 0 and failed > 0:
            return "failure"
        elif processed == 0 and failed == 0:
            return "success"  # Empty input is success
        return "error"

    @classmethod
    def compute_exit_code(cls, status: str) -> int:
        """Map status to exit code."""
        from . import exit_codes
        if status == "success":
            return exit_codes.SUCCESS
        elif status in ("partial_success", "failure"):
            return exit_codes.EXTRACTION_ERROR
        else:
            return exit_codes.GENERAL_ERROR

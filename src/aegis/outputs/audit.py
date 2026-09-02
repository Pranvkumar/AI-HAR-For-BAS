"""Tamper-evident audit trail.

The session log already records what happened. What it could not do was let a
reviewer establish that the record had not been edited afterwards -- which, for
a system whose output is evidence that a scientific protocol was followed
correctly, is the property that actually matters.

Each entry carries the hash of the previous entry, so the file is a chain:

    entry 0   prev=GENESIS          hash=a3f1...
    entry 1   prev=a3f1...          hash=9b2c...
    entry 2   prev=9b2c...          hash=41de...

Changing entry 1 changes its hash, which breaks entry 2's ``prev``, and every
entry after it. :func:`verify_chain` walks the file and reports the first index
where the chain breaks.

This is **tamper-evident, not tamper-proof.** Anyone with write access can
recompute the whole chain. Calling it "blockchain" or "military-grade" would be
dishonest and a reviewer would be right to push back. The honest claim is:
accidental corruption and casual edits are detectable.

Also defines the four-level event hierarchy from the Round-2 brief, so that a
perception fact and a protocol decision are distinguishable in the record rather
than being flattened into one stream of strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import threading
import time

GENESIS = "0" * 64


class EventLevel(str, Enum):
    """Four levels, coarsening from raw observation to protocol decision."""

    PERCEPTION = "perception"      # a frame was scored, a landmark seen
    INTERACTION = "interaction"    # a hand contacted an object, entered a zone
    ACTION = "action"              # an action was recognised
    PROTOCOL = "protocol"          # a step was verified, skipped, blocked
    SYSTEM = "system"              # health, faults, operator overrides


@dataclass
class AuditEntry:
    index: int
    level: EventLevel
    kind: str
    message: str
    utc: str
    monotonic_s: float
    payload: dict = field(default_factory=dict)
    prev_hash: str = GENESIS
    entry_hash: str = ""

    def digest(self) -> str:
        """Hash over every field except the hash itself, order-stable."""
        body = {
            "index": self.index,
            "level": self.level.value,
            "kind": self.kind,
            "message": self.message,
            "utc": self.utc,
            "monotonic_s": round(self.monotonic_s, 4),
            "payload": self.payload,
            "prev_hash": self.prev_hash,
        }
        raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["level"] = self.level.value
        return d


class AuditTrail:
    """Append-only, hash-chained JSONL event log."""

    def __init__(self, path: str | Path, *, session_id: str, flush_each: bool = True) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id
        self.flush_each = flush_each
        self.entries: list[AuditEntry] = []
        self._lock = threading.Lock()
        self._started = time.monotonic()
        self._last_hash = GENESIS
        self._fh = self.path.open("w", encoding="utf-8", buffering=1)
        self.append(
            EventLevel.SYSTEM, "audit_opened",
            f"Audit trail opened for session {session_id}",
            {"session_id": session_id, "algorithm": "sha256", "chain": "prev_hash"},
        )

    # ------------------------------------------------------------------ write

    def append(self, level: EventLevel, kind: str, message: str, payload: dict | None = None) -> AuditEntry:
        with self._lock:
            entry = AuditEntry(
                index=len(self.entries),
                level=level,
                kind=kind,
                message=message,
                utc=datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds"),
                monotonic_s=time.monotonic() - self._started,
                payload=dict(payload or {}),
                prev_hash=self._last_hash,
            )
            entry.entry_hash = entry.digest()
            self._last_hash = entry.entry_hash
            self.entries.append(entry)
            try:
                if self._fh is not None:
                    self._fh.write(json.dumps(entry.to_dict(), default=str) + "\n")
            except Exception:
                pass
            return entry

    # convenience wrappers keep call sites readable at the point of use
    def perception(self, kind: str, message: str, **payload) -> AuditEntry:
        return self.append(EventLevel.PERCEPTION, kind, message, payload)

    def interaction(self, kind: str, message: str, **payload) -> AuditEntry:
        return self.append(EventLevel.INTERACTION, kind, message, payload)

    def action(self, kind: str, message: str, **payload) -> AuditEntry:
        return self.append(EventLevel.ACTION, kind, message, payload)

    def protocol(self, kind: str, message: str, **payload) -> AuditEntry:
        return self.append(EventLevel.PROTOCOL, kind, message, payload)

    def system(self, kind: str, message: str, **payload) -> AuditEntry:
        return self.append(EventLevel.SYSTEM, kind, message, payload)

    # ----------------------------------------------------------------- verify

    @property
    def head(self) -> str:
        return self._last_hash

    def verify(self) -> tuple[bool, int | None, str]:
        """Verify the in-memory chain. Returns (ok, first_bad_index, message)."""
        return verify_entries(self.entries)

    def close(self, summary: dict | None = None) -> str:
        """Seal the trail. The returned head hash is what you quote."""
        self.append(
            EventLevel.SYSTEM, "audit_sealed",
            "Audit trail sealed",
            {"entries": len(self.entries) + 1, **(summary or {})},
        )
        with self._lock:
            try:
                if self._fh is not None:
                    self._fh.close()
            except Exception:
                pass
            self._fh = None
        return self._last_hash

    def counts(self) -> dict:
        out: dict[str, int] = {}
        for e in self.entries:
            out[e.level.value] = out.get(e.level.value, 0) + 1
        return out


# ================================================================== verifying

def verify_entries(entries: list[AuditEntry]) -> tuple[bool, int | None, str]:
    previous = GENESIS
    for i, entry in enumerate(entries):
        if entry.index != i:
            return False, i, f"entry {i} declares index {entry.index}"
        if entry.prev_hash != previous:
            return False, i, f"entry {i} prev_hash does not match entry {i - 1}"
        if entry.digest() != entry.entry_hash:
            return False, i, f"entry {i} content does not match its hash - modified"
        previous = entry.entry_hash
    return True, None, f"chain intact across {len(entries)} entries"


def verify_file(path: str | Path) -> tuple[bool, int | None, str]:
    """Verify a written audit file. This is what a reviewer runs."""
    path = Path(path)
    if not path.exists():
        return False, None, f"no audit file at {path}"

    entries: list[AuditEntry] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            entries.append(AuditEntry(
                index=int(data["index"]),
                level=EventLevel(data["level"]),
                kind=str(data["kind"]),
                message=str(data["message"]),
                utc=str(data["utc"]),
                monotonic_s=float(data["monotonic_s"]),
                payload=data.get("payload", {}),
                prev_hash=str(data["prev_hash"]),
                entry_hash=str(data["entry_hash"]),
            ))
        except Exception as exc:
            return False, lineno, f"line {lineno} is not a valid audit entry: {exc}"

    if not entries:
        return False, None, "audit file is empty"
    return verify_entries(entries)


def file_checksum(path: str | Path) -> str:
    """SHA-256 of a file, for model and config provenance."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def write_checksums(paths: list[str | Path], out_path: str | Path) -> Path:
    """Write a SHA256SUMS file for a set of deployed artefacts."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for p in paths:
        p = Path(p)
        if p.exists() and p.is_file():
            lines.append(f"{file_checksum(p)}  {p.name}")
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out_path

"""Evidence fusion, uncertainty, and explainability.

The single biggest weakness of a hackathon HAR system is that it says
``confidence = 0.94`` and nothing else. That is unfalsifiable. A reviewer cannot
tell whether the number came from strong agreement across independent signals or
from one over-confident network on a blurry frame.

This module replaces that with an auditable verdict:

    STEP 04 VERIFIED
      + hand entered zone 'sample_tray'          weight 0.25   score 0.97
      + grip released after dwell 1.4 s          weight 0.20   score 0.91
      + temporal model agrees ('transfer')       weight 0.30   score 0.88
      + rack localisation locked (aruco)         weight 0.15   score 0.99
      - camera quality degraded                  weight 0.10   score 0.75
      = fused 0.906  ->  VERIFIED

Two design commitments:

**Uncertainty is a first-class outcome.** The verdict is one of VERIFIED,
REJECTED, UNCERTAIN or NOT_OBSERVABLE. A system that must always choose a class
will happily assert nonsense about an empty frame; this one is allowed to say it
does not know, and the protocol engine treats that differently from a rejection.

**No single source can carry a decision.** Weighted fusion with a veto list, so
an unusable camera or a lost rack frame forces NOT_OBSERVABLE regardless of how
confident the classifier is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time

import numpy as np


class Verdict(str, Enum):
    VERIFIED = "verified"              # act on it
    REJECTED = "rejected"              # confidently the wrong action
    UNCERTAIN = "uncertain"            # evidence conflicts or is weak
    NOT_OBSERVABLE = "not_observable"  # we cannot see well enough to judge

    @property
    def actionable(self) -> bool:
        return self is Verdict.VERIFIED


class Source(str, Enum):
    """Where a piece of evidence came from. Kept explicit for the audit log."""

    ZONE = "zone"
    GRIP = "grip"
    DWELL = "dwell"
    MOTION = "motion"
    TEMPORAL_MODEL = "temporal_model"
    OBJECT = "object"
    INTERACTION = "interaction"
    RACK = "rack"
    CAMERA = "camera"
    OPERATOR = "operator"


@dataclass
class Evidence:
    """One independent signal contributing to a decision."""

    source: Source
    label: str                 # human-readable, appears verbatim in the log
    score: float               # 0-1, how strongly this supports the hypothesis
    weight: float              # 0-1, how much this source is trusted
    detail: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.score = float(np.clip(self.score, 0.0, 1.0))
        self.weight = float(np.clip(self.weight, 0.0, 1.0))

    @property
    def contribution(self) -> float:
        return self.score * self.weight

    def render(self) -> str:
        mark = "+" if self.score >= 0.5 else "-"
        return f"{mark} {self.label:<44} w{self.weight:.2f}  s{self.score:.2f}"

    def to_dict(self) -> dict:
        return {
            "source": self.source.value,
            "label": self.label,
            "score": round(self.score, 3),
            "weight": round(self.weight, 3),
            **({"detail": self.detail} if self.detail else {}),
        }


@dataclass
class FusedDecision:
    """The result of fusing all evidence for one hypothesis."""

    action: str | None
    verdict: Verdict
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)
    vetoes: list[str] = field(default_factory=list)
    monotonic: float = field(default_factory=time.monotonic)

    @property
    def actionable(self) -> bool:
        return self.verdict is Verdict.VERIFIED

    def explain(self, header: str | None = None) -> str:
        """Human-readable justification. This is what goes in the report."""
        lines = [header or f"{(self.action or 'no action').upper()}  ->  {self.verdict.value.upper()}"]
        for ev in sorted(self.evidence, key=lambda e: -e.contribution):
            lines.append("    " + ev.render())
        for veto in self.vetoes:
            lines.append(f"    ! VETO  {veto}")
        lines.append(f"    = fused {self.confidence:.3f}  ->  {self.verdict.value.upper()}")
        return "\n".join(lines)

    def reason(self) -> str:
        """One-line reason, suitable for the GUI and for speech."""
        if self.vetoes:
            return self.vetoes[0]
        if not self.evidence:
            return "no supporting evidence"
        top = max(self.evidence, key=lambda e: e.contribution)
        weak = [e for e in self.evidence if e.score < 0.4]
        if self.verdict is Verdict.VERIFIED:
            return f"strongest signal: {top.label}"
        if weak:
            return f"insufficient: {weak[0].label}"
        return f"weak agreement (fused {self.confidence:.2f})"

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 4),
            "evidence": [e.to_dict() for e in self.evidence],
            "vetoes": list(self.vetoes),
        }


# Default trust weights. They sum to 1.0 when every source is present; the
# fuser renormalises when some are missing, so a run without an object detector
# is not silently penalised.
DEFAULT_WEIGHTS: dict[Source, float] = {
    Source.ZONE: 0.20,
    Source.GRIP: 0.12,
    Source.DWELL: 0.10,
    Source.MOTION: 0.08,
    Source.TEMPORAL_MODEL: 0.25,
    Source.OBJECT: 0.10,
    Source.INTERACTION: 0.10,
    Source.RACK: 0.05,
}


class EvidenceFuser:
    """Combines independent signals into a verdict, with vetoes.

    Fusion is a renormalised weighted mean rather than a product of
    probabilities: the sources are not independent (zone and interaction share
    the same hand track), so a product would be badly over-confident.
    """

    def __init__(
        self,
        *,
        weights: dict[Source, float] | None = None,
        verify_threshold: float = 0.62,
        reject_threshold: float = 0.28,
        min_sources: int = 2,
    ) -> None:
        self.weights = dict(weights or DEFAULT_WEIGHTS)
        self.verify_threshold = verify_threshold
        self.reject_threshold = reject_threshold
        self.min_sources = min_sources

    def weight_for(self, source: Source) -> float:
        return self.weights.get(source, 0.05)

    def evidence(self, source: Source, label: str, score: float, **detail) -> Evidence:
        """Convenience constructor applying the configured trust weight."""
        return Evidence(source, label, score, self.weight_for(source), detail)

    def fuse(
        self,
        action: str | None,
        evidence: list[Evidence],
        *,
        vetoes: list[str] | None = None,
        quality_scale: float = 1.0,
    ) -> FusedDecision:
        """Combine evidence into a verdict.

        ``quality_scale`` comes from the camera-health monitor. A degraded frame
        scales the fused confidence down rather than being treated as one more
        vote, because poor input undermines *every* other signal simultaneously.
        """
        vetoes = list(vetoes or [])

        if vetoes:
            return FusedDecision(action, Verdict.NOT_OBSERVABLE, 0.0, evidence, vetoes)

        if not evidence:
            return FusedDecision(action, Verdict.NOT_OBSERVABLE, 0.0, [],
                                 ["no evidence sources reported"])

        total_weight = sum(e.weight for e in evidence)
        if total_weight <= 1e-9:
            return FusedDecision(action, Verdict.UNCERTAIN, 0.0, evidence)

        fused = sum(e.contribution for e in evidence) / total_weight
        fused *= float(np.clip(quality_scale, 0.0, 1.0))

        distinct = {e.source for e in evidence}
        if len(distinct) < self.min_sources:
            # One source alone is never enough to verify a step. It can still
            # reject, because a single strong disagreement is informative.
            verdict = Verdict.REJECTED if fused <= self.reject_threshold else Verdict.UNCERTAIN
            return FusedDecision(action, verdict, fused, evidence)

        if fused >= self.verify_threshold:
            verdict = Verdict.VERIFIED
        elif fused <= self.reject_threshold:
            verdict = Verdict.REJECTED
        else:
            verdict = Verdict.UNCERTAIN

        return FusedDecision(action, verdict, fused, evidence)


def camera_veto(quality) -> list[str]:
    """Turn an unusable frame into a veto string. Empty list when usable."""
    if quality is None:
        return []
    if not getattr(quality, "usable", True):
        return [f"camera unusable: {'; '.join(quality.reasons) or 'unknown'}"]
    return []


def rack_veto(rack, *, min_confidence: float = 0.3) -> list[str]:
    """Veto when the rack frame has degenerated to whole-image normalisation."""
    if rack is None:
        return ["rack frame unavailable"]
    if getattr(rack, "source", "") == "identity":
        return ["rack not localised - zones cannot be trusted"]
    if getattr(rack, "confidence", 1.0) < min_confidence:
        return [f"rack localisation confidence {rack.confidence:.2f} below minimum"]
    return []

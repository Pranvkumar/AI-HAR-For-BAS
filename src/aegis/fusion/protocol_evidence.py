"""Relational evidence for nested-container procedures.

This keeps the useful containment history from the microgravity implementation
while using AEGIS Track and InteractionEvent objects at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from aegis.fusion.interaction import EventType


@dataclass(frozen=True)
class RelationalEvidence:
    """One change-only fact that can support a named protocol action."""

    action: str
    label: str
    score: float = 0.95
    weight: float = 0.18


class NestedContainerEvidence:
    """Infer removal and return of inner objects from a tracked container."""

    INNER_OBJECTS = ("red_box", "blue_box")

    def __init__(self) -> None:
        self._was_inside = {label: False for label in self.INNER_OBJECTS}
        self._was_removed = {label: False for label in self.INNER_OBJECTS}
        self._grasped = {label: False for label in self.INNER_OBJECTS}
        self._emitted: set[str] = set()

    @staticmethod
    def _inside(item, container) -> bool:
        ix1, iy1, ix2, iy2 = item.box
        cx1, cy1, cx2, cy2 = container.box
        return ix1 >= cx1 and iy1 >= cy1 and ix2 <= cx2 and iy2 <= cy2

    @staticmethod
    def _first(tracks, label):
        return next((track for track in tracks if track.label == label), None)

    def reset(self) -> None:
        self._was_inside = {label: False for label in self.INNER_OBJECTS}
        self._was_removed = {label: False for label in self.INNER_OBJECTS}
        self._grasped = {label: False for label in self.INNER_OBJECTS}
        self._emitted.clear()

    def _emit_once(self, key: str, evidence: RelationalEvidence, out: list[RelationalEvidence]) -> None:
        if key not in self._emitted:
            self._emitted.add(key)
            out.append(evidence)

    def process(self, tracks, interaction_events) -> list[RelationalEvidence]:
        """Return new removal/return facts from this frame."""
        for event in interaction_events or []:
            label = event.object_label
            if label not in self._grasped:
                continue
            if event.type is EventType.GRASP_CONFIRMED:
                self._grasped[label] = True
            elif event.type in (EventType.RELEASE_CONFIRMED, EventType.CONTACT_END):
                self._grasped[label] = False

        confirmed = [track for track in (tracks or []) if getattr(track, "confirmed", False)]
        container = self._first(confirmed, "outer_container")
        if container is None:
            return []

        out: list[RelationalEvidence] = []
        for label in self.INNER_OBJECTS:
            item = self._first(confirmed, label)
            if item is None:
                continue
            contained = self._inside(item, container)
            if contained:
                if self._was_removed[label] and not self._grasped[label]:
                    self._emit_once(
                        f"{label}:returned",
                        RelationalEvidence(
                            "stow_red_box" if label == "red_box" else "stow_blue_box",
                            f"{label} returned to outer container",
                        ),
                        out,
                    )
                self._was_inside[label] = True
                continue

            if self._was_inside[label] and self._grasped[label]:
                self._was_removed[label] = True
                self._emit_once(
                    f"{label}:removed",
                    RelationalEvidence(
                        "retrieve_red_box" if label == "red_box" else "retrieve_blue_box",
                        f"{label} removed from outer container",
                    ),
                    out,
                )
        return out
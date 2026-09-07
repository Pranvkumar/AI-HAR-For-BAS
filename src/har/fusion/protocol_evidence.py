"""Convert relational detector observations into mock-protocol evidence events."""

from __future__ import annotations

from har.events import Detection, InteractionEvent


class ProtocolEvidenceEngine:
    """Infer biological-fluid protocol evidence without gravity or fixed axes."""

    def __init__(self, injection_dwell_s: float = 2.0) -> None:
        self.injection_dwell_s = injection_dwell_s
        self._states: dict[str, bool] = {}
        self._overlap_started: dict[str, float] = {}
        self._was_in_rack: dict[str, bool] = {"sample_vial": False, "reagent_pipette": False}
        self._grasped: dict[str, bool] = {"sample_vial": False, "reagent_pipette": False}

    @staticmethod
    def _overlap(a: Detection, b: Detection) -> float:
        left, top = max(a.xyxy[0], b.xyxy[0]), max(a.xyxy[1], b.xyxy[1])
        right, bottom = min(a.xyxy[2], b.xyxy[2]), min(a.xyxy[3], b.xyxy[3])
        intersection = max(0.0, right - left) * max(0.0, bottom - top)
        area_a = max(0.0, a.xyxy[2] - a.xyxy[0]) * max(0.0, a.xyxy[3] - a.xyxy[1])
        area_b = max(0.0, b.xyxy[2] - b.xyxy[0]) * max(0.0, b.xyxy[3] - b.xyxy[1])
        return intersection / (area_a + area_b - intersection) if area_a + area_b - intersection else 0.0

    @staticmethod
    def _inside(item: Detection, container: Detection) -> bool:
        return item.xyxy[0] >= container.xyxy[0] and item.xyxy[1] >= container.xyxy[1] and item.xyxy[2] <= container.xyxy[2] and item.xyxy[3] <= container.xyxy[3]

    def _changed(self, key: str, active: bool) -> bool:
        previous = self._states.get(key, False)
        self._states[key] = active
        return active and not previous

    @staticmethod
    def _first(detections: list[Detection], cls: str) -> Detection | None:
        return next((item for item in detections if item.cls == cls), None)

    def process(self, detections: list[Detection], hand_events: list[InteractionEvent], timestamp_s: float) -> list[InteractionEvent]:
        """Return change-only high-level procedure evidence from one frame."""

        events: list[InteractionEvent] = []
        for item in hand_events:
            if item.object_class in self._grasped:
                self._grasped[item.object_class] = item.grasped
        vial, pipette = self._first(detections, "sample_vial"), self._first(detections, "reagent_pipette")
        rack, slot = self._first(detections, "rack_holder"), self._first(detections, "centrifuge_slot")
        lid = self._first(detections, "centrifuge_lid")
        if vial and rack:
            vial_in_rack = self._overlap(vial, rack) > 0.1
            if vial_in_rack:
                self._was_in_rack["sample_vial"] = True
            removed = self._was_in_rack["sample_vial"] and self._grasped["sample_vial"] and not vial_in_rack
            if self._changed("sample_removed", removed):
                events.append(InteractionEvent(timestamp_s, "left", "sample_vial", vial.track_id, "removed_from_rack", True, 0.0))
        if pipette and rack:
            pipette_in_rack = self._overlap(pipette, rack) > 0.1
            if pipette_in_rack:
                self._was_in_rack["reagent_pipette"] = True
            stowed = self._was_in_rack["reagent_pipette"] and pipette_in_rack and not self._grasped["reagent_pipette"]
            if self._changed("pipette_stowed", stowed):
                events.append(InteractionEvent(timestamp_s, "", "reagent_pipette", pipette.track_id, "stowed_in_rack", False, 0.0))
        if vial and pipette:
            injecting = self._overlap(vial, pipette) > 0.05
            key = "pipette_vial_overlap"
            if injecting and key not in self._overlap_started:
                self._overlap_started[key] = timestamp_s
            if not injecting:
                self._overlap_started.pop(key, None)
            confirmed = injecting and timestamp_s - self._overlap_started[key] >= self.injection_dwell_s
            if self._changed("injection", confirmed):
                events.append(InteractionEvent(timestamp_s, "", "reagent_pipette+sample_vial", None, "overlap_2s", False, self._overlap(vial, pipette)))
        vial_loaded = bool(vial and slot and self._inside(vial, slot))
        if vial and self._changed("vial_loaded", vial_loaded):
            events.append(InteractionEvent(timestamp_s, "", "sample_vial", vial.track_id, "inside_centrifuge_slot", False, 1.0))
        lid_closed = bool(lid and slot and self._overlap(lid, slot) > 0.1)
        if lid and self._changed("lid_closed", lid_closed):
            interaction = "closed_over_centrifuge_slot" if vial_loaded else "closed_empty"
            events.append(InteractionEvent(timestamp_s, "", "centrifuge_lid", lid.track_id, interaction, False, self._overlap(lid, slot)))
        return events


class BoxExperimentEvidenceEngine:
    """Infer visible SIH box-procedure evidence from containment and hand state."""

    INNER_BOXES = ("red_box", "second_colored_box")

    def __init__(self) -> None:
        self._was_inside = {item: False for item in self.INNER_BOXES}
        self._was_removed = {item: False for item in self.INNER_BOXES}
        self._grasped = {item: False for item in self.INNER_BOXES}
        self._states: dict[str, bool] = {}

    @staticmethod
    def _inside(item: Detection, container: Detection) -> bool:
        return (
            item.xyxy[0] >= container.xyxy[0]
            and item.xyxy[1] >= container.xyxy[1]
            and item.xyxy[2] <= container.xyxy[2]
            and item.xyxy[3] <= container.xyxy[3]
        )

    @staticmethod
    def _first(detections: list[Detection], cls: str) -> Detection | None:
        return next((item for item in detections if item.cls == cls), None)

    def _changed(self, key: str, active: bool) -> bool:
        previous = self._states.get(key, False)
        self._states[key] = active
        return active and not previous

    def process(
        self,
        detections: list[Detection],
        hand_events: list[InteractionEvent],
        timestamp_s: float,
    ) -> list[InteractionEvent]:
        """Emit change-only removal and return evidence for the box experiment."""

        for event in hand_events:
            if event.object_class in self._grasped:
                self._grasped[event.object_class] = event.grasped
        container = self._first(detections, "outer_container")
        if container is None:
            return []
        events: list[InteractionEvent] = []
        for class_name in self.INNER_BOXES:
            inner_box = self._first(detections, class_name)
            if inner_box is None:
                continue
            contained = self._inside(inner_box, container)
            if contained:
                if self._was_removed[class_name] and not self._grasped[class_name]:
                    key = f"{class_name}:returned"
                    if self._changed(key, True):
                        events.append(
                            InteractionEvent(
                                timestamp_s,
                                "",
                                class_name,
                                inner_box.track_id,
                                "returned_to_outer_container",
                                False,
                                1.0,
                            )
                        )
                self._was_inside[class_name] = True
                continue
            removed = self._was_inside[class_name] and self._grasped[class_name]
            if removed:
                self._was_removed[class_name] = True
                key = f"{class_name}:removed"
                if self._changed(key, True):
                    events.append(
                        InteractionEvent(
                            timestamp_s,
                            "",
                            class_name,
                            inner_box.track_id,
                            "removed_from_outer_container",
                            True,
                            0.0,
                        )
                    )
        return events

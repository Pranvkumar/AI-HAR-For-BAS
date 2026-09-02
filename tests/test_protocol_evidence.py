from types import SimpleNamespace

from aegis.fusion.interaction import EventType, InteractionEvent
from aegis.fusion.protocol_evidence import NestedContainerEvidence


def track(label, box, track_id):
    return SimpleNamespace(label=label, box=box, track_id=track_id, confirmed=True)


def test_nested_container_emits_removal_then_return_once():
    engine = NestedContainerEvidence()
    container = track("outer_container", (0, 0, 100, 100), 1)
    red_inside = track("red_box", (20, 20, 40, 40), 2)
    red_outside = track("red_box", (120, 20, 140, 40), 2)

    assert engine.process([container, red_inside], []) == []
    grasp = InteractionEvent(EventType.GRASP_CONFIRMED, object_label="red_box", object_id=2)
    removed = engine.process([container, red_outside], [grasp])
    assert [(item.action, item.label) for item in removed] == [
        ("retrieve_red_box", "red_box removed from outer container")
    ]
    assert engine.process([container, red_outside], []) == []

    release = InteractionEvent(EventType.RELEASE_CONFIRMED, object_label="red_box", object_id=2)
    returned = engine.process([container, red_inside], [release])
    assert [(item.action, item.label) for item in returned] == [
        ("stow_red_box", "red_box returned to outer container")
    ]
    assert engine.process([container, red_inside], []) == []


def test_nested_container_ignores_unconfirmed_tracks():
    engine = NestedContainerEvidence()
    container = track("outer_container", (0, 0, 100, 100), 1)
    container.confirmed = False
    red = track("red_box", (20, 20, 40, 40), 2)
    assert engine.process([container, red], []) == []
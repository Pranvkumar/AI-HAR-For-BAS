"""Local Streamlit dashboard for protocol status and telemetry."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _tail_jsonl(path: Path, limit: int = 30) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(line) for line in lines if line.strip()]


def main() -> None:
    """Render the standalone local monitoring dashboard."""

    import streamlit as st

    st.set_page_config(page_title="Offline HAR", layout="wide")
    st.title("Astronaut Experiment Activity Monitor")
    log_path = Path(os.environ.get("HAR_TELEMETRY", "logs/latest.jsonl"))
    stream_url = os.environ.get("HAR_STREAM_URL", "http://127.0.0.1:8000/stream")
    events = _tail_jsonl(log_path)
    latest = events[-1] if events else {}
    first, second = st.columns(2)
    first.metric("Current step", latest.get("to_step", latest.get("expected_step", "Waiting")))
    second.metric("Latest event", latest.get("event_type", "No telemetry"))
    st.subheader("Live camera")
    st.image(stream_url)
    st.subheader("Recent protocol events")
    st.dataframe(events, use_container_width=True)


if __name__ == "__main__":
    main()

"""Offline Streamlit dashboard for telemetry and the MJPEG stream."""

import json
import importlib
from pathlib import Path


def main() -> None:
    st = importlib.import_module("streamlit")
    st.set_page_config(page_title="AI HAR Monitor", layout="wide")
    st.title("AI HAR Monitor")
    st.image("http://127.0.0.1:8000/stream", caption="Annotated experiment stream")
    path = Path(st.sidebar.text_input("Telemetry file", "logs/events.jsonl"))
    if path.exists():
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()[-25:]]
        st.dataframe(records, use_container_width=True)


if __name__ == "__main__":
    main()

# Open-source references

The implementation uses these established open-source projects, pinned as
runtime dependencies where appropriate:

- [Ultralytics](https://github.com/ultralytics/ultralytics): YOLO detection, tracking, ONNX/TensorRT export
- [MediaPipe](https://github.com/google-ai-edge/mediapipe): CPU Holistic hand landmarks
- [pyttsx3](https://github.com/nateshmbhat/pyttsx3): offline platform TTS
- [FastAPI](https://github.com/fastapi/fastapi) and Uvicorn: local MJPEG HTTP serving
- [Streamlit](https://github.com/streamlit/streamlit): local monitoring dashboard
- OpenCV: frame handling, annotation, and fallback video writing
- [`transitions`](https://github.com/pytransitions/transitions): protocol state-machine dependency for future model integration

Useful research references from the architecture brief are PREGO, Assembly101,
100DOH, Ego-Exo4D, and MMAction2. They inform evaluation and future temporal
action modeling; they are not runtime dependencies.

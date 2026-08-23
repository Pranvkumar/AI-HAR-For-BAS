# AI HAR Repository Guidelines

This is an offline, edge-deployed human activity recognition system for
astronaut BAS experiments. Keep protocol behavior YAML-driven and keep all
interaction logic relational: hand-to-object distance, overlap, and contact
only. Never infer behavior from absolute position or gravity.

The YOLO layer may use one TensorRT engine on GPU, while MediaPipe and TTS run
on CPU. Vision processing must not synchronously perform file, audio, or
network I/O. Cross-thread events should be typed dataclasses. The package must
remain importable and testable without a GPU or downloaded model weights.

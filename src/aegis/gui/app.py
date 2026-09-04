"""AEGIS Mission Console -- the operator-facing GUI.

Layout: live annotated video on the left, protocol state on the right, controls
along the bottom. The single most important element is the NEXT STEP card: it is
the largest text on screen because it is the one thing an operator needs to read
at a glance while their hands are busy.

The GUI owns no perception state. It polls :class:`HARPipeline` on a timer and
renders whatever it finds. If the pipeline thread dies, the console keeps
running and shows the error rather than freezing -- a console that hangs is worse
than one that reports a fault.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import logging
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import tempfile
import traceback
import webbrowser

import numpy as np

from aegis.config import AppConfig, load_config
from aegis.gui.theme import C, font, mono, pick_fonts
from aegis.pipeline import HARPipeline
from aegis.safety.failure_injection import FaultType

LOGGER = logging.getLogger(__name__)

try:
    from PIL import Image, ImageTk
except Exception:  # pragma: no cover
    Image = ImageTk = None  # type: ignore


REFRESH_MS = 60          # video/UI refresh cadence (~16 fps display)
STATUS_MS = 500          # slower cadence for status text


class StatusLamp(tk.Frame):
    """A small coloured dot with a label -- one subsystem's health."""

    def __init__(self, parent, label: str) -> None:
        super().__init__(parent, bg=C.PANEL)
        self.canvas = tk.Canvas(self, width=12, height=12, bg=C.PANEL, highlightthickness=0)
        self.dot = self.canvas.create_oval(2, 2, 10, 10, fill=C.IDLE, outline="")
        self.canvas.pack(side="left", padx=(0, 6))
        self.text = tk.Label(self, text=label, bg=C.PANEL, fg=C.TEXT_DIM, font=font(9))
        self.text.pack(side="left")

    def set(self, colour: str, label: str | None = None) -> None:
        self.canvas.itemconfig(self.dot, fill=colour)
        if label is not None:
            self.text.config(text=label)


class StepRail(tk.Frame):
    """Vertical list of protocol steps with live state colouring."""

    def __init__(self, parent) -> None:
        super().__init__(parent, bg=C.PANEL)
        self.rows: dict[int, dict] = {}
        self._built_for: list[int] = []

    def build(self, steps: list[dict]) -> None:
        for child in self.winfo_children():
            child.destroy()
        self.rows.clear()
        for step in steps:
            row = tk.Frame(self, bg=C.PANEL)
            row.pack(fill="x", pady=1)

            marker = tk.Canvas(row, width=18, height=22, bg=C.PANEL, highlightthickness=0)
            dot = marker.create_oval(4, 8, 14, 18, fill=C.TEXT_FAINT, outline="")
            marker.pack(side="left")

            num = tk.Label(row, text=f"{step['id']:02d}", bg=C.PANEL, fg=C.TEXT_FAINT,
                           font=mono(9), width=3, anchor="w")
            num.pack(side="left")

            name = tk.Label(row, text=step["name"][:30], bg=C.PANEL, fg=C.TEXT_DIM,
                            font=font(9), anchor="w", justify="left")
            name.pack(side="left", fill="x", expand=True)

            badge = tk.Label(row, text="", bg=C.PANEL, fg=C.TEXT_FAINT, font=mono(8), width=9, anchor="e")
            badge.pack(side="right")

            self.rows[step["id"]] = {"marker": marker, "dot": dot, "num": num, "name": name, "badge": badge}
        self._built_for = [s["id"] for s in steps]

    def update_states(self, steps: list[dict]) -> None:
        if [s["id"] for s in steps] != self._built_for:
            self.build(steps)
        for step in steps:
            row = self.rows.get(step["id"])
            if row is None:
                continue
            state = step["state"]
            colour = C.STATE.get(state, C.TEXT_FAINT)
            row["marker"].itemconfig(row["dot"], fill=colour)
            row["name"].config(fg=C.TEXT if state in ("active", "done") else colour)
            row["num"].config(fg=colour)
            label = {
                "done": "OK",
                "skipped": "SKIP",
                "blocked": "BYPASS",
                "failed": "FAIL",
                "active": "> NOW",
                "pending": "",
            }.get(state, "")
            if step["safety_critical"] and state == "pending":
                label = "CRIT"
            row["badge"].config(text=label, fg=colour)


class EventLog(tk.Frame):
    """Scrolling, colour-coded event feed."""

    def __init__(self, parent) -> None:
        super().__init__(parent, bg=C.PANEL)
        self.text = tk.Text(
            self, bg=C.BG, fg=C.TEXT_DIM, font=mono(8), height=10, wrap="word",
            relief="flat", padx=8, pady=6, insertbackground=C.TEXT, state="disabled",
        )
        scroll = ttk.Scrollbar(self, command=self.text.yview)
        self.text.config(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for name, colour in C.SEVERITY.items():
            self.text.tag_config(name, foreground=colour)
        self.text.tag_config("time", foreground=C.TEXT_FAINT)

    def append(self, severity: str, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.text.config(state="normal")
        self.text.insert("end", f"{stamp}  ", "time")
        self.text.insert("end", f"{message}\n", severity if severity in C.SEVERITY else "info")
        lines = int(self.text.index("end-1c").split(".")[0])
        if lines > 400:
            self.text.delete("1.0", f"{lines - 400}.0")
        self.text.see("end")
        self.text.config(state="disabled")


def button(parent, text: str, command, *, kind: str = "normal", width: int = 14) -> tk.Button:
    colours = {
        "normal": (C.PANEL_HI, C.TEXT),
        "primary": (C.ACCENT, "#101010"),
        "danger": (C.CRIT, "#150808"),
        "ok": (C.OK, "#08150c"),
    }[kind]
    btn = tk.Button(
        parent, text=text, command=command, bg=colours[0], fg=colours[1],
        activebackground=C.LINE_HI, activeforeground=C.TEXT, font=font(9, "bold"),
        relief="flat", bd=0, padx=10, pady=8, width=width, cursor="hand2",
        highlightthickness=1, highlightbackground=C.LINE,
    )
    return btn


class MissionConsole:
    def __init__(self, root: tk.Tk, config: AppConfig) -> None:
        self.root = root
        self.config = config
        self.pipeline: HARPipeline | None = None
        self.photo = None
        self._closing = False
        self._last_status_text = ""
        self._whisper_model = None
        self._details_visible = True
        self._markers_visible = True

        pick_fonts(root)
        root.title("AEGIS  //  AI-HAR Mission Console  --  ISRO BAS Payload")
        root.configure(bg=C.BG)
        root.geometry("1500x980")
        root.minsize(1180, 820)
        if sys.platform.startswith("win"):
            root.state("zoomed")
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._style()
        self._build()
        self._tick_video()
        self._tick_status()

    # ------------------------------------------------------------------ chrome

    def _style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TScrollbar", background=C.PANEL_HI, troughcolor=C.BG,
                        bordercolor=C.BG, arrowcolor=C.TEXT_DIM, relief="flat")

    def _build(self) -> None:
        # ---- header ----------------------------------------------------
        header = tk.Frame(self.root, bg=C.PANEL, height=54)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=C.PANEL)
        brand.pack(side="left", padx=18)
        tk.Label(brand, text="AEGIS", bg=C.PANEL, fg=C.ACCENT, font=font(17, "bold")).pack(side="left")
        tk.Label(brand, text="  AI-HAR  //  ON-BOARD EXPERIMENT VALIDATION",
                 bg=C.PANEL, fg=C.TEXT_DIM, font=font(9)).pack(side="left", padx=(8, 0))

        lamps = tk.Frame(header, bg=C.PANEL)
        lamps.pack(side="right", padx=18)
        self.lamps = {}
        for key, label in (
            ("camera", "CAMERA"), ("model", "MODEL"), ("rack", "RACK"),
            ("voice", "VOICE"), ("rec", "RECORD"), ("stream", "STREAM"),
        ):
            lamp = StatusLamp(lamps, label)
            lamp.pack(side="left", padx=9)
            self.lamps[key] = lamp

        # ---- body ------------------------------------------------------
        body = tk.Frame(self.root, bg=C.BG)
        body.pack(fill="both", expand=True, padx=12, pady=10)

        left = tk.Frame(body, bg=C.BG)
        left.pack(side="left", fill="both", expand=True)

        self.video = tk.Label(left, bg="#101214", bd=0)
        self.video.pack(fill="both", expand=True)

        metrics = tk.Frame(left, bg=C.PANEL, height=34)
        self.metrics = metrics
        metrics.pack(fill="x", pady=(8, 0))
        metrics.pack_propagate(False)
        self.metric_vars = {}
        for key, label in (
            ("fps", "FPS"), ("latency", "LATENCY"), ("tier", "RECOGNITION"),
            ("action", "OBSERVING"), ("mode", "MODE"), ("verdict", "VERDICT"),
            ("object", "OBJECT"), ("session", "SESSION"),
        ):
            cell = tk.Frame(metrics, bg=C.PANEL)
            cell.pack(side="left", padx=16, pady=6)
            tk.Label(cell, text=label, bg=C.PANEL, fg=C.TEXT_FAINT, font=font(7, "bold")).pack(anchor="w")
            var = tk.StringVar(value="-")
            tk.Label(cell, textvariable=var, bg=C.PANEL, fg=C.TEXT, font=mono(9)).pack(anchor="w")
            self.metric_vars[key] = var

        # ---- right column ----------------------------------------------
        right = tk.Frame(body, bg=C.BG, width=440)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        # next step card
        card = tk.Frame(right, bg=C.CARD, highlightthickness=1, highlightbackground=C.LINE)
        card.pack(fill="x")
        tk.Label(card, text="NEXT STEP", bg=C.CARD, fg=C.TEXT_FAINT,
                 font=font(8, "bold")).pack(anchor="w", padx=14, pady=(12, 2))
        self.step_title = tk.Label(card, text="STANDBY", bg=C.CARD, fg=C.ACCENT,
                                   font=font(14, "bold"), anchor="w", justify="left", wraplength=400)
        self.step_title.pack(anchor="w", padx=14)
        self.step_instruction = tk.Label(
            card, text="Press START SESSION to begin.", bg=C.CARD, fg=C.TEXT,
            font=font(11), anchor="w", justify="left", wraplength=400,
        )
        self.step_instruction.pack(anchor="w", padx=14, pady=(6, 12))

        self.progress_canvas = tk.Canvas(card, height=6, bg=C.PANEL_HI, highlightthickness=0)
        self.progress_canvas.pack(fill="x", padx=14, pady=(0, 6))
        self.progress_bar = self.progress_canvas.create_rectangle(0, 0, 0, 6, fill=C.OK, outline="")
        self.progress_label = tk.Label(card, text="0 / 0 steps verified", bg=C.CARD,
                                       fg=C.TEXT_DIM, font=mono(8))
        self.progress_label.pack(anchor="w", padx=14, pady=(0, 12))

        # alert banner
        self.alert = tk.Label(right, text="", bg=C.BG, fg=C.CRIT, font=font(10, "bold"),
                              wraplength=420, justify="left", anchor="w")
        self.alert.pack(fill="x", pady=(8, 0))

        scene = tk.Frame(right, bg=C.PANEL, highlightthickness=1, highlightbackground=C.LINE)
        scene.pack(fill="x", pady=(8, 0))
        tk.Label(scene, text="LIVE SCENE", bg=C.PANEL, fg=C.TEXT_FAINT,
                 font=font(8, "bold")).pack(anchor="w", padx=12, pady=(8, 1))
        self.scene_objects = tk.Label(
            scene, text="Detector offline", bg=C.PANEL, fg=C.TEXT_DIM,
            font=mono(9), anchor="w", justify="left", wraplength=410,
        )
        self.scene_objects.pack(fill="x", padx=12, pady=(0, 8))

        # protocol rail
        rail_wrap = tk.Frame(right, bg=C.PANEL, highlightthickness=1, highlightbackground=C.LINE)
        rail_wrap.pack(fill="both", expand=True, pady=10)
        tk.Label(rail_wrap, text="PROTOCOL", bg=C.PANEL, fg=C.TEXT_FAINT,
                 font=font(8, "bold")).pack(anchor="w", padx=12, pady=(10, 6))
        self.rail = StepRail(rail_wrap)
        self.rail.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # event log
        log_wrap = tk.Frame(right, bg=C.PANEL, highlightthickness=1, highlightbackground=C.LINE)
        log_wrap.pack(fill="both", expand=True)
        tk.Label(log_wrap, text="EVENT LOG", bg=C.PANEL, fg=C.TEXT_FAINT,
                 font=font(8, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        self.log = EventLog(log_wrap)
        self.log.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # ---- controls ---------------------------------------------------
        controls = tk.Frame(self.root, bg=C.PANEL, height=104,
                    highlightthickness=1, highlightbackground=C.LINE)
        controls.pack(fill="x", side="top", before=body)
        controls.pack_propagate(True)

        command_row = tk.Frame(controls, bg=C.PANEL)
        command_row.pack(fill="x", padx=12, pady=(6, 2))
        tk.Label(command_row, text="VOICE COMMAND", bg=C.PANEL, fg=C.TEXT_FAINT,
                 font=font(8, "bold")).pack(side="left", padx=(4, 8))
        self.command_entry = tk.Entry(
            command_row, bg=C.BG, fg=C.TEXT, insertbackground=C.TEXT,
            relief="flat", width=28, font=font(9),
        )
        self.command_entry.pack(side="left", ipady=7)
        self.command_entry.bind("<Return>", lambda _event: self.on_voice_command())
        self.btn_listen = button(command_row, "LISTEN", self.on_listen, width=9)
        self.btn_listen.pack(side="left", padx=(8, 4))
        self.btn_markers = button(command_row, "MARKERS ON", self.on_markers, width=10)
        self.btn_markers.pack(side="left", padx=4)
        self.btn_details = button(command_row, "DETAILS ON", self.on_details, width=10)
        self.btn_details.pack(side="left", padx=4)
        self.command_hint = tk.Label(command_row, text="say: status / confirm / skip",
                                     bg=C.PANEL, fg=C.TEXT_FAINT, font=font(8), anchor="w")
        self.command_hint.pack(side="left", padx=4)

        row = tk.Frame(controls, bg=C.PANEL)
        row.pack(fill="x", padx=12, pady=(2, 8))

        self.btn_start = button(row, "START SESSION", self.on_start, kind="primary", width=16)
        self.btn_start.pack(side="left", padx=4)
        self.btn_stop = button(row, "STOP", self.on_stop, kind="danger", width=10)
        self.btn_stop.pack(side="left", padx=4)
        self.btn_ack = button(row, "ACKNOWLEDGE", self.on_ack, width=14)
        self.btn_ack.pack(side="left", padx=4)
        self.btn_confirm = button(row, "CONFIRM STEP", self.on_confirm, kind="ok", width=14)
        self.btn_confirm.pack(side="left", padx=4)
        self.btn_skip = button(row, "SKIP STEP", self.on_skip, width=12)
        self.btn_skip.pack(side="left", padx=4)
        self.btn_rec = button(row, "RECORD", self.on_record, width=9)
        self.btn_rec.pack(side="left", padx=4)
        self.btn_stream = button(row, "STREAM", self.on_stream, width=9)
        self.btn_stream.pack(side="left", padx=4)
        self.btn_voice = button(row, "VOICE", self.on_voice, width=8)
        self.btn_voice.pack(side="left", padx=4)
        self.btn_more = button(row, "MORE", self.on_more, width=8)
        self.btn_more.pack(side="left", padx=4)

        self.btn_logs = button(row, "OPEN LOGS", self.on_open_logs, width=11)
        self.btn_why = button(row, "WHY?", self.on_why, width=8)
        self.btn_faults = button(row, "INJECT FAULT", self.on_faults, kind="danger", width=13)

        self._set_running(False)
        self._render_protocol_preview()

    def _render_protocol_preview(self) -> None:
        """Show the protocol before a session starts, so the console isn't blank."""
        try:
            from aegis.protocol.spec import load_protocol

            protocol = load_protocol(self.config.protocol_file)
            steps = [
                {"id": s.id, "name": s.name, "state": "pending", "safety_critical": s.safety_critical}
                for s in protocol.steps
            ]
            self.rail.update_states(steps)
            self.progress_label.config(text=f"0 / {len(steps)} steps verified")
            self.log.append("info", f"Protocol loaded: {protocol.experiment} ({len(steps)} steps)")
        except Exception as exc:
            self.log.append("critical", f"Could not load protocol: {exc}")

    # ------------------------------------------------------------------ actions

    def _set_running(self, running: bool) -> None:
        state = "normal" if running else "disabled"
        for btn in (self.btn_stop, self.btn_ack, self.btn_confirm, self.btn_skip,
                    self.btn_rec, self.btn_stream, self.btn_voice,
                    self.btn_why, self.btn_faults, self.btn_listen,
                    self.btn_markers, self.btn_details, self.btn_more):
            btn.config(state=state)
        self.btn_start.config(state="disabled" if running else "normal")

    def on_start(self) -> None:
        if self.pipeline is not None and self.pipeline.running:
            return
        try:
            self.pipeline = HARPipeline(self.config, on_event=self._on_event)
            status = self.pipeline.start()
        except Exception as exc:
            LOGGER.exception("failed to start pipeline")
            messagebox.showerror("AEGIS", f"Could not start the session:\n\n{exc}")
            self.log.append("critical", f"Start failed: {exc}")
            self.pipeline = None
            return

        self._set_running(True)
        self.log.append("info", f"Session {status.session_id} started")
        self.log.append("info", f"Perception: {status.perception}")
        self.log.append("info", f"Recognition: {status.tier} ({status.tier_detail})")
        if not status.camera_ok:
            self.log.append("critical", status.camera_error or "camera unavailable")
        if not status.zones_calibrated:
            self.log.append("warning", "Zones are auto-generated. Run CALIBRATE_ZONES.bat for real accuracy.")

    def on_stop(self) -> None:
        if self.pipeline is None:
            return
        self.log.append("info", "Stopping session...")
        pipeline, self.pipeline = self.pipeline, None
        self._set_running(False)

        def worker():
            try:
                report = pipeline.stop()
                self.root.after(0, lambda: self._after_stop(report))
            except Exception as exc:
                self.root.after(0, lambda: self.log.append("critical", f"Stop error: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def _after_stop(self, report) -> None:
        if report is not None:
            self.log.append("success", f"Session report: {report}")
            if messagebox.askyesno("AEGIS", f"Session complete.\n\nReport written to:\n{report}\n\nOpen it now?"):
                self._open_path(report)
        self.step_title.config(text="STANDBY", fg=C.ACCENT)
        self.step_instruction.config(text="Press START SESSION to begin.")
        self.alert.config(text="")

    def on_ack(self) -> None:
        if self.pipeline:
            self.pipeline.acknowledge()

    def on_confirm(self) -> None:
        if self.pipeline:
            self.pipeline.confirm_step()

    def on_skip(self) -> None:
        if self.pipeline:
            self.pipeline.manual_skip()

    def on_record(self) -> None:
        if self.pipeline:
            active = self.pipeline.toggle_recording()
            self.log.append("info", f"Recording {'started' if active else 'stopped'}")

    def on_stream(self) -> None:
        if not self.pipeline:
            return
        active = self.pipeline.toggle_streaming()
        status = self.pipeline.streamer.status()
        if active:
            self.log.append("success", f"Streaming live at {status.url}")
            if messagebox.askyesno("AEGIS", f"Stream is live at:\n\n{status.url}\n\nOpen it in a browser?"):
                try:
                    webbrowser.open(status.url)
                except Exception:
                    pass
        else:
            self.log.append("info", f"Streaming stopped {status.error}".strip())

    def on_voice(self) -> None:
        if self.pipeline:
            enabled = self.pipeline.toggle_voice()
            self.log.append("info", f"Voice alerts {'enabled' if enabled else 'muted'}")

    def on_markers(self) -> None:
        self._markers_visible = not self._markers_visible
        if self.pipeline is not None:
            self.pipeline.set_markers_visible(self._markers_visible)
        self.btn_markers.config(text="MARKERS ON" if self._markers_visible else "MARKERS OFF")
        self.log.append("info", f"Rack markers {'shown' if self._markers_visible else 'hidden'}")

    def on_details(self) -> None:
        self._details_visible = not self._details_visible
        if self._details_visible:
            self.metrics.pack(fill="x", pady=(8, 0))
            self.btn_details.config(text="DETAILS ON")
        else:
            self.metrics.pack_forget()
            self.btn_details.config(text="DETAILS OFF")

    def on_more(self) -> None:
        for btn in (self.btn_logs, self.btn_why, self.btn_faults):
            if btn.winfo_ismapped():
                btn.pack_forget()
                self.btn_more.config(text="MORE")
            else:
                btn.pack(side="left", padx=4)
                self.btn_more.config(text="LESS")

    def _speak(self, text: str) -> None:
        if self.pipeline is not None and self.pipeline.voice.enabled:
            self.pipeline.voice.say(text, force=True)

    def on_voice_command(self) -> None:
        """Run a short, safety-scoped command without blocking the UI."""
        command = self.command_entry.get().strip().lower()
        if not command:
            return
        self.command_entry.delete(0, "end")
        if self.pipeline is None:
            response = "Start a session before issuing mission commands."
        elif any(word in command for word in ("start", "begin", "resume")):
            response = "The session is already running."
        elif any(word in command for word in ("stop", "end", "finish")):
            response = "Stopping the session."
            self.on_stop()
        elif "confirm" in command or "complete" in command:
            response = "Confirming the current step."
            self.on_confirm()
        elif "skip" in command:
            response = "Skipping the current step."
            self.on_skip()
        elif "acknowledge" in command or command == "ack":
            response = "Alert acknowledged."
            self.on_ack()
        elif "record" in command:
            self.on_record()
            response = "Recording state changed."
        elif "stream" in command:
            self.on_stream()
            response = "Streaming state changed."
        elif "mute" in command or "voice off" in command:
            if self.pipeline.voice.enabled:
                self.on_voice()
            response = "Voice alerts muted."
        elif "voice" in command or "unmute" in command:
            if not self.pipeline.voice.enabled:
                self.on_voice()
            response = "Voice alerts enabled."
        elif "status" in command or "how are" in command:
            status = self.pipeline.snapshot()
            response = f"System {status.mode}. Camera {'ready' if status.camera_ok else 'not ready'}."
        else:
            response = "Command not recognized. Try status, confirm, skip, record, or stop."
        self.log.append("info", f"Command: {command} -> {response}")
        self._speak(response)

    def on_listen(self) -> None:
        if self.pipeline is None:
            self.log.append("warning", "Start a session before listening for commands.")
            return
        self.btn_listen.config(state="disabled", text="LISTENING")

        def worker():
            try:
                import speech_recognition as sr

                recognizer = sr.Recognizer()
                with sr.Microphone() as source:
                    self.root.after(0, lambda: self.command_hint.config(text="Listening..."))
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                model = self._get_whisper_model()
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as recording:
                    recording.write(audio.get_wav_data())
                    recording_path = recording.name
                try:
                    segments, _ = model.transcribe(
                        recording_path, beam_size=5, vad_filter=True, language="en"
                    )
                    text = " ".join(segment.text.strip() for segment in segments).strip()
                finally:
                    Path(recording_path).unlink(missing_ok=True)
                if not text:
                    raise RuntimeError("no speech was recognized")
                self.root.after(0, lambda: (self.command_entry.insert(0, text), self.on_voice_command()))
            except ImportError:
                self.root.after(0, lambda: self.log.append(
                    "warning", "Voice input unavailable; install SpeechRecognition, PyAudio, and faster-whisper."
                ))
            except Exception as exc:
                self.root.after(0, lambda: self.log.append("warning", f"Microphone command failed: {exc}"))
            finally:
                self.root.after(0, lambda: self._finish_listen())

        threading.Thread(target=worker, name="voice-input", daemon=True).start()

    def _get_whisper_model(self):
        if self._whisper_model is not None:
            return self._whisper_model
        model_dir = self.config.voice_model_directory
        if not (model_dir / "model.bin").exists():
            raise FileNotFoundError(
                f"Whisper model not found: {model_dir / 'model.bin'}. "
                "Place the complete voice model in models/voice."
            )
        from faster_whisper import WhisperModel

        self.command_hint.config(text="Loading voice model...")
        self._whisper_model = WhisperModel(
            str(model_dir), device=self.config.voice_model_device, compute_type="int8"
        )
        return self._whisper_model

    def _finish_listen(self) -> None:
        self.btn_listen.config(state="normal" if self.pipeline is not None else "disabled", text="LISTEN")
        self.command_hint.config(text="say: status / confirm / skip")

    def on_why(self) -> None:
        """Show the evidence behind the most recent decision."""
        if self.pipeline is None:
            return
        text = self.pipeline.last_explanation()
        win = tk.Toplevel(self.root)
        win.title("AEGIS - Decision Evidence")
        win.configure(bg=C.BG)
        win.geometry("760x420")
        tk.Label(win, text="WHY THIS DECISION", bg=C.BG, fg=C.ACCENT,
                 font=font(11, "bold")).pack(anchor="w", padx=16, pady=(14, 6))
        box = tk.Text(win, bg=C.PANEL, fg=C.TEXT, font=mono(10), relief="flat",
                      wrap="word", padx=14, pady=12)
        box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        box.insert("1.0", text)
        box.config(state="disabled")

    def on_faults(self) -> None:
        """Failure-injection console.

        Each fault is listed with the response the system is supposed to
        produce, so a reviewer can check the claim against the live GUI rather
        than taking it on trust.
        """
        if self.pipeline is None:
            return
        win = tk.Toplevel(self.root)
        win.title("AEGIS - Failure Injection")
        win.configure(bg=C.BG)
        win.geometry("820x520")

        tk.Label(win, text="CONTROLLED FAILURE INJECTION", bg=C.BG, fg=C.CRIT,
                 font=font(12, "bold")).pack(anchor="w", padx=18, pady=(16, 2))
        tk.Label(win, text="Inject a fault and watch the status lamps and mode respond.",
                 bg=C.BG, fg=C.TEXT_DIM, font=font(9)).pack(anchor="w", padx=18, pady=(0, 12))

        holder = tk.Frame(win, bg=C.BG)
        holder.pack(fill="both", expand=True, padx=18)
        buttons: dict = {}

        def refresh():
            if self.pipeline is None:
                return
            active = set(self.pipeline.injector.active_faults())
            for fault, btn in buttons.items():
                on = fault in active
                btn.config(text=("ACTIVE  " if on else "inject  ") + fault.label,
                           bg=C.CRIT if on else C.PANEL_HI,
                           fg="#150808" if on else C.TEXT)

        def make(fault):
            def handler():
                self.pipeline.inject_fault(fault)
                self.log.append("warning", f"Fault toggled: {fault.label}")
                refresh()
            return handler

        for fault in FaultType:
            if fault is FaultType.NONE:
                continue
            rowf = tk.Frame(holder, bg=C.BG)
            rowf.pack(fill="x", pady=2)
            b = tk.Button(rowf, text=fault.label, command=make(fault),
                          bg=C.PANEL_HI, fg=C.TEXT, font=font(9, "bold"),
                          relief="flat", bd=0, width=30, anchor="w", padx=10, pady=6,
                          cursor="hand2", highlightthickness=1, highlightbackground=C.LINE)
            b.pack(side="left")
            buttons[fault] = b
            tk.Label(rowf, text="-> " + fault.expected_response, bg=C.BG,
                     fg=C.TEXT_DIM, font=font(8)).pack(side="left", padx=10)

        footer = tk.Frame(win, bg=C.BG)
        footer.pack(fill="x", padx=18, pady=14)
        tk.Button(footer, text="CLEAR ALL FAULTS",
                  command=lambda: (self.pipeline.clear_faults(),
                                   self.log.append("info", "All faults cleared"), refresh()),
                  bg=C.OK, fg="#08150c", font=font(9, "bold"), relief="flat", bd=0,
                  padx=14, pady=8, cursor="hand2").pack(side="left")
        refresh()

    def on_open_logs(self) -> None:
        self._open_path(self.config.log_directory)

    def _open_path(self, path: Path) -> None:
        try:
            import os
            import subprocess

            path = Path(path)
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            self.log.append("warning", f"Could not open {path}: {exc}")

    def _on_event(self, event) -> None:
        """Called from the pipeline thread -- marshal onto the Tk thread."""
        try:
            self.root.after(0, lambda: self._render_event(event))
        except RuntimeError:
            pass

    def _render_event(self, event) -> None:
        severity = getattr(getattr(event, "severity", None), "value", "info")
        self.log.append(severity, event.message)
        if severity in ("warning", "critical"):
            self.alert.config(text=("!! " if severity == "critical" else "! ") + event.message,
                              fg=C.SEVERITY[severity])
        elif event.kind in ("step_completed", "block_cleared", "session_completed"):
            self.alert.config(text="")

    # ------------------------------------------------------------------- ticks

    def _tick_video(self) -> None:
        if self._closing:
            return
        try:
            if self.pipeline is not None and Image is not None:
                frame = self.pipeline.latest_frame()
                self._show(frame)
        except Exception as exc:  # pragma: no cover
            LOGGER.debug("video tick failed: %s", exc)
        self.root.after(REFRESH_MS, self._tick_video)

    def _show(self, frame_bgr: np.ndarray) -> None:
        widget_w = max(320, self.video.winfo_width())
        widget_h = max(240, self.video.winfo_height())
        h, w = frame_bgr.shape[:2]
        scale = min(widget_w / w, widget_h / h)
        if scale <= 0:
            return
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        rgb = frame_bgr[:, :, ::-1]
        image = Image.fromarray(rgb).resize(new_size, Image.BILINEAR)
        self.photo = ImageTk.PhotoImage(image)
        self.video.config(image=self.photo)

    def _tick_status(self) -> None:
        if self._closing:
            return
        try:
            self._refresh_status()
        except Exception as exc:  # pragma: no cover
            LOGGER.debug("status tick failed: %s", exc)
        self.root.after(STATUS_MS, self._tick_status)

    def _refresh_status(self) -> None:
        if self.pipeline is None:
            for lamp in self.lamps.values():
                lamp.set(C.IDLE)
            return

        status = self.pipeline.snapshot()
        proto = self.pipeline.protocol_snapshot()

        self.lamps["camera"].set(C.OK if status.camera_ok else C.CRIT)
        self.lamps["model"].set(C.OK if "Tier 1" in status.tier else C.WARN)
        self.lamps["rack"].set(
            C.OK if status.rack_source in ("aruco",) else
            C.WARN if status.rack_source in ("aruco_hold", "static") else C.IDLE
        )
        self.lamps["voice"].set(C.OK if status.voice_ok else C.IDLE)
        self.lamps["rec"].set(C.CRIT if status.recording else C.IDLE)
        self.lamps["stream"].set(C.OK if status.streaming else C.IDLE)

        self.metric_vars["fps"].set(f"{status.fps:5.1f}")
        self.metric_vars["latency"].set(f"{status.latency_ms:5.1f} ms")
        self.metric_vars["tier"].set(status.tier.replace("Tier ", "T"))
        self.metric_vars["action"].set(f"{status.last_action} {status.last_confidence:.2f}")
        self.metric_vars["session"].set(status.session_id or "-")

        # Round-2 state: mode, camera health, evidence verdict
        mode = status.mode.upper()
        if status.injected_faults:
            mode += f"  [{len(status.injected_faults)} FAULT]"
        self.metric_vars["mode"].set(mode)
        self.metric_vars["verdict"].set(
            f"{status.verdict or '-'}" + (f"  {status.verdict_reason[:30]}" if status.verdict_reason else "")
        )

        # Object identity. A mismatch is the most decisive thing this system can
        # report, so it gets the operator's attention rather than sitting quietly
        # inside the evidence list.
        if not status.detector_ok:
            self.metric_vars["object"].set("OFF")
            self.scene_objects.config(text="Detector offline", fg=C.TEXT_DIM)
        elif status.object_match == "mismatch":
            self.metric_vars["object"].set("WRONG OBJECT")
            self.scene_objects.config(
                text="WRONG OBJECT\n" + (status.object_summary or "identity mismatch"),
                fg=C.CRIT,
            )
        elif status.object_match == "match":
            self.metric_vars["object"].set("OK")
            self.scene_objects.config(
                text="  ".join(status.detected_labels) or "Detector warming up",
                fg=C.OK,
            )
        elif status.object_match == "absent":
            self.metric_vars["object"].set("not seen")
            self.scene_objects.config(
                text="  ".join(status.detected_labels) or "No confirmed objects near hand",
                fg=C.WARN,
            )
        else:
            self.metric_vars["object"].set(
                f"{len(status.detected_labels)} tracked" if status.detected_labels else "-"
            )
            self.scene_objects.config(
                text="  ".join(status.detected_labels) or "Detector warming up",
                fg=C.TEXT_DIM,
            )

        self.lamps["camera"].set(
            C.OK if status.camera_health == "nominal"
            else C.WARN if status.camera_health == "degraded" else C.CRIT
        )
        self.lamps["rack"].set(
            C.OK if status.rack_health == "green"
            else C.WARN if status.rack_health == "yellow" else C.CRIT
        )
        if not status.workers_ok:
            self.lamps["model"].set(C.CRIT)

        if status.mode == "safe":
            self.step_title.config(text="VALIDATION SUSPENDED", fg=C.CRIT)
            self.step_instruction.config(
                text=(status.camera_reasons[0] if status.camera_reasons else status.rack_summary)
                     or "Subsystem impaired - observing only, protocol will not advance."
            )
            return

        blocked = proto["blocked"]
        title = proto["current_step_name"] or "PROTOCOL COMPLETE"
        step_id = proto["current_step_id"]
        if blocked:
            self.step_title.config(text=f"HALTED - RECOVER STEP {step_id}", fg=C.CRIT)
        elif proto["completed"]:
            self.step_title.config(text="EXPERIMENT COMPLETE", fg=C.OK)
        else:
            self.step_title.config(text=f"STEP {step_id} - {title}", fg=C.ACCENT)
        self.step_instruction.config(text=proto["next_instruction"])

        done, total = proto["done"], max(1, proto["total"])
        width = self.progress_canvas.winfo_width()
        self.progress_canvas.coords(self.progress_bar, 0, 0, width * done / total, 6)
        self.progress_canvas.itemconfig(self.progress_bar, fill=C.CRIT if blocked else C.OK)
        self.progress_label.config(text=f"{done} / {proto['total']} steps verified")

        self.rail.update_states(proto["steps"])

        self.btn_rec.config(text="STOP REC" if status.recording else "RECORD")
        self.btn_stream.config(text="UNSTREAM" if status.streaming else "STREAM")

        if status.errors:
            newest = status.errors[-1]
            if newest != self._last_status_text:
                self._last_status_text = newest
                self.log.append("warning", newest)

    # -------------------------------------------------------------------- exit

    def on_close(self) -> None:
        if self.pipeline is not None and self.pipeline.running:
            if not messagebox.askokcancel("AEGIS", "A session is running. Stop it and exit?"):
                return
        self._closing = True
        if self.pipeline is not None:
            try:
                self.pipeline.stop()
            except Exception:
                pass
        self.root.destroy()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AEGIS AI-HAR Mission Console")
    parser.add_argument("--config", default=None, help="path to app.yaml")
    parser.add_argument("--source", default=None, help="override video source (index, file, or URL)")
    parser.add_argument("--autostart", action="store_true", help="begin the session immediately")
    parser.add_argument("--no-voice", action="store_true")
    parser.add_argument("--stream", action="store_true", help="enable streaming at launch")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    if Image is None:
        print("ERROR: Pillow is required for the GUI. Run INSTALL.bat.", file=sys.stderr)
        return 2

    try:
        config = load_config(args.config)
    except Exception as exc:
        print(f"ERROR: could not load configuration: {exc}", file=sys.stderr)
        return 2

    if args.source is not None:
        config.video_source = args.source
    if args.no_voice:
        config.voice_enabled = False
    if args.stream:
        config.stream_enabled = True

    root = tk.Tk()
    console = MissionConsole(root, config)
    if args.autostart:
        root.after(400, console.on_start)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        console.on_close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        input("\nPress Enter to close...")
        raise

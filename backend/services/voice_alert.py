"""
Windows Native Background TTS Voice Alert Worker for AEGIS AI-HAR.
Uses pyttsx3 or Windows SAPI.SpVoice in a background thread to speak voice guidance
without blocking the FastAPI event loop.
"""
import queue
import threading
from loguru import logger


class BackgroundTTSWorker(threading.Thread):
    """Threaded TTS worker that speaks audio cues without blocking inference."""

    def __init__(self, enabled: bool = True):
        super().__init__(daemon=True)
        self._queue: queue.Queue = queue.Queue()
        self._enabled = enabled
        self._running = False

    def run(self):
        self._running = True
        engine = None

        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            logger.info("TTS: pyttsx3 initialized successfully")
        except Exception as e:
            logger.debug(f"TTS: pyttsx3 not available ({e}), will use PowerShell SAPI fallback")

        while self._running:
            try:
                text = self._queue.get(timeout=0.5)
                if text is None:
                    break

                if not self._enabled:
                    continue

                if engine is not None:
                    try:
                        engine.say(text)
                        engine.runAndWait()
                        continue
                    except Exception:
                        pass

                # Windows native PowerShell SAPI fallback
                try:
                    import subprocess
                    clean_text = text.replace("'", "").replace('"', "")
                    cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{clean_text}')"
                    subprocess.run(["powershell", "-NoProfile", "-Command", cmd], timeout=5, creationflags=0x08000000)
                except Exception as exc:
                    logger.debug(f"TTS speak error: {exc}")

            except queue.Empty:
                continue
            except Exception as e:
                logger.debug(f"TTS worker loop error: {e}")

    def speak(self, text: str):
        if self._running and text:
            self._queue.put(text)

    def stop(self):
        self._running = False
        self._queue.put(None)


tts_worker = BackgroundTTSWorker()
try:
    tts_worker.start()
except Exception:
    pass

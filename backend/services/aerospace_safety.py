"""
Aerospace Safety & Autonomous Telemetry Extensions for AEGIS AI-HAR.
Includes:
  - Thermal Governor (Dynamic CPU throttle on fanless/laptop hardware)
  - Hardware Watchdog (Auto-recovers from USB camera bus deadlocks)
  - Glare Detection (V-channel saturation monitoring for optical glare)
  - Immobility Detection (Flags potential crew emergency if hand variance drops)
  - Unsecured Drift Detection (Kalman velocity analysis of unheld objects)
  - Kinetic Jerk & Slosh Guard (Physics-based fluid spill mitigation)
  - SWaP-C Eco-Governor (Autonomous spacecraft power optimization)
  - Cognitive Stall Detector (Kinematic hesitation tracking)
  - FOD Vector Projection (Active collision avoidance trajectory projection)
"""
import time
import math
import cv2
import numpy as np
from collections import deque, OrderedDict
from typing import List, Dict, Tuple, Optional, Any
from loguru import logger


# ─── THERMAL GOVERNOR ────────────────────────────────────────────────────────
class ThermalGovernor:
    """Monitors CPU load on host hardware and dynamically adjusts pose frequency."""
    
    def __init__(self):
        self.thermal_level = 0  # 0=COOL, 1=WARM, 2=HOT
        self.last_check_time = 0.0
        self.cpu_percent = 25.0
        self.pose_interval = 2

    def check(self) -> int:
        now = time.time()
        if now - self.last_check_time < 3.0:
            return self.thermal_level
        self.last_check_time = now

        try:
            import psutil
            self.cpu_percent = psutil.cpu_percent(interval=0.05)
            if self.cpu_percent > 90.0:
                self.thermal_level = 2
                self.pose_interval = 6
            elif self.cpu_percent > 75.0:
                self.thermal_level = 1
                self.pose_interval = 4
            else:
                self.thermal_level = 0
                self.pose_interval = 2
        except Exception:
            self.thermal_level = 0
            self.pose_interval = 2

        return self.thermal_level

    def get_state(self) -> Dict[str, Any]:
        level_str = "COOL" if self.thermal_level == 0 else ("WARM" if self.thermal_level == 1 else "HOT")
        return {
            "thermal_level": self.thermal_level,
            "thermal_status": level_str,
            "cpu_percent": round(self.cpu_percent, 1),
            "pose_interval": self.pose_interval,
            "throttle_active": self.thermal_level > 0,
        }


# ─── HARDWARE WATCHDOG ───────────────────────────────────────────────────────
class HardwareWatchdog:
    """Supervises frame arrival from camera hardware and auto-recovers on bus deadlocks."""

    def __init__(self, timeout_s: float = 2.5):
        self.timeout_s = timeout_s
        self.last_frame_time = time.time()
        self.recovery_count = 0
        self.last_recovery_time = 0.0

    def feed(self):
        self.last_frame_time = time.time()

    def check_health(self) -> bool:
        """Returns True if camera is healthy, False if bus deadlock detected."""
        if time.time() - self.last_frame_time > self.timeout_s:
            self.recovery_count += 1
            self.last_recovery_time = time.time()
            self.last_frame_time = time.time()  # reset to avoid repeat triggers
            logger.warning(f"Hardware Watchdog: Camera bus deadlock detected! Recovery #{self.recovery_count}")
            return False
        return True

    def get_state(self) -> Dict[str, Any]:
        return {
            "healthy": (time.time() - self.last_frame_time) <= self.timeout_s,
            "recovery_count": self.recovery_count,
            "last_recovery_time": self.last_recovery_time,
        }


# ─── GLARE DETECTOR ──────────────────────────────────────────────────────────
class GlareDetector:
    """V-channel saturation monitoring in HSV space for optical camera blinding."""

    def __init__(self, pixel_threshold: int = 245, area_threshold: float = 0.30):
        self.pixel_threshold = pixel_threshold
        self.area_threshold = area_threshold
        self.saturation_ratio = 0.0
        self.is_blinded = False

    def evaluate(self, frame: np.ndarray) -> Tuple[bool, float]:
        if frame is None or frame.size == 0:
            return False, 0.0
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            v_channel = hsv[:, :, 2]
            saturated = int(np.count_nonzero(v_channel > self.pixel_threshold))
            self.saturation_ratio = round(float(saturated) / float(v_channel.size), 3)
            self.is_blinded = self.saturation_ratio > self.area_threshold
        except Exception:
            self.saturation_ratio = 0.0
            self.is_blinded = False
        return self.is_blinded, self.saturation_ratio


# ─── IMMOBILITY & CREW TRACKER ────────────────────────────────────────────────
class ImmobilityDetector:
    """Flags crew emergency if hand or body motion variance drops to zero in hazard zones."""

    def __init__(self, history_len: int = 45, variance_threshold: float = 4.0, emergency_seconds: float = 4.0):
        self.history = deque(maxlen=history_len)
        self.variance_threshold = variance_threshold
        self.emergency_seconds = emergency_seconds
        self.immobile_start: Optional[float] = None
        self.is_immobile = False
        self.current_variance = 50.0

    def update(self, point: Optional[Tuple[float, float]]) -> bool:
        now = time.time()
        if point is None:
            self.history.clear()
            self.immobile_start = None
            self.is_immobile = False
            return False

        self.history.append(point)
        if len(self.history) < 15:
            self.is_immobile = False
            return False

        xs = [p[0] for p in self.history]
        ys = [p[1] for p in self.history]
        var_x = float(np.var(xs))
        var_y = float(np.var(ys))
        self.current_variance = round(math.sqrt(var_x + var_y), 2)

        if self.current_variance < self.variance_threshold:
            if self.immobile_start is None:
                self.immobile_start = now
            elif (now - self.immobile_start) >= self.emergency_seconds:
                self.is_immobile = True
        else:
            self.immobile_start = None
            self.is_immobile = False

        return self.is_immobile


# ─── KALMAN TRACKER ──────────────────────────────────────────────────────────
class BBoxKalmanFilter:
    """Kalman filter for single bounding box state [cx, cy, w, h, vx, vy, vw, vh]."""

    def __init__(self):
        self.kf = cv2.KalmanFilter(8, 4)
        self.kf.transitionMatrix = np.array([
            [1, 0, 0, 0, 1, 0, 0, 0],
            [0, 1, 0, 0, 0, 1, 0, 0],
            [0, 0, 1, 0, 0, 0, 1, 0],
            [0, 0, 0, 1, 0, 0, 0, 1],
            [0, 0, 0, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 0, 1],
        ], np.float32)

        self.kf.measurementMatrix = np.array([
            [1, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0, 0],
        ], np.float32)

        self.kf.processNoiseCov = np.eye(8, dtype=np.float32) * 1e-2
        self.kf.measurementNoiseCov = np.eye(4, dtype=np.float32) * 1e-1
        self.kf.errorCovPost = np.eye(8, dtype=np.float32) * 1.0
        self.is_initialized = False

    def predict(self) -> List[float]:
        pred = self.kf.predict()
        cx, cy, w, h = pred[0, 0], pred[1, 0], pred[2, 0], pred[3, 0]
        return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]

    def update(self, bbox: List[float]):
        x1, y1, x2, y2 = bbox
        cx, cy, w, h = (x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1), (y2 - y1)
        meas = np.array([[cx], [cy], [w], [h]], np.float32)
        if not self.is_initialized:
            self.kf.statePost = np.array([[cx], [cy], [w], [h], [0], [0], [0], [0]], np.float32)
            self.is_initialized = True
        else:
            self.kf.correct(meas)


class MultiObjectKalmanTracker:
    """Tracks multiple objects and provides relative velocity vectors for drift detection."""

    def __init__(self):
        self.filters: Dict[str, BBoxKalmanFilter] = {}

    def update(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        updated = []
        for i, det in enumerate(detections):
            name = det.get("class_name", f"obj_{i}")
            bbox = det.get("bbox", [0, 0, 0, 0])
            if name not in self.filters:
                self.filters[name] = BBoxKalmanFilter()
            kf = self.filters[name]
            kf.predict()
            kf.update(bbox)
            
            state = kf.kf.statePost
            vx = float(state[4, 0])
            vy = float(state[5, 0])
            v_mag = math.sqrt(vx**2 + vy**2)
            
            d_copy = dict(det)
            d_copy["vx"] = round(vx, 2)
            d_copy["vy"] = round(vy, 2)
            d_copy["velocity_mag"] = round(v_mag, 2)
            updated.append(d_copy)

        return updated


# ─── UNSECURED DRIFT & FOD PROJECTOR ─────────────────────────────────────────
class UnsecuredDriftDetector:
    """Detects unheld microgravity items drifting and projects collision trajectories."""

    def __init__(self, drift_velocity_threshold: float = 12.0, projection_time_s: float = 2.5):
        self.threshold = drift_velocity_threshold
        self.projection_time = projection_time_s
        self.active_drifts: Dict[str, int] = {}
        self.fod_active = False
        self.fod_object = ""
        self.fod_eta = 0.0
        self.predicted_impact: Optional[Tuple[int, int]] = None

    def evaluate(self, detections: List[Dict[str, Any]], hand_present: bool) -> Dict[str, Any]:
        self.fod_active = False
        self.fod_object = ""
        self.fod_eta = 0.0
        self.predicted_impact = None

        for det in detections:
            cname = det.get("class_name", "")
            if cname in ["hand", "astronaut_hand"]:
                continue

            v_mag = det.get("velocity_mag", 0.0)
            if v_mag > self.threshold and not hand_present:
                count = self.active_drifts.get(cname, 0) + 1
                self.active_drifts[cname] = count
                if count >= 2:
                    self.fod_active = True
                    self.fod_object = cname
                    self.fod_eta = self.projection_time
                    bbox = det.get("bbox", [0.5, 0.5, 0.6, 0.6])
                    cx = (bbox[0] + bbox[2]) / 2.0 * 640
                    cy = (bbox[1] + bbox[3]) / 2.0 * 480
                    vx = det.get("vx", 0.0) * 30
                    vy = det.get("vy", 0.0) * 30
                    px = int(max(0, min(640, cx + vx * self.projection_time)))
                    py = int(max(0, min(480, cy + vy * self.projection_time)))
                    self.predicted_impact = (px, py)
                    break
            else:
                self.active_drifts[cname] = 0

        return {
            "fod_active": self.fod_active,
            "fod_object": self.fod_object,
            "fod_eta": self.fod_eta,
            "predicted_impact": self.predicted_impact,
        }


# ─── KINETIC JERK & SLOSH GUARD ──────────────────────────────────────────────
class SloshGuard:
    """Computes discrete jerk j = d^2v/dt^2 to prevent fluid spills in microgravity."""

    def __init__(self, jerk_threshold: float = 800.0):
        self.jerk_threshold = jerk_threshold
        self.prev_vx = 0.0
        self.prev_vy = 0.0
        self.prev_ax = 0.0
        self.prev_ay = 0.0
        self.last_time = time.time()
        self.jerk_magnitude = 0.0
        self.alert_active = False
        self.alert_text = ""
        self.alert_cooldown = 0.0

    def update(self, vx: float, vy: float) -> Tuple[float, bool]:
        now = time.time()
        dt = now - self.last_time
        if dt > 0.005:
            ax = (vx - self.prev_vx) / dt
            ay = (vy - self.prev_vy) / dt
            jx = (ax - self.prev_ax) / dt
            jy = (ay - self.prev_ay) / dt
            self.jerk_magnitude = round(math.sqrt(jx**2 + jy**2), 1)

            if self.jerk_magnitude > self.jerk_threshold and now > self.alert_cooldown:
                self.alert_active = True
                self.alert_text = "CAUTION: EXCESSIVE JERK — MICROGRAVITY SLOSH HAZARD"
                self.alert_cooldown = now + 2.5
            elif now > self.alert_cooldown:
                self.alert_active = False
                self.alert_text = ""

            self.prev_vx, self.prev_vy = vx, vy
            self.prev_ax, self.prev_ay = ax, ay
            self.last_time = now

        return self.jerk_magnitude, self.alert_active


# ─── SWaP-C ECO-GOVERNOR ─────────────────────────────────────────────────────
class EcoGovernor:
    """Frame differencing power optimizer; throttles static scenes to save ~83% compute."""

    def __init__(self, static_threshold: float = 2.2, standby_delay_s: float = 4.0):
        self.static_threshold = static_threshold
        self.standby_delay_s = standby_delay_s
        self.prev_gray: Optional[np.ndarray] = None
        self.standby_timer = 0.0
        self.is_standby = False
        self.mode = "ACTIVE"
        self.target_fps = 30.0
        self.frames_skipped = 0
        self.skip_counter = 0

    def process(self, frame: np.ndarray, motion_override: bool = False) -> bool:
        """Returns True if the frame should be processed by heavy inference, False if skipped."""
        if frame is None:
            return True

        small = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2GRAY)
        if self.prev_gray is not None and not motion_override:
            diff = cv2.absdiff(small, self.prev_gray)
            mean_diff = float(np.mean(diff))

            if mean_diff < self.static_threshold:
                self.standby_timer += 0.033
                if self.standby_timer > self.standby_delay_s:
                    self.is_standby = True
                    self.mode = "STANDBY"
                    self.target_fps = 5.0
            else:
                self.standby_timer = 0.0
                self.is_standby = False
                self.mode = "ACTIVE"
                self.target_fps = 30.0
        else:
            self.standby_timer = 0.0
            self.is_standby = False
            self.mode = "ACTIVE"
            self.target_fps = 30.0

        self.prev_gray = small

        self.skip_counter += 1
        if self.is_standby and (self.skip_counter % 6 != 0):
            self.frames_skipped += 1
            return False

        return True


# ─── COGNITIVE STALL DETECTOR ────────────────────────────────────────────────
class CognitiveStallDetector:
    """Detects kinematic hesitation near target experiment tools and prompts operator."""

    def __init__(self, hover_radius_px: float = 160.0, vel_threshold: float = 18.0, dwell_s: float = 3.5):
        self.hover_radius_px = hover_radius_px
        self.vel_threshold = vel_threshold
        self.dwell_s = dwell_s
        self.hover_start: Optional[float] = None
        self.is_hesitating = False
        self.dwell_ms = 0.0
        self.hesitation_count = 0
        self.prompted = False

    def update(self, hand_pos: Optional[Tuple[float, float]], target_pos: Optional[Tuple[float, float]], hand_vel: float) -> Tuple[bool, float]:
        if hand_pos is None or target_pos is None:
            self.hover_start = None
            self.is_hesitating = False
            self.dwell_ms = 0.0
            self.prompted = False
            return False, 0.0

        dist = math.sqrt((hand_pos[0] - target_pos[0])**2 + (hand_pos[1] - target_pos[1])**2)
        if dist < self.hover_radius_px and hand_vel < self.vel_threshold:
            if self.hover_start is None:
                self.hover_start = time.time()
            elapsed = time.time() - self.hover_start
            self.dwell_ms = round(elapsed * 1000, 0)
            if elapsed >= self.dwell_s:
                self.is_hesitating = True
                if not self.prompted:
                    self.hesitation_count += 1
                    self.prompted = True
            else:
                self.is_hesitating = False
        else:
            self.hover_start = None
            self.is_hesitating = False
            self.dwell_ms = 0.0
            self.prompted = False

        return self.is_hesitating, self.dwell_ms


# Global instances
thermal_governor = ThermalGovernor()
hardware_watchdog = HardwareWatchdog()
glare_detector = GlareDetector()
immobility_detector = ImmobilityDetector()
kalman_tracker = MultiObjectKalmanTracker()
drift_detector = UnsecuredDriftDetector()
slosh_guard = SloshGuard()
eco_governor = EcoGovernor()
cognitive_stall_detector = CognitiveStallDetector()

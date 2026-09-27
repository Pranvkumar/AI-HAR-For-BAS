/**
 * Shapes returned by the FastAPI backend.
 * These mirror backend/schemas/dto.py.
 */

export type ValidationStatus = 'CORRECT' | 'WARNING' | 'SEQUENCE_VIOLATION' | 'DUPLICATE';
export type AlertSeverityApi = 'INFO' | 'WARNING' | 'CRITICAL';
export type SessionStatusApi = 'IN_PROGRESS' | 'COMPLETED' | 'ABORTED';
export type ScenarioName = 'nominal' | 'low_confidence' | 'violation';

export interface ApiExperimentStep {
  id: number;
  step_number: number;
  title: string | null;
  expected_activity: string;
  description: string | null;
  safety_critical: boolean;
}

export interface ApiExperiment {
  id: number;
  title: string;
  code: string;
  description: string | null;
  category: string;
  environment: string;
  estimated_duration: string;
  total_steps: number;
  created_at: string;
  steps: ApiExperimentStep[];
  status: string;
  current_step: number;
  progress: number;
  latest_session_id: number | null;
  completed_activities: string[];
}

export interface ApiSystemStatus {
  ai_engine_online: boolean;
  camera_stream_active: boolean;
  database_connected: boolean;
  demo_mode: boolean;
  confidence_threshold: number;
  model_loaded: boolean;
}

export interface ApiTimelineEntry {
  time: string;
  event: string;
}

export interface ApiActivity {
  id: number;
  session_id: number;
  detected_activity: string;
  confidence: number;
  timestamp: string;
}

export interface ApiDashboard {
  active_sessions: number;
  total_experiments: number;
  unacknowledged_alerts: number;
  total_activities_today: number;
  active_experiment_code: string | null;
  active_experiment_title: string | null;
  active_experiment_progress: number;
  current_activity: string | null;
  last_activity: ApiActivity | null;
  recent_timeline: ApiTimelineEntry[];
  system_status: ApiSystemStatus;
}

export interface ApiBoundingBox {
  bbox: [number, number, number, number];
  class_name: string;
  confidence: number;
}

export interface ApiPose {
  keypoints: [number, number, number][];
}

export interface ApiCurrentActivity {
  detected_activity: string;
  confidence: number;
  expected_activity: string | null;
  step_number: number;
  total_steps: number;
  validation_status: ValidationStatus;
  timestamp: string;
  session_id: number | null;
  progress: number;
  guidance: string | null;
  bounding_boxes: ApiBoundingBox[];
  pose_keypoints: ApiPose[];
}

/** Live frame pushed over the monitoring WebSocket. */
export interface ApiMonitoringFrame {
  timestamp: string;
  session_id: number | null;
  experiment_id: number | null;
  detected_activity: string;
  confidence: number;
  expected_step: string | null;
  step_number: number;
  total_steps: number;
  status: ValidationStatus;
  bounding_boxes: ApiBoundingBox[];
  pose_keypoints: ApiPose[];
  alert: { id: number; severity: AlertSeverityApi; message: string } | null;
  fsm_state: string | null;
  progress: number;
  guidance: string | null;
  completed_activities: string[];
  // Aerospace Extensions Telemetry
  merkle_hash?: string | null;
  merkle_chain_length?: number;
  slosh_jerk?: number;
  slosh_alert?: boolean;
  eco_mode?: string;
  eco_fps?: number;
  eco_frames_saved?: number;
  thermal_status?: string;
  cpu_percent?: number;
  is_blinded?: boolean;
  glare_saturation?: number;
  is_immobile?: boolean;
  fod_active?: boolean;
  fod_object?: string;
  fod_eta?: number;
  predicted_impact?: [number, number] | null;
  hesitation_active?: boolean;
  hesitation_dwell_ms?: number;
  ccsds_last_hex?: string;
  ccsds_total_packets?: number;
  hand_pos?: [number, number] | null;
}

export interface ApiAlert {
  id: number;
  session_id: number | null;
  severity: AlertSeverityApi;
  message: string;
  timestamp: string;
  acknowledged: boolean;
}

export interface ApiAlertSummary {
  total: number;
  active: number;
  warnings: number;
  critical: number;
}

export interface ApiActivityLog {
  id: number;
  session_id: number;
  experiment_code: string;
  detected_activity: string;
  step_number: number | null;
  validation_status: ValidationStatus;
  confidence: number;
  timestamp: string;
}

export interface ApiSession {
  id: number;
  experiment_id: number;
  astronaut_id: number | null;
  status: SessionStatusApi;
  started_at: string | null;
  ended_at: string | null;
}

export interface ApiScenario {
  name: ScenarioName;
  description: string;
}

export interface ApiStartResponse {
  session_id: number;
  experiment_id: number;
  status: string;
  scenario: string;
  message: string;
}

export interface ApiStopResponse {
  session_id: number;
  status: string;
  activities_recorded: number;
  duration_seconds: number;
}

export interface ApiChatResponse {
  reply: string;
  context: Record<string, unknown> | null;
  timestamp: string;
}

export interface ApiEnvironmentMetric {
  label: string;
  value: string;
  detail: string;
}

export interface ApiEnvironmentTrend {
  label: string;
  value: number;
  unit: string;
  data: number[];
}

export interface ApiEnvironmentGauge {
  label: string;
  value: number;
  max: number;
  unit: string;
  status: string;
}

export interface ApiEnvironment {
  metrics: ApiEnvironmentMetric[];
  trends: ApiEnvironmentTrend[];
  gauges: ApiEnvironmentGauge[];
  environmental_stability: number;
  motion_disturbance: string;
  experiment_environment: string;
  simulated: boolean;
}

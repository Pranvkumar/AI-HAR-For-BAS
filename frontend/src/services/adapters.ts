/**
 * Adapters from backend API shapes to the view models the UI components
 * already consume. Keeping the mapping here means no presentational component
 * needs to know the API exists.
 */
import type {
  ActivityEvent,
  AlertEvent,
  AlertSeverity,
  Experiment,
  ExperimentStatus,
  ExperimentStep,
  StepStatus,
} from '@/types';
import type {
  ApiActivityLog,
  ApiAlert,
  ApiExperiment,
  ValidationStatus,
} from '@/types/api';

/** ACTIVITY_LABEL -> "Activity Label" */
export function humanizeActivity(activity: string): string {
  return activity
    .split('_')
    .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
    .join(' ');
}

export function formatTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? '--:--:--'
    : date.toLocaleTimeString('en-GB', { hour12: false });
}

const EXPERIMENT_STATUSES: ExperimentStatus[] = ['Active', 'Completed', 'Scheduled', 'Paused'];

function toExperimentStatus(status: string): ExperimentStatus {
  return EXPERIMENT_STATUSES.includes(status as ExperimentStatus)
    ? (status as ExperimentStatus)
    : 'Scheduled';
}

/**
 * Step status is derived from position relative to the current step, which is
 * what the backend's FSM progress actually tells us.
 */
function toStepStatus(stepNumber: number, currentStep: number, isComplete: boolean): StepStatus {
  if (isComplete || stepNumber < currentStep) return 'Completed';
  if (stepNumber === currentStep) return 'In Progress';
  return 'Pending';
}

export function toExperiment(api: ApiExperiment): Experiment {
  const isComplete = api.status === 'Completed';
  const currentStep = api.status === 'Scheduled' ? 0 : api.current_step;

  const steps: ExperimentStep[] = api.steps.map((step) => ({
    id: step.step_number,
    title: step.title ?? humanizeActivity(step.expected_activity),
    description: step.description ?? '',
    status: toStepStatus(step.step_number, currentStep, isComplete),
  }));

  return {
    id: api.code,
    name: api.title,
    category: api.category,
    environment: api.environment,
    progress: Math.round(api.progress),
    status: toExperimentStatus(api.status),
    duration: api.estimated_duration,
    currentStep,
    totalSteps: api.total_steps,
    steps,
  };
}

/** Validation status -> the table's Completed / In Progress / Pending vocabulary. */
const LOG_STATUS_LABEL: Record<ValidationStatus, string> = {
  CORRECT: 'Completed',
  DUPLICATE: 'In Progress',
  WARNING: 'Warning',
  SEQUENCE_VIOLATION: 'Violation',
};

export function toActivityEvent(log: ApiActivityLog): ActivityEvent {
  return {
    id: String(log.id),
    time: formatTime(log.timestamp),
    experiment: log.experiment_code,
    activity: humanizeActivity(log.detected_activity),
    step: log.step_number ? `Step ${log.step_number}` : 'N/A',
    status: LOG_STATUS_LABEL[log.validation_status] ?? log.validation_status,
    confidence: Math.round(log.confidence * 100),
  };
}

const ALERT_SEVERITY: Record<string, AlertSeverity> = {
  CRITICAL: 'critical',
  WARNING: 'warning',
  INFO: 'info',
};

export function toAlertEvent(alert: ApiAlert, experimentCode?: string): AlertEvent {
  return {
    id: String(alert.id),
    severity: ALERT_SEVERITY[alert.severity] ?? 'system',
    title: alert.message,
    experiment: experimentCode,
    time: formatTime(alert.timestamp),
    action: alert.acknowledged ? undefined : 'Acknowledge to clear this alert.',
  };
}

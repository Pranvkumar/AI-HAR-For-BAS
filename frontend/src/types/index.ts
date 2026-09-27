export type ExperimentStatus = 'Active' | 'Completed' | 'Scheduled' | 'Paused';
export type StepStatus = 'Completed' | 'In Progress' | 'Pending';

export interface ExperimentStep {
  id: number;
  title: string;
  description: string;
  status: StepStatus;
}

export interface Experiment {
  id: string;
  name: string;
  category: string;
  environment: string;
  progress: number;
  status: ExperimentStatus;
  duration: string;
  currentStep: number;
  totalSteps: number;
  steps: ExperimentStep[];
}

export interface ActivityEvent {
  id: string;
  time: string;
  experiment: string;
  activity: string;
  step: string;
  status: string;
  confidence: number;
}

export type AlertSeverity = 'critical' | 'warning' | 'info' | 'system';

export interface AlertEvent {
  id: string;
  severity: AlertSeverity;
  title: string;
  experiment?: string;
  time: string;
  action?: string;
}

export interface MicrogravityMetric {
  label: string;
  value: string;
  status: 'nominal' | 'stable' | 'active' | 'good';
  detail: string;
}

export interface SystemStatusItem {
  label: string;
  status: string;
  active: boolean;
}

export interface TrendData {
  label: string;
  value: number;
  unit: string;
  data: number[];
}

export interface AssistantQA {
  question: string;
  answer: string;
}

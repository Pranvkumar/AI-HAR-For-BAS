/**
 * Backend HTTP client.
 *
 * Requests go through Vite's dev proxy (see vite.config.ts) so the browser
 * talks to the same origin and no CORS preflight is needed in development.
 */
import type {
  ApiActivityLog,
  ApiAlert,
  ApiAlertSummary,
  ApiChatResponse,
  ApiCurrentActivity,
  ApiDashboard,
  ApiEnvironment,
  ApiExperiment,
  ApiScenario,
  ApiSession,
  ApiStartResponse,
  ApiStopResponse,
  ApiSystemStatus,
  ScenarioName,
} from '@/types/api';

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1';

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

  if (!response.ok) {
    // FastAPI returns {detail: ...}; fall back to the status text otherwise.
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      // Non-JSON error body — keep the status text.
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  // Dashboard / system
  getDashboard: () => request<ApiDashboard>('/dashboard'),
  getSystemStatus: () => request<ApiSystemStatus>('/system/status'),
  getEnvironment: () => request<ApiEnvironment>('/system/environment'),

  // Experiments
  listExperiments: () => request<ApiExperiment[]>('/experiments'),
  getExperiment: (identifier: string) =>
    request<ApiExperiment>(`/experiments/${encodeURIComponent(identifier)}`),

  // Monitoring
  getCurrentActivity: () => request<ApiCurrentActivity>('/monitoring/activities/current'),
  listSessions: () => request<ApiSession[]>('/monitoring/sessions'),
  listScenarios: () =>
    request<{ scenarios: ApiScenario[] }>('/monitoring/scenarios').then((r) => r.scenarios),
  startMonitoring: (experimentId: number, scenario: ScenarioName = 'nominal') =>
    request<ApiStartResponse>('/monitoring/start', {
      method: 'POST',
      body: JSON.stringify({ experiment_id: experimentId, scenario }),
    }),
  stopMonitoring: (sessionId: number) =>
    request<ApiStopResponse>(`/monitoring/stop/${sessionId}`, { method: 'POST' }),

  // Alerts
  listAlerts: (limit = 100) => request<ApiAlert[]>(`/alerts?limit=${limit}`),
  getAlertSummary: () => request<ApiAlertSummary>('/alerts/summary'),
  acknowledgeAlert: (alertId: number) =>
    request<ApiAlert>(`/alerts/${alertId}/acknowledge`, { method: 'POST' }),

  // Logs
  listLogs: (limit = 200) => request<ApiActivityLog[]>(`/logs?limit=${limit}`),

  // Assistant
  chat: (message: string, sessionId?: number | null) =>
    request<ApiChatResponse>('/assistant/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId ?? null }),
    }),
  getSuggestions: () =>
    request<{ suggestions: string[] }>('/assistant/suggestions').then((r) => r.suggestions),
  getGuidance: (sessionId?: number | null) =>
    request<{ session_id: number | null; guidance: string }>(
      `/assistant/guidance${sessionId ? `?session_id=${sessionId}` : ''}`,
    ),
};

/** WebSocket URL for the live monitoring stream, derived from the page origin. */
export function monitoringSocketUrl(): string {
  const explicit = import.meta.env.VITE_WS_URL;
  if (explicit) return explicit;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/monitoring`;
}

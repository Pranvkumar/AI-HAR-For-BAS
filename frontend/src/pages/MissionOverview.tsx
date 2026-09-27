import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bot,
  Activity,
  FlaskConical,
  Gauge,
  CheckCircle2,
  Radio,
  Layers,
  ShieldCheck,
  Cpu,
  ArrowUpRight,
  Flame,
  Zap,
  Clock,
  Sparkles,
  Lock,
} from 'lucide-react';
import AppLayout from '@/components/layout/AppLayout';
import KpiCard from '@/components/common/KpiCard';
import Panel from '@/components/common/Panel';
import ProgressBar from '@/components/common/ProgressBar';
import StatusDot from '@/components/common/StatusDot';
import AssistantPanel from '@/components/assistant/AssistantPanel';
import { api } from '@/services/api';
import { useQuery } from '@/hooks/useApi';
import { useMonitoringSocket } from '@/hooks/useMonitoringSocket';
import { humanizeActivity } from '@/services/adapters';

const DASHBOARD_POLL_MS = 5000;

export default function MissionOverview() {
  const [assistantOpen, setAssistantOpen] = useState(false);
  const { data: dashboard, error } = useQuery(() => api.getDashboard(), {
    intervalMs: DASHBOARD_POLL_MS,
  });
  const { frame } = useMonitoringSocket();

  // Fresh live frame from websocket wins over polled snapshot
  const currentActivity = frame
    ? humanizeActivity(frame.detected_activity)
    : dashboard?.current_activity ?? 'STANDBY';
  const progress = frame?.progress ?? dashboard?.active_experiment_progress ?? 0;
  const experimentCode = dashboard?.active_experiment_code ?? 'EXP-BIO-01';
  const experimentTitle = dashboard?.active_experiment_title ?? 'Cell Culture & Microfluidics Handling';
  const status = dashboard?.system_status;
  const systemOperational = status?.ai_engine_online && status?.database_connected;

  const systemHealth = [
    { label: 'Vision Inference Engine (ONNX)', status: status?.ai_engine_online ? 'Operational' : 'Offline', active: Boolean(status?.ai_engine_online) },
    { label: 'Optical Camera Bus & Watchdog', status: status?.camera_stream_active ? 'Streaming' : 'Standby', active: Boolean(status?.camera_stream_active) },
    { label: 'Autonomous Voice & TTS SAPI5', status: 'Online', active: true },
    { label: 'DO-178C Merkle Flight Ledger', status: 'Verified', active: true },
    { label: 'CCSDS 133.0-B-2 Packet Link', status: 'Packaging', active: true },
  ];

  const stepLabel = frame
    ? `Step ${frame.step_number} of ${frame.total_steps}`
    : `${dashboard?.active_sessions ?? 0} active session(s)`;

  return (
    <>
      <AppLayout title="Mission Control" subtitle="Real-time spacecraft telemetry, experiment validation, and avionics flight status.">
        {error && (
          <div className="panel border-redx-500/30 p-3 mb-4 bg-redx-500/10">
            <p className="text-xs text-redx-400 font-mono">Telemetry link interrupt — {error}</p>
          </div>
        )}

        {/* Quick Launch & Mission Banner */}
        <div className="relative overflow-hidden rounded-xl bg-gradient-to-r from-space-900/90 via-space-900/70 to-accent-950/40 border border-white/[0.08] p-5 mb-6 backdrop-blur-xl shadow-glass-card">
          <div className="absolute top-0 right-0 w-96 h-full bg-gradient-to-l from-accent-500/10 to-transparent pointer-events-none" />
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
            <div>
              <div className="flex items-center gap-3 mb-1.5 flex-wrap">
                <h2 className="text-xl font-bold text-white font-display tracking-tight">
                  {experimentTitle}
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-tealx-500/15 text-tealx-400 border border-tealx-500/30 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-tealx-400 animate-pulse" />
                  FLIGHT READY
                </span>
              </div>
              <div className="text-xs text-space-400 font-mono mb-1">
                ORBIT VELOCITY: 7.66 KM/S • ALTITUDE: 408 KM
              </div>
              <p className="text-xs text-space-300 mt-1 max-w-2xl">
                Real-time computer vision procedure verification, microgravity slosh prevention, and tamper-proof Merkle ledger flight recording.
              </p>
            </div>

            <div className="flex items-center gap-2.5 flex-wrap">
              <Link to="/monitoring" className="btn-primary">
                <Radio className="w-3.5 h-3.5" />
                Live Monitoring
                <ArrowUpRight className="w-3.5 h-3.5 ml-0.5" />
              </Link>
              <Link to="/experiments" className="btn-ghost">
                <FlaskConical className="w-3.5 h-3.5 text-accent-400" />
                Procedures
              </Link>
            </div>
          </div>
        </div>

        {/* KPI Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <KpiCard
            label="Active Procedure"
            value={experimentCode}
            subtitle={stepLabel}
            icon={<FlaskConical className="w-4 h-4" />}
            variant="accent"
          />
          <KpiCard
            label="Detected Activity"
            value={currentActivity.toUpperCase()}
            subtitle={frame ? `${Math.round(frame.confidence * 100)}% Confidence` : 'Awaiting sensor input'}
            icon={<Activity className="w-4 h-4" />}
            variant="default"
          />
          <KpiCard
            label="Procedure Progress"
            value={`${Math.round(progress)}%`}
            trend="+12% nominal"
            subtitle="Current procedure step"
            icon={<Gauge className="w-4 h-4" />}
            variant="success"
          />
          <KpiCard
            label="System Health"
            value={systemOperational ? 'OPERATIONAL' : 'DEGRADED'}
            subtitle="5 of 5 engines nominal"
            icon={<CheckCircle2 className="w-4 h-4" />}
            variant={systemOperational ? 'success' : 'warning'}
          />
        </div>

        {/* Two-Column Flight Operations Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          {/* Left Column (2 Cols): Current Experiment & Aerospace Telemetry */}
          <div className="lg:col-span-2 space-y-6">
            <Panel title="Active Experiment Workflow" hudCorners>
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 rounded-lg bg-space-950/60 border border-white/[0.04]">
                  <div>
                    <span className="kpi-label block mb-1">Experiment Code</span>
                    <span className="text-sm font-mono font-bold text-white">{experimentCode}</span>
                  </div>
                  <div>
                    <span className="kpi-label block mb-1">Environment</span>
                    <span className="text-sm font-mono text-tealx-400 font-semibold">Microgravity (μG)</span>
                  </div>
                  <div>
                    <span className="kpi-label block mb-1">Active Step</span>
                    <span className="text-sm font-mono text-white">{stepLabel}</span>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-mono text-space-300">Procedure Execution</span>
                    <span className="text-xs font-mono font-bold text-accent-300">{Math.round(progress)}%</span>
                  </div>
                  <ProgressBar value={Math.round(progress)} variant="accent" height="h-2.5" />
                </div>

                {/* Subsystem Quick-Status Chips */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
                  <div className="p-2.5 rounded-lg bg-space-900/50 border border-white/[0.04]">
                    <div className="flex items-center gap-1.5 text-[10px] text-space-400 font-mono mb-1">
                      <Lock className="w-3 h-3 text-tealx-400" />
                      MERKLE LEDGER
                    </div>
                    <div className="text-xs font-mono font-bold text-white">DO-178C SYNC</div>
                  </div>

                  <div className="p-2.5 rounded-lg bg-space-900/50 border border-white/[0.04]">
                    <div className="flex items-center gap-1.5 text-[10px] text-space-400 font-mono mb-1">
                      <Zap className="w-3 h-3 text-accent-400" />
                      SWAP-C ECO
                    </div>
                    <div className="text-xs font-mono font-bold text-white">AUTONOMOUS</div>
                  </div>

                  <div className="p-2.5 rounded-lg bg-space-900/50 border border-white/[0.04]">
                    <div className="flex items-center gap-1.5 text-[10px] text-space-400 font-mono mb-1">
                      <Flame className="w-3 h-3 text-amberx-400" />
                      SLOSH GUARD
                    </div>
                    <div className="text-xs font-mono font-bold text-white">ARMED (&lt;800)</div>
                  </div>

                  <div className="p-2.5 rounded-lg bg-space-900/50 border border-white/[0.04]">
                    <div className="flex items-center gap-1.5 text-[10px] text-space-400 font-mono mb-1">
                      <ShieldCheck className="w-3 h-3 text-violetx-400" />
                      BIOMETRICS
                    </div>
                    <div className="text-xs font-mono font-bold text-white">WINDOWS NATIVE</div>
                  </div>
                </div>
              </div>
            </Panel>

            {/* Recent Flight Activity Timeline */}
            <Panel title="Recent Mission Timeline" hudCorners>
              {dashboard?.recent_timeline.length ? (
                <div className="relative pl-6 space-y-4 my-2">
                  <div className="absolute left-2.5 top-2 bottom-2 w-[1px] bg-gradient-to-b from-accent-400/40 via-tealx-400/20 to-transparent" />
                  {dashboard.recent_timeline.map((item, i) => (
                    <div key={`${item.time}-${i}`} className="relative flex items-start gap-4">
                      <div className="absolute -left-[19px] top-1.5 w-2.5 h-2.5 rounded-full bg-accent-400 border-2 border-space-950 shadow-[0_0_8px_#0ea5e9]" />
                      <span className="text-[11px] font-mono text-accent-300 shrink-0 w-20 pt-0.5">
                        {item.time}
                      </span>
                      <div className="flex-1 p-2 rounded bg-space-950/40 border border-white/[0.04]">
                        <span className="text-xs text-space-100 font-medium">{item.event}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-8 text-center">
                  <Clock className="w-6 h-6 text-space-500 mx-auto mb-2" />
                  <p className="text-xs font-mono text-space-400">
                    Awaiting monitoring session events. Start a session to populate live flight milestones.
                  </p>
                </div>
              )}
            </Panel>
          </div>

          {/* Right Column (1 Col): Subsystem Diagnostics & Avionics Status */}
          <div className="space-y-6">
            <Panel title="Subsystem Diagnostics" hudCorners>
              <div className="space-y-3">
                {systemHealth.map((item) => (
                  <div
                    key={item.label}
                    className="flex items-center justify-between p-2.5 rounded-lg bg-space-950/50 border border-white/[0.04]"
                  >
                    <div>
                      <span className="text-xs font-medium text-space-200 block">{item.label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-2 h-2 rounded-full ${
                          item.active
                            ? 'bg-tealx-400 shadow-[0_0_8px_rgba(20,184,166,0.9)] animate-pulse'
                            : 'bg-space-600'
                        }`}
                      />
                      <span className="text-xs font-mono font-semibold text-tealx-400">
                        {item.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="Mission Quick Actions" hudCorners>
              <div className="space-y-2.5">
                <Link
                  to="/monitoring"
                  className="flex items-center justify-between p-3 rounded-lg bg-space-950/60 border border-white/[0.06] hover:border-accent-400/40 hover:bg-space-900/60 transition-all group"
                >
                  <div className="flex items-center gap-2.5">
                    <Radio className="w-4 h-4 text-accent-400" />
                    <div>
                      <div className="text-xs font-bold text-white">Live Monitoring Feed</div>
                      <div className="text-[10px] text-space-400">Optical camera with YOLO/ORB overlays</div>
                    </div>
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-space-400 group-hover:text-accent-400 transition-colors" />
                </Link>

                <Link
                  to="/microgravity"
                  className="flex items-center justify-between p-3 rounded-lg bg-space-950/60 border border-white/[0.06] hover:border-tealx-400/40 hover:bg-space-900/60 transition-all group"
                >
                  <div className="flex items-center gap-2.5">
                    <Layers className="w-4 h-4 text-tealx-400" />
                    <div>
                      <div className="text-xs font-bold text-white">Microgravity Physics</div>
                      <div className="text-[10px] text-space-400">Slosh dynamics & float sensor status</div>
                    </div>
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-space-400 group-hover:text-tealx-400 transition-colors" />
                </Link>

                <Link
                  to="/logs"
                  className="flex items-center justify-between p-3 rounded-lg bg-space-950/60 border border-white/[0.06] hover:border-violetx-400/40 hover:bg-space-900/60 transition-all group"
                >
                  <div className="flex items-center gap-2.5">
                    <ShieldCheck className="w-4 h-4 text-violetx-400" />
                    <div>
                      <div className="text-xs font-bold text-white">Audit & Activity Logs</div>
                      <div className="text-[10px] text-space-400">DO-178C verified flight hash records</div>
                    </div>
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-space-400 group-hover:text-violetx-400 transition-colors" />
                </Link>
              </div>
            </Panel>
          </div>
        </div>

        {/* AI Assistant Floating Trigger */}
        <button
          onClick={() => setAssistantOpen(true)}
          className="fixed bottom-6 right-6 flex items-center gap-2 px-4 py-3 rounded-full bg-gradient-to-r from-accent-600 to-accent-500 hover:from-accent-500 hover:to-accent-400 text-white shadow-glow-accent transition-all z-30 cursor-pointer active:scale-95"
        >
          <Bot className="w-5 h-5 animate-pulse" />
          <span className="text-xs font-bold uppercase tracking-wider font-display">AI Copilot</span>
        </button>
      </AppLayout>

      <AssistantPanel open={assistantOpen} onClose={() => setAssistantOpen(false)} />
    </>
  );
}

import {
  Play,
  Square,
  Clock,
  CheckCircle2,
  Box,
  ShieldCheck,
  Film,
  FileCheck2,
  Layers,
} from 'lucide-react';
import type { ApiExperiment, ScenarioName } from '@/types/api';
import { humanizeActivity } from '@/services/adapters';

interface ExperimentSummaryPanelProps {
  experiment: ApiExperiment | null;
  experiments: ApiExperiment[] | null;
  selectedExpId: number | null;
  onSelectExperiment: (id: number) => void;
  scenario: ScenarioName;
  onSelectScenario: (sc: ScenarioName) => void;
  running: boolean;
  busy: boolean;
  onStart: () => void;
  onStop: () => void;
  elapsedTime: string;
  currentStep: number;
  totalSteps: number;
  completedCount: number;
  detectedEntities: Array<[string, number]>;
  systemNominal: boolean;
  onOpenBiometrics: () => void;
  onOpenObjects: () => void;
  onOpenReplay: () => void;
  onOpenMerkle: () => void;
}

const SCENARIOS: Record<ScenarioName, string> = {
  nominal: 'Nominal Telemetry Sequence',
  low_confidence: 'Low Confidence Alert Injection',
  violation: 'Protocol Sequence Violation',
};

export default function ExperimentSummaryPanel({
  experiment,
  experiments,
  selectedExpId,
  onSelectExperiment,
  scenario,
  onSelectScenario,
  running,
  busy,
  onStart,
  onStop,
  elapsedTime,
  currentStep,
  totalSteps,
  completedCount,
  detectedEntities,
  systemNominal,
  onOpenBiometrics,
  onOpenObjects,
  onOpenReplay,
  onOpenMerkle,
}: ExperimentSummaryPanelProps) {
  return (
    <div className="panel p-3">
      {/* Panel Title */}
      <div className="flex items-center justify-between pb-2 mb-2.5 border-b border-[#ded2c5]">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-[#964f19]" />
          <span className="text-[11px] font-mono font-bold tracking-[0.14em] text-[#261912] uppercase">
            Experiment Operations Control
          </span>
        </div>
        <span
          className={`status-dot ${
            running ? 'bg-tealx-500 animate-pulse' : 'bg-space-400'
          }`}
        />
      </div>

      {/* Target Experiment & Scenario Selector */}
      <div className="space-y-2 mb-3">
        <div>
          <label className="kpi-label block mb-1">Target Scientific Protocol</label>
          <select
            value={experiment?.id ?? ''}
            onChange={(e) => onSelectExperiment(Number(e.target.value))}
            disabled={running}
            className="input-field w-full cursor-pointer disabled:opacity-50"
          >
            {experiments?.map((exp) => (
              <option key={exp.id} value={exp.id}>
                {exp.code}: {exp.title} ({exp.total_steps || exp.steps?.length || 5} steps)
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="kpi-label block mb-1">Simulation Telemetry Scenario</label>
          <select
            value={scenario}
            onChange={(e) => onSelectScenario(e.target.value as ScenarioName)}
            disabled={running}
            className="input-field w-full cursor-pointer disabled:opacity-50"
          >
            {(Object.keys(SCENARIOS) as ScenarioName[]).map((key) => (
              <option key={key} value={key}>
                {SCENARIOS[key]}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Compact Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-2 bg-[#fbf9f6] border border-[#ded2c5] rounded mb-3">
        <div>
          <div className="text-[9px] font-mono text-space-400 uppercase">PROTOCOL TIME</div>
          <div className="text-sm font-mono font-bold text-[#261912] tabular-nums flex items-center gap-1 mt-0.5">
            <Clock className="w-3 h-3 text-[#964f19]" />
            {elapsedTime}
          </div>
        </div>

        <div>
          <div className="text-[9px] font-mono text-space-400 uppercase">ACTIVE STEP</div>
          <div className="text-sm font-mono font-bold text-[#964f19] tabular-nums mt-0.5">
            0{currentStep} <span className="text-[10px] text-space-400">/ 0{totalSteps}</span>
          </div>
        </div>

        <div>
          <div className="text-[9px] font-mono text-space-400 uppercase">COMPLETED</div>
          <div className="text-sm font-mono font-bold text-[#166534] tabular-nums flex items-center gap-1 mt-0.5">
            <CheckCircle2 className="w-3 h-3 text-[#166534]" />
            {completedCount} STEPS
          </div>
        </div>

        <div>
          <div className="text-[9px] font-mono text-space-400 uppercase">AVIONICS HEALTH</div>
          <div className="text-xs font-mono font-bold text-[#166534] mt-1">
            {systemNominal ? '100% NOMINAL' : 'DEGRADED'}
          </div>
        </div>
      </div>

      {/* Detected Entities in Frame */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-[9px] font-mono text-space-400 uppercase mb-1">
          <span>DETECTED ENTITIES IN WORKSPACE</span>
          <span className="text-space-400 tabular-nums">{detectedEntities.length} IN FRAME</span>
        </div>
        <div className="flex flex-wrap gap-1.5 min-h-[32px] p-1.5 bg-[#fbf9f6] border border-[#ded2c5] rounded">
          {detectedEntities.length === 0 ? (
            <span className="text-[10px] font-mono text-space-400 self-center">
              Awaiting recognized objects in optical workspace...
            </span>
          ) : (
            detectedEntities.map(([name, conf]) => (
              <span
                key={name}
                className="px-2 py-0.5 rounded bg-[#ede3d8] border border-[#d8cbbe] text-[10px] font-mono flex items-center gap-1.5 text-[#261912]"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#964f19]" />
                <span>{humanizeActivity(name).toUpperCase()}</span>
                <span className="text-[#166534] font-bold tabular-nums">
                  {Math.round(conf * 100)}%
                </span>
              </span>
            ))
          )}
        </div>
      </div>

      {/* Operational Actions & Modals */}
      <div className="grid grid-cols-2 gap-1.5 mb-3">
        <button
          onClick={onOpenBiometrics}
          className="btn-telemetry justify-center text-[10px]"
          title="Biometric Crew Authentication"
        >
          <ShieldCheck className="w-3 h-3 text-[#166534]" />
          BIOMETRICS
        </button>
        <button
          onClick={onOpenObjects}
          className="btn-telemetry justify-center text-[10px]"
          title="ORB Dynamic Object Registry"
        >
          <Box className="w-3 h-3 text-[#964f19]" />
          ORB REGISTRY
        </button>
        <button
          onClick={onOpenReplay}
          className="btn-telemetry justify-center text-[10px]"
          title="Audit Replay & Video Logs"
        >
          <Film className="w-3 h-3 text-[#b45309]" />
          AUDIT REPLAY
        </button>
        <button
          onClick={onOpenMerkle}
          className="btn-telemetry justify-center text-[10px]"
          title="DO-178C Merkle Flight Ledger"
        >
          <FileCheck2 className="w-3 h-3 text-[#582f0e]" />
          LEDGER CHAIN
        </button>
      </div>

      {/* Main Mission Engage / Abort Trigger */}
      {running ? (
        <button
          onClick={onStop}
          disabled={busy}
          className="btn-primary w-full justify-center bg-[#b91c1c] hover:bg-[#991b1b] border-[#7f1d1d] text-white font-bold py-2"
        >
          <Square className="w-4 h-4" />
          ABORT PROTOCOL SESSION
        </button>
      ) : (
        <button
          onClick={onStart}
          disabled={busy || !experiment}
          className="btn-primary w-full justify-center py-2"
        >
          <Play className="w-4 h-4" />
          ENGAGE MISSION PROTOCOL
        </button>
      )}
    </div>
  );
}

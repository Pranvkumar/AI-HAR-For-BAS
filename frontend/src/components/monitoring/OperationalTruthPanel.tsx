import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  HelpCircle,
  ShieldCheck,
  ShieldAlert,
  Zap,
} from 'lucide-react';
import type { ValidationStatus } from '@/types/api';
import { humanizeActivity } from '@/services/adapters';

interface OperationalTruthPanelProps {
  detectedActivity?: string | null;
  confidence?: number;
  expectedStep?: string | null;
  stepNumber?: number;
  totalSteps?: number;
  status?: ValidationStatus;
  guidance?: string | null;
  nextStepName?: string | null;
  running?: boolean;
}

export default function OperationalTruthPanel({
  detectedActivity,
  confidence = 0,
  expectedStep,
  stepNumber = 1,
  totalSteps = 5,
  status = 'CORRECT',
  guidance,
  nextStepName,
  running = false,
}: OperationalTruthPanelProps) {
  const confPct = Math.round(confidence * 100);

  // Conformance verdict presentation
  const verdictConfig = {
    CORRECT: {
      tag: 'NOMINAL CONFORMANCE',
      headline: 'ASTRONAUT IS ON CORRECT STEP',
      note: 'Observed action matches the deterministic DO-178C state machine protocol sequence.',
      bg: 'bg-[#f0fdf4]',
      border: 'border-[#bbf7d0]',
      text: 'text-[#166534]',
      icon: CheckCircle2,
    },
    DUPLICATE: {
      tag: 'STEP CONFIRMED',
      headline: 'STEP CONFIRMED // READY FOR TRANSITION',
      note: 'Step milestones satisfied. Proceed with subsequent procedure actions.',
      bg: 'bg-[#faefe6]',
      border: 'border-[#fed7aa]',
      text: 'text-[#964f19]',
      icon: CheckCircle2,
    },
    WARNING: {
      tag: 'LOW CONFIDENCE',
      headline: 'CONFIDENCE BELOW SAFETY THRESHOLD',
      note: 'Camera line-of-sight partially obstructed or action ambiguously detected. Re-verify visual.',
      bg: 'bg-[#fffbeb]',
      border: 'border-[#fde68a]',
      text: 'text-[#b45309]',
      icon: AlertTriangle,
    },
    SEQUENCE_VIOLATION: {
      tag: 'SEQUENCE VIOLATION',
      headline: 'NON-CONFORMING ACTION DETECTED',
      note: 'CRITICAL: Astronaut performed an action out of sequence. Halt action and realign to protocol.',
      bg: 'bg-[#fef2f2]',
      border: 'border-[#fecaca]',
      text: 'text-[#b91c1c]',
      icon: ShieldAlert,
    },
  }[status] ?? {
    tag: 'STANDBY',
    headline: 'AWAITING MISSION TELEMETRY',
    note: 'Engage session to initiate real-time state machine tracking.',
    bg: 'bg-[#fbf9f6]',
    border: 'border-[#ded2c5]',
    text: 'text-space-400',
    icon: HelpCircle,
  };

  const VerdictIcon = verdictConfig.icon;

  return (
    <div className="panel p-3">
      {/* Panel Header */}
      <div className="flex items-center justify-between pb-2 mb-3 border-b border-[#ded2c5]">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-[#964f19]" />
          <span className="text-[11px] font-mono font-bold tracking-[0.14em] text-[#261912] uppercase">
            Operational Situational Truth
          </span>
        </div>
        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-[#ede3d8] border border-[#d8cbbe] text-[#166534] font-bold">
          REAL-TIME HAR ENGINE
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
        {/* Question 1: What is happening right now? */}
        <div className="p-3 rounded bg-[#fbf9f6] border border-[#ded2c5]">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[9px] font-mono font-bold tracking-wider text-space-400 uppercase">
              Q1 // CURRENT DETECTED ACTION
            </span>
            <span className="text-[9px] font-mono text-space-400">WHAT IS HAPPENING?</span>
          </div>

          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-[#964f19] shrink-0" />
            <span className="text-sm font-bold font-mono text-[#261912] tracking-wide truncate">
              {running && detectedActivity
                ? humanizeActivity(detectedActivity).toUpperCase()
                : 'AWAITING ACTIVE SENSOR TELEMETRY'}
            </span>
          </div>

          {/* Model Confidence Bar */}
          <div className="flex items-center justify-between text-[10px] font-mono mb-1">
            <span className="text-space-400">Model Certainty:</span>
            <span
              className={`font-bold tabular-nums ${
                confPct >= 70 ? 'text-[#166534]' : confPct >= 40 ? 'text-[#b45309]' : 'text-space-400'
              }`}
            >
              {running ? `${confPct}%` : '—'}
            </span>
          </div>
          <div className="w-full bg-[#f0e7de] h-1.5 rounded-full overflow-hidden border border-[#ded2c5]">
            <div
              className={`h-full transition-all duration-300 ${
                confPct >= 70 ? 'bg-[#166534]' : 'bg-[#b45309]'
              }`}
              style={{ width: `${running ? confPct : 0}%` }}
            />
          </div>
        </div>

        {/* Question 2: What does the system expect? */}
        <div className="p-3 rounded bg-[#fbf9f6] border border-[#ded2c5]">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[9px] font-mono font-bold tracking-wider text-space-400 uppercase">
              Q2 // EXPECTED PROCEDURE STEP
            </span>
            <span className="text-[9px] font-mono text-space-400">WHAT DOES SYSTEM EXPECT?</span>
          </div>

          <div className="flex items-center gap-2 mb-2">
            <ShieldCheck className="w-4 h-4 text-[#166534] shrink-0" />
            <span className="text-sm font-bold font-mono text-[#261912] tracking-wide truncate">
              {expectedStep
                ? humanizeActivity(expectedStep).toUpperCase()
                : `STEP 0${stepNumber} OF 0${totalSteps}`}
            </span>
          </div>

          <p className="text-[10px] font-mono text-space-400 line-clamp-2 leading-relaxed">
            {guidance || 'Astronaut is expected to conform to the predefined scientific flight sequence.'}
          </p>
        </div>
      </div>

      {/* Question 3: Is the astronaut on the correct step? (High-consequence verdict) */}
      <div className={`p-3 rounded border mb-3 ${verdictConfig.bg} ${verdictConfig.border}`}>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[9px] font-mono font-bold tracking-wider text-[#261912] uppercase flex items-center gap-1.5">
            <VerdictIcon className={`w-3.5 h-3.5 ${verdictConfig.text}`} />
            Q3 // CONFORMANCE VERDICT: {verdictConfig.tag}
          </span>
          <span className="text-[9px] font-mono text-space-400">IS CREW ON STEP?</span>
        </div>

        <div className={`text-xs font-bold font-mono tracking-wider ${verdictConfig.text} mb-1`}>
          {verdictConfig.headline}
        </div>
        <p className="text-[11px] font-sans text-space-300 leading-relaxed">
          {verdictConfig.note}
        </p>
      </div>

      {/* Question 4: What should happen next? */}
      <div className="p-2.5 rounded bg-[#fbf9f6] border border-[#ded2c5] flex items-center justify-between">
        <div className="flex items-center gap-2.5 min-w-0">
          <ArrowRight className="w-4 h-4 text-[#964f19] shrink-0" />
          <div className="min-w-0">
            <div className="text-[9px] font-mono font-bold text-space-400 uppercase">
              Q4 // UPCOMING SUBSEQUENT ACTION
            </div>
            <div className="text-[11px] font-mono font-bold text-[#261912] truncate">
              {nextStepName
                ? humanizeActivity(nextStepName).toUpperCase()
                : stepNumber >= totalSteps
                ? 'PROTOCOL CONCLUSION & SAMPLE CONTAINMENT'
                : `ADVANCE TO PROCEDURE STEP 0${stepNumber + 1}`}
            </div>
          </div>
        </div>
        <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-[#ede3d8] border border-[#d8cbbe] text-[#261912] shrink-0 ml-2 font-bold">
          NEXT
        </span>
      </div>
    </div>
  );
}

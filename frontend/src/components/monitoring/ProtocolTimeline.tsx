import { CheckCircle2, AlertTriangle, ArrowRight, ShieldAlert, ListOrdered } from 'lucide-react';
import type { ApiExperimentStep, ValidationStatus } from '@/types/api';
import { humanizeActivity } from '@/services/adapters';

interface ProtocolTimelineProps {
  steps?: ApiExperimentStep[];
  currentStepNumber: number;
  totalSteps: number;
  progress: number;
  status?: ValidationStatus;
  completedActivities?: string[];
}

export default function ProtocolTimeline({
  steps = [],
  currentStepNumber,
  totalSteps,
  progress,
  status = 'CORRECT',
  completedActivities = [],
}: ProtocolTimelineProps) {
  const displayedSteps: ApiExperimentStep[] = steps.length > 0
    ? steps
    : Array.from({ length: totalSteps || 5 }, (_, i) => ({
        id: i + 1,
        step_number: i + 1,
        title: `Procedure Milestone ${i + 1}`,
        expected_activity: `step_${i + 1}`,
        description: `Operational milestone execution for phase ${i + 1}.`,
        safety_critical: i === 2,
      }));

  const isViolation = status === 'SEQUENCE_VIOLATION';

  return (
    <div className="panel p-3">
      {/* Header with Progress Metrics */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 mb-3 border-b border-[#ded2c5]">
        <div className="flex items-center gap-2">
          <ListOrdered className="w-4 h-4 text-[#964f19]" />
          <span className="text-[11px] font-mono font-bold tracking-[0.14em] text-[#261912] uppercase">
            Experiment Protocol State Machine
          </span>
          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-[#ede3d8] border border-[#d8cbbe] text-[#261912] font-semibold">
            DO-178C FSM
          </span>
        </div>
        <div className="flex items-center gap-3 font-mono text-[11px] tabular-nums">
          <span className="text-space-400">
            STEP <span className="text-[#261912] font-bold">{Math.min(currentStepNumber, totalSteps || 5)}</span> / {totalSteps || 5}
          </span>
          <span className="text-space-400">|</span>
          <span className="text-space-400">
            PROGRESS <span className="text-[#166534] font-bold">{Math.round(progress)}%</span>
          </span>
          <span className="text-space-400">|</span>
          <span className={`font-semibold ${isViolation ? 'text-[#b91c1c]' : 'text-[#166534]'}`}>
            {isViolation ? 'VIOLATION DETECTED' : '100% CONFORMANCE'}
          </span>
        </div>
      </div>

      {/* Progress Track */}
      <div className="w-full bg-[#f0e7de] h-1.5 rounded-full overflow-hidden border border-[#ded2c5] mb-3.5">
        <div
          className={`h-full transition-all duration-300 ${
            isViolation
              ? 'bg-[#b91c1c]'
              : 'bg-[#964f19]'
          }`}
          style={{ width: `${Math.min(Math.max(progress, 0), 100)}%` }}
        />
      </div>

      {/* Horizontal Step Sequence / Visual State Machine */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">
        {displayedSteps.map((step, idx) => {
          const stepNum = step.step_number || idx + 1;
          const isCompleted = stepNum < currentStepNumber || completedActivities.includes(step.expected_activity);
          const isActive = stepNum === currentStepNumber;
          const isUpcoming = stepNum > currentStepNumber && !isCompleted;
          const isFailedStep = isActive && isViolation;

          return (
            <div
              key={step.id || stepNum}
              className={`relative p-2.5 rounded border transition-all ${
                isFailedStep
                  ? 'bg-[#fef2f2] border-[#fecaca] text-[#b91c1c]'
                  : isActive
                  ? 'bg-[#faefe6] border-[#964f19]/60 text-[#261912] shadow-sm'
                  : isCompleted
                  ? 'bg-[#f0fdf4] border-[#bbf7d0] text-[#166534]'
                  : 'bg-[#fcfaf7] border-[#ded2c5] text-space-400'
              }`}
            >
              {/* Step Status Badge & Critical Indicator */}
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-mono font-bold tracking-wider text-[#261912]">
                  STEP 0{stepNum}
                </span>
                <div className="flex items-center gap-1">
                  {step.safety_critical && (
                    <span
                      title="Safety Critical Procedure Step"
                      className="px-1 py-0.2 rounded text-[9px] font-mono font-bold bg-[#fffbeb] border border-[#fed7aa] text-[#b45309] flex items-center gap-0.5"
                    >
                      <ShieldAlert className="w-2.5 h-2.5" />
                      CRIT
                    </span>
                  )}
                  {isCompleted && (
                    <span className="text-[9px] font-mono text-[#166534] flex items-center gap-0.5 font-bold">
                      <CheckCircle2 className="w-3 h-3 text-[#166534]" />
                      DONE
                    </span>
                  )}
                  {isActive && !isFailedStep && (
                    <span className="text-[9px] font-mono text-[#964f19] flex items-center gap-1 font-bold animate-pulse">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#964f19]" />
                      ACTIVE
                    </span>
                  )}
                  {isFailedStep && (
                    <span className="text-[9px] font-mono text-[#b91c1c] flex items-center gap-1 font-bold">
                      <AlertTriangle className="w-3 h-3 text-[#b91c1c]" />
                      FAULT
                    </span>
                  )}
                  {isUpcoming && (
                    <span className="text-[9px] font-mono text-space-400">
                      PENDING
                    </span>
                  )}
                </div>
              </div>

              {/* Step Title / Activity */}
              <div className="text-[11px] font-bold font-sans tracking-wide truncate mb-1 text-[#261912]">
                {step.title || humanizeActivity(step.expected_activity)}
              </div>

              {/* Step Description / Operational Note */}
              <p className="text-[10px] font-mono text-space-400 line-clamp-2 leading-relaxed">
                {step.description || `Execute protocol activity: ${humanizeActivity(step.expected_activity)}`}
              </p>

              {/* State transition pointer for desktop */}
              {idx < displayedSteps.length - 1 && (
                <div className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 z-10 text-space-400 pointer-events-none">
                  <ArrowRight className="w-3 h-3" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

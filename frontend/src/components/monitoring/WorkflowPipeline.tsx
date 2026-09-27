import { Eye, Brain, CheckCircle2, Bot, ChevronRight } from 'lucide-react';

interface WorkflowPipelineProps {
  activeStep?: number;
}

const pipelineSteps = [
  {
    phase: '01',
    label: 'OPTICAL HAR',
    subtitle: 'Pose & Object Tracking',
    icon: Eye,
    color: 'text-accent-400',
    border: 'border-accent-500/30',
    bg: 'bg-accent-500/10',
    rate: '30 FPS',
  },
  {
    phase: '02',
    label: 'COGNITIVE INTENT',
    subtitle: 'Temporal Transformer',
    icon: Brain,
    color: 'text-violetx-400',
    border: 'border-violetx-500/30',
    bg: 'bg-violetx-500/10',
    rate: '12.4ms',
  },
  {
    phase: '03',
    label: 'FSM VALIDATION',
    subtitle: 'Procedure Conformance',
    icon: CheckCircle2,
    color: 'text-tealx-400',
    border: 'border-tealx-500/30',
    bg: 'bg-tealx-500/10',
    rate: 'DO-178C',
  },
  {
    phase: '04',
    label: 'CREW COPILOT',
    subtitle: 'Autonomous Speech & HUD',
    icon: Bot,
    color: 'text-amberx-400',
    border: 'border-amberx-500/30',
    bg: 'bg-amberx-500/10',
    rate: 'REALTIME',
  },
];

export default function WorkflowPipeline({ activeStep = 2 }: WorkflowPipelineProps) {
  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between mb-3 border-b border-space-800/80 pb-2.5">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-accent-400 animate-pulse" />
          <span className="text-xs font-mono font-bold tracking-wider text-space-100 uppercase">
            Onboard Avionics Inference Pipeline
          </span>
        </div>
        <span className="text-[10px] font-mono text-space-400 tracking-wider">
          ZERO-LATENCY PIPELINE ARCHITECTURE
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {pipelineSteps.map((step, idx) => {
          const Icon = step.icon;
          const isActive = idx <= activeStep;
          return (
            <div
              key={step.phase}
              className={`relative p-3 rounded-lg border transition-all duration-300 ${
                isActive
                  ? `${step.bg} ${step.border} shadow-lg shadow-black/40`
                  : 'bg-space-900/40 border-space-800/50 opacity-60'
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <span className="text-[10px] font-mono font-bold text-space-400">
                  STAGE {step.phase}
                </span>
                <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-space-950/80 border border-space-800 text-space-300">
                  {step.rate}
                </span>
              </div>

              <div className="flex items-center gap-3 mb-2">
                <div className={`w-8 h-8 rounded-md ${step.bg} border ${step.border} flex items-center justify-center shrink-0`}>
                  <Icon className={`w-4 h-4 ${step.color}`} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-bold text-white truncate tracking-wide">
                    {step.label}
                  </div>
                  <div className="text-[10px] text-space-300 truncate">
                    {step.subtitle}
                  </div>
                </div>
              </div>

              {/* Status pulse line */}
              <div className="w-full h-1 bg-space-950/80 rounded-full overflow-hidden mt-1">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    isActive ? 'bg-gradient-to-r from-accent-500 to-tealx-400' : 'bg-transparent'
                  }`}
                  style={{ width: isActive ? '100%' : '0%' }}
                />
              </div>

              {/* Connecting chevron on right for desktop */}
              {idx < pipelineSteps.length - 1 && (
                <div className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 z-10 text-space-600">
                  <ChevronRight className="w-3.5 h-3.5" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

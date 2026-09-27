import { Check, Loader2, Circle, Clock } from 'lucide-react';
import type { ExperimentStep } from '@/types';

interface ExperimentStepperProps {
  steps: ExperimentStep[];
}

const statusConfig: Record<string, { icon: typeof Check; color: string; bg: string; border: string; label: string }> = {
  Completed: { icon: Check, color: 'text-tealx-400', bg: 'bg-tealx-500/15', border: 'border-tealx-500/40', label: 'VERIFIED' },
  'In Progress': { icon: Loader2, color: 'text-amberx-400', bg: 'bg-amberx-500/15', border: 'border-amberx-500/40', label: 'ACTIVE' },
  Pending: { icon: Circle, color: 'text-space-500', bg: 'bg-space-950/60', border: 'border-space-800', label: 'QUEUED' },
};

export default function ExperimentStepper({ steps }: ExperimentStepperProps) {
  return (
    <div className="space-y-2">
      {steps.map((step, i) => {
        const config = statusConfig[step.status];
        const Icon = config.icon;
        const isLast = i === steps.length - 1;

        return (
          <div key={step.id} className="flex gap-4 group">
            {/* Vertical connector line and step circle */}
            <div className="flex flex-col items-center">
              <div className={`w-9 h-9 rounded-lg ${config.bg} border ${config.border} flex items-center justify-center shrink-0 shadow-md transition-all duration-300 group-hover:scale-105`}>
                <Icon className={`w-4 h-4 ${config.color} ${step.status === 'In Progress' ? 'animate-spin' : ''}`} />
              </div>
              {!isLast && (
                <div className={`w-0.5 flex-1 ${steps[i + 1]?.status === 'Completed' ? 'bg-tealx-500/40' : 'bg-space-800'} my-1 min-h-[2.5rem]`} />
              )}
            </div>

            {/* Step content card */}
            <div className={`flex-1 p-3.5 rounded-lg border transition-all duration-200 mb-2 ${
              step.status === 'In Progress'
                ? 'bg-space-900/90 border-amberx-500/40 shadow-glow-accent/10'
                : step.status === 'Completed'
                ? 'bg-space-900/50 border-space-800/80'
                : 'bg-space-950/40 border-space-800/50 opacity-70'
            }`}>
              <div className="flex items-center justify-between mb-1.5 flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono font-bold text-space-400 tracking-wider">
                    PHASE {String(step.id).padStart(2, '0')}
                  </span>
                  <h3 className={`text-sm font-bold tracking-wide font-sans ${step.status === 'Pending' ? 'text-space-300' : 'text-white'}`}>
                    {step.title}
                  </h3>
                </div>
                <span className={`badge ${config.bg} ${config.color} border ${config.border} font-mono text-[10px]`}>
                  {config.label}
                </span>
              </div>
              <p className="text-xs text-space-300 leading-relaxed font-sans">{step.description}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

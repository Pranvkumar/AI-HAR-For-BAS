import { useNavigate } from 'react-router-dom';
import { ChevronRight, FlaskConical, Play, CheckCircle2, Clock, Layers } from 'lucide-react';
import type { Experiment } from '@/types';
import ProgressBar from '@/components/common/ProgressBar';
import StatusBadge from '@/components/common/StatusBadge';

const statusVariant: Record<string, 'success' | 'warning' | 'info' | 'neutral'> = {
  Active: 'warning',
  Completed: 'success',
  Scheduled: 'info',
  Paused: 'neutral',
};

export default function ExperimentCard({ experiment }: { experiment: Experiment }) {
  const navigate = useNavigate();

  return (
    <div
      onClick={() => navigate(`/experiments/${experiment.id}`)}
      className="panel p-4 cursor-pointer hover:border-accent-500/50 hover:shadow-glow-accent transition-all duration-300 group relative overflow-hidden"
    >
      {/* Decorative top accent line */}
      <div className={`absolute top-0 left-0 right-0 h-0.5 ${
        experiment.status === 'Completed'
          ? 'bg-tealx-500'
          : experiment.status === 'Active'
          ? 'bg-amberx-500'
          : 'bg-accent-500'
      }`} />

      <div className="flex items-start justify-between mb-3 pt-1">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-accent-500/15 border border-accent-500/30 flex items-center justify-center group-hover:scale-105 transition-transform">
            <FlaskConical className="w-4 h-4 text-accent-400" />
          </div>
          <div>
            <div className="text-[10px] font-mono text-space-400 font-bold uppercase tracking-wider">{experiment.id}</div>
            <div className="text-sm font-bold text-white group-hover:text-accent-300 transition-colors">{experiment.name}</div>
          </div>
        </div>
        <ChevronRight className="w-4 h-4 text-space-500 group-hover:text-accent-400 group-hover:translate-x-1 transition-all" />
      </div>

      <div className="flex items-center gap-2 mb-3">
        <span className="badge bg-space-950/80 text-space-300 border border-space-800 text-[10px] font-mono">
          <Layers className="w-3 h-3 inline mr-1 text-space-400" />
          {experiment.category}
        </span>
        <span className="badge bg-space-950/80 text-space-300 border border-space-800 text-[10px] font-mono">
          {experiment.environment}
        </span>
      </div>

      <div className="mb-3 p-2.5 rounded-lg bg-space-950/60 border border-space-800/80">
        <div className="flex items-center justify-between mb-1.5 font-mono text-xs">
          <span className="text-space-400">Step {experiment.currentStep} of {experiment.totalSteps}</span>
          <span className="font-bold text-accent-300">{experiment.progress}%</span>
        </div>
        <ProgressBar
          value={experiment.progress}
          variant={experiment.status === 'Completed' ? 'success' : 'accent'}
        />
      </div>

      <div className="flex items-center justify-between pt-1">
        <div className="flex items-center gap-1.5 text-xs text-space-400 font-mono">
          <Clock className="w-3 h-3 text-space-500" />
          <span>{experiment.duration}</span>
        </div>
        <StatusBadge status={experiment.status} variant={statusVariant[experiment.status] ?? 'neutral'}>
          {experiment.status.toUpperCase()}
        </StatusBadge>
      </div>
    </div>
  );
}

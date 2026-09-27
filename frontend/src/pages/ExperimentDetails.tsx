import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, FlaskConical, Clock, Layers, Globe, ListOrdered, Percent, ShieldCheck, Play } from 'lucide-react';
import AppLayout from '@/components/layout/AppLayout';
import Panel from '@/components/common/Panel';
import ProgressBar from '@/components/common/ProgressBar';
import StatusBadge from '@/components/common/StatusBadge';
import ExperimentStepper from '@/components/experiment/ExperimentStepper';
import { api } from '@/services/api';
import { useQuery } from '@/hooks/useApi';
import { toExperiment } from '@/services/adapters';

const statusVariant: Record<string, 'success' | 'warning' | 'info' | 'neutral'> = {
  Active: 'warning',
  Completed: 'success',
  Scheduled: 'info',
  Paused: 'neutral',
};

const DETAIL_POLL_MS = 3000;

export default function ExperimentDetails() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data, loading, error } = useQuery(() => api.getExperiment(id ?? ''), {
    intervalMs: DETAIL_POLL_MS,
    enabled: Boolean(id),
    deps: [id],
  });

  if (loading) {
    return (
      <AppLayout title="Loading protocol telemetry…" subtitle="">
        <div className="text-center py-24">
          <FlaskConical className="w-10 h-10 text-accent-400 mx-auto mb-3 animate-pulse" />
          <p className="text-sm font-mono text-space-300">Synchronizing procedure definition...</p>
        </div>
      </AppLayout>
    );
  }

  if (error || !data) {
    return (
      <AppLayout title="Experiment Not Found" subtitle="">
        <Panel hudCorners={true} className="text-center py-16 max-w-lg mx-auto">
          <FlaskConical className="w-10 h-10 text-space-600 mx-auto mb-3" />
          <p className="text-sm font-mono text-space-300 mb-4">{error ?? 'Experiment manifest does not exist.'}</p>
          <button onClick={() => navigate('/experiments')} className="btn-primary mx-auto">
            <ArrowLeft className="w-4 h-4" />
            Return to Manifest
          </button>
        </Panel>
      </AppLayout>
    );
  }

  const experiment = toExperiment(data);

  return (
    <AppLayout
      title={experiment.name}
      subtitle={`Mission Procedure Specification: ${experiment.id}`}
    >
      {/* Top action navigation */}
      <div className="flex items-center justify-between gap-3 mb-6">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/experiments')} className="btn-telemetry">
            <ArrowLeft className="w-4 h-4" />
            Manifest
          </button>
          <StatusBadge status={experiment.status} variant={statusVariant[experiment.status] ?? 'neutral'}>
            {experiment.status.toUpperCase()}
          </StatusBadge>
          <span className="badge bg-space-950/80 border border-space-800 text-tealx-400 font-mono text-xs">
            <ShieldCheck className="w-3.5 h-3.5 inline mr-1" />
            DO-178C FLIGHT QUALIFIED
          </span>
        </div>

        <button
          onClick={() => navigate('/monitoring')}
          className="btn-primary"
        >
          <Play className="w-3.5 h-3.5" />
          ENGAGE IN LIVE DECK
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Stepper Workflow */}
        <div className="lg:col-span-2">
          <Panel hudCorners={true} title="Procedural Execution Sequence">
            <ExperimentStepper steps={experiment.steps} />
          </Panel>
        </div>

        {/* Right: Experiment Information & Telemetry Specs */}
        <div className="space-y-4">
          <Panel hudCorners={true} title="Payload Specifications">
            <div className="space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between py-2 border-b border-space-800">
                <div className="flex items-center gap-2 text-space-400">
                  <FlaskConical className="w-4 h-4 text-accent-400" />
                  <span>Protocol Code</span>
                </div>
                <span className="font-bold text-white">{experiment.id}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-space-800">
                <div className="flex items-center gap-2 text-space-400">
                  <Globe className="w-4 h-4 text-accent-400" />
                  <span>Environment</span>
                </div>
                <span className="text-white">{experiment.environment}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-space-800">
                <div className="flex items-center gap-2 text-space-400">
                  <Clock className="w-4 h-4 text-accent-400" />
                  <span>Est. Duration</span>
                </div>
                <span className="text-white">{experiment.duration}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-space-800">
                <div className="flex items-center gap-2 text-space-400">
                  <ListOrdered className="w-4 h-4 text-accent-400" />
                  <span>Step Status</span>
                </div>
                <span className="text-tealx-400 font-bold">Step {experiment.currentStep} of {experiment.totalSteps}</span>
              </div>
              <div className="pt-2">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5 text-space-300">
                    <Percent className="w-3.5 h-3.5 text-accent-400" />
                    <span>Completion Rate</span>
                  </div>
                  <span className="text-accent-300 font-bold">{experiment.progress}%</span>
                </div>
                <ProgressBar
                  value={experiment.progress}
                  showLabel={false}
                  variant={experiment.status === 'Completed' ? 'success' : 'accent'}
                />
              </div>
            </div>
          </Panel>

          {/* Discipline card */}
          <Panel hudCorners={true} title="Discipline Classification">
            <div className="flex items-center gap-2.5 p-3 rounded-lg bg-space-950/70 border border-space-800/80">
              <div className="w-8 h-8 rounded-md bg-accent-500/15 border border-accent-500/30 flex items-center justify-center">
                <Layers className="w-4 h-4 text-accent-400" />
              </div>
              <div>
                <span className="text-[10px] font-mono text-space-400 block uppercase">Scientific Domain</span>
                <span className="text-sm font-bold text-white font-sans">{experiment.category}</span>
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </AppLayout>
  );
}

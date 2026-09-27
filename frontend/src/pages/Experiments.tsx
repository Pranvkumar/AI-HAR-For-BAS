import { Search, FlaskConical, Filter, Sparkles, PlusCircle } from 'lucide-react';
import { useMemo, useState } from 'react';
import AppLayout from '@/components/layout/AppLayout';
import ExperimentCard from '@/components/experiment/ExperimentCard';
import Panel from '@/components/common/Panel';
import { api } from '@/services/api';
import { useQuery } from '@/hooks/useApi';
import { toExperiment } from '@/services/adapters';

const statusFilters = ['All', 'Active', 'Completed', 'Scheduled'] as const;

const EXPERIMENTS_POLL_MS = 5000;

export default function Experiments() {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<typeof statusFilters[number]>('All');

  const { data, loading, error } = useQuery(() => api.listExperiments(), {
    intervalMs: EXPERIMENTS_POLL_MS,
  });

  const experiments = useMemo(() => (data ?? []).map(toExperiment), [data]);

  const filtered = experiments.filter((e) => {
    const matchesSearch =
      e.name.toLowerCase().includes(search.toLowerCase()) ||
      e.id.toLowerCase().includes(search.toLowerCase()) ||
      e.category.toLowerCase().includes(search.toLowerCase());
    const matchesFilter = filter === 'All' || e.status === filter;
    return matchesSearch && matchesFilter;
  });

  const activeCount = experiments.filter(e => e.status === 'Active').length;
  const completedCount = experiments.filter(e => e.status === 'Completed').length;
  const scheduledCount = experiments.filter(e => e.status === 'Scheduled').length;

  return (
    <AppLayout
      title="Scientific Experiment Manifest"
      subtitle="Flight-qualified microgravity science protocols, step-by-step procedures, and progress telemetry."
    >
      {error && (
        <div className="panel border-redx-500/30 p-3 mb-4 bg-redx-500/5">
          <p className="text-xs text-redx-400 font-mono">Payload data bus unreachable — {error}</p>
        </div>
      )}

      {/* Manifest Overview Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="panel p-3 bg-space-900/60 border-space-800">
          <span className="text-[10px] font-mono text-space-400 block mb-1">TOTAL PROTOCOLS</span>
          <span className="text-2xl font-mono font-bold text-white">{experiments.length}</span>
        </div>
        <div className="panel p-3 bg-space-900/60 border-space-800">
          <span className="text-[10px] font-mono text-amberx-400 block mb-1">IN EXECUTION</span>
          <span className="text-2xl font-mono font-bold text-amberx-400">{activeCount}</span>
        </div>
        <div className="panel p-3 bg-space-900/60 border-space-800">
          <span className="text-[10px] font-mono text-tealx-400 block mb-1">VERIFIED COMPLETE</span>
          <span className="text-2xl font-mono font-bold text-tealx-400">{completedCount}</span>
        </div>
        <div className="panel p-3 bg-space-900/60 border-space-800">
          <span className="text-[10px] font-mono text-accent-400 block mb-1">QUEUED SCHEDULE</span>
          <span className="text-2xl font-mono font-bold text-accent-300">{scheduledCount}</span>
        </div>
      </div>

      {/* Search and filters */}
      <Panel hudCorners={true} className="p-3 mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-space-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search experiments by code, title, or scientific discipline..."
              className="input-field w-full pl-10 font-mono text-xs"
            />
          </div>
          <div className="flex gap-1.5 p-1 rounded-lg bg-space-950/80 border border-space-800">
            {statusFilters.map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-md text-xs font-mono font-semibold transition-all ${
                  filter === f
                    ? 'bg-accent-500 text-white shadow-glow-accent'
                    : 'text-space-400 hover:text-white'
                }`}
              >
                {f.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </Panel>

      {/* Experiment count indicator */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <FlaskConical className="w-4 h-4 text-accent-400" />
          <span className="text-xs font-mono text-space-300">
            {loading ? 'Interrogating experiment register...' : `DISPLAYING ${filtered.length} EXPERIMENT MANIFESTS`}
          </span>
        </div>
      </div>

      {/* Experiment grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((exp) => (
          <ExperimentCard key={exp.id} experiment={exp} />
        ))}
      </div>

      {!loading && filtered.length === 0 && (
        <Panel hudCorners={true} className="text-center py-16">
          <FlaskConical className="w-10 h-10 text-space-600 mx-auto mb-3" />
          <p className="text-sm font-mono text-space-300">No experiment matches filter criteria.</p>
        </Panel>
      )}
    </AppLayout>
  );
}

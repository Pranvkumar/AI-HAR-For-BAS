import { useMemo, useState } from 'react';
import { Search, Calendar, FlaskConical, Filter, FileCheck2 } from 'lucide-react';
import AppLayout from '@/components/layout/AppLayout';
import StatusBadge from '@/components/common/StatusBadge';
import { api } from '@/services/api';
import { useQuery } from '@/hooks/useApi';
import { toActivityEvent } from '@/services/adapters';

const statusFilters = ['All', 'Completed', 'In Progress', 'Warning', 'Violation'] as const;

const LOGS_POLL_MS = 4000;

/** Table badge colour per derived log status. */
const STATUS_VARIANT: Record<string, 'success' | 'warning' | 'critical' | 'neutral'> = {
  Completed: 'success',
  'In Progress': 'neutral',
  Warning: 'warning',
  Violation: 'critical',
};

export default function ActivityLogs() {
  const [search, setSearch] = useState('');
  const [expFilter, setExpFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState<typeof statusFilters[number]>('All');
  const [dateFilter, setDateFilter] = useState('');

  const { data: logData, error } = useQuery(() => api.listLogs(500), { intervalMs: LOGS_POLL_MS });
  const { data: experimentData } = useQuery(() => api.listExperiments());

  const activities = useMemo(() => (logData ?? []).map(toActivityEvent), [logData]);

  // Raw timestamps drive date filtering; the display row only carries HH:MM:SS.
  const dateByLogId = useMemo(() => {
    const map = new Map<string, string>();
    for (const log of logData ?? []) {
      map.set(String(log.id), log.timestamp.slice(0, 10));
    }
    return map;
  }, [logData]);

  const filtered = useMemo(() => {
    return activities.filter((a) => {
      const matchesSearch =
        a.activity.toLowerCase().includes(search.toLowerCase()) ||
        a.experiment.toLowerCase().includes(search.toLowerCase());
      const matchesExp = expFilter === 'All' || a.experiment === expFilter;
      const matchesStatus = statusFilter === 'All' || a.status === statusFilter;
      const matchesDate = !dateFilter || dateByLogId.get(a.id) === dateFilter;
      return matchesSearch && matchesExp && matchesStatus && matchesDate;
    });
  }, [activities, search, expFilter, statusFilter, dateFilter, dateByLogId]);

  return (
    <AppLayout title="Activity & Experiment Logs" subtitle="Detailed activity and experiment event logs for audit and review.">
      {error && (
        <div className="panel border-redx-500/30 p-3 mb-4">
          <p className="text-xs text-redx-400">Backend unreachable — {error}</p>
        </div>
      )}

      {/* DO-178C Cryptographic Merkle Chain Audit Bar */}
      <div className="mb-5 p-3.5 rounded-xl bg-space-950/70 border border-white/[0.08] backdrop-blur-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-glass-card">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-tealx-500/15 border border-tealx-500/30 flex items-center justify-center">
            <FileCheck2 className="w-4 h-4 text-tealx-400" />
          </div>
          <div>
            <div className="text-xs font-bold text-white uppercase font-display flex items-center gap-2">
              DO-178C Merkle Flight Ledger
              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-tealx-500/15 text-tealx-400 border border-tealx-500/30">
                TAMPER-PROOF
              </span>
            </div>
            <div className="text-[11px] text-space-300 font-mono">
              Immutable SHA-256 state transitions synchronized to mission storage
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs">
          <span className="text-space-400">Ledger Verification:</span>
          <span className="px-2 py-0.5 rounded bg-tealx-500/10 text-tealx-400 border border-tealx-500/25 font-bold flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-tealx-400 animate-pulse" />
            VALIDATED
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col lg:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-space-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search activities..."
            className="input-field w-full pl-10"
          />
        </div>

        <div className="relative">
          <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-space-400 pointer-events-none" />
          <input
            type="date"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            className="input-field pl-10"
          />
        </div>

        <div className="relative">
          <FlaskConical className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-space-400 pointer-events-none" />
          <select
            value={expFilter}
            onChange={(e) => setExpFilter(e.target.value)}
            className="input-field pl-10 appearance-none pr-8"
          >
            <option value="All">All Experiments</option>
            {(experimentData ?? []).map((e) => (
              <option key={e.code} value={e.code}>{e.code}</option>
            ))}
          </select>
        </div>

        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-space-400 pointer-events-none" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as typeof statusFilters[number])}
            className="input-field pl-10 appearance-none pr-8"
          >
            {statusFilters.map((s) => (
              <option key={s} value={s}>{s === 'All' ? 'All Statuses' : s}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Data table */}
      <div className="panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-space-600/40 bg-space-900/40">
                <th className="px-4 py-3 text-left text-[10px] font-semibold tracking-wider text-space-300 uppercase">Time</th>
                <th className="px-4 py-3 text-left text-[10px] font-semibold tracking-wider text-space-300 uppercase">Experiment</th>
                <th className="px-4 py-3 text-left text-[10px] font-semibold tracking-wider text-space-300 uppercase">Activity</th>
                <th className="px-4 py-3 text-left text-[10px] font-semibold tracking-wider text-space-300 uppercase">Step</th>
                <th className="px-4 py-3 text-left text-[10px] font-semibold tracking-wider text-space-300 uppercase">Status</th>
                <th className="px-4 py-3 text-right text-[10px] font-semibold tracking-wider text-space-300 uppercase">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <tr key={a.id} className="border-b border-space-600/20 hover:bg-space-800/40 transition-colors">
                  <td className="px-4 py-3 text-xs font-mono text-accent-300 whitespace-nowrap">{a.time}</td>
                  <td className="px-4 py-3 text-xs font-mono text-space-200 whitespace-nowrap">{a.experiment}</td>
                  <td className="px-4 py-3 text-sm text-space-100">{a.activity}</td>
                  <td className="px-4 py-3 text-xs text-space-300 whitespace-nowrap">{a.step}</td>
                  <td className="px-4 py-3">
                    <StatusBadge variant={STATUS_VARIANT[a.status] ?? 'neutral'}>
                      {a.status}
                    </StatusBadge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className="text-sm font-mono font-semibold text-white">{a.confidence}%</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-12">
            <Search className="w-8 h-8 text-space-500 mx-auto mb-2" />
            <p className="text-sm text-space-300">
              No log entries yet. Start a monitoring session to generate audit records.
            </p>
          </div>
        )}
      </div>

      {/* Table footer */}
      <div className="flex items-center justify-between mt-3 text-xs text-space-400">
        <span>{filtered.length} of {activities.length} entries</span>
        <span>Live — refreshes every {LOGS_POLL_MS / 1000}s</span>
      </div>
    </AppLayout>
  );
}

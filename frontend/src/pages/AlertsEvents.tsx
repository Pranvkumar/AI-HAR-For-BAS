import { useMemo, useState } from 'react';
import { AlertTriangle, Info, Bell, ShieldAlert, Check, ShieldCheck, Filter, Search, Terminal } from 'lucide-react';
import AppLayout from '@/components/layout/AppLayout';
import KpiCard from '@/components/common/KpiCard';
import StatusBadge from '@/components/common/StatusBadge';
import Panel from '@/components/common/Panel';
import { api } from '@/services/api';
import { useQuery } from '@/hooks/useApi';
import { toAlertEvent } from '@/services/adapters';
import type { AlertSeverity } from '@/types';

const filters = ['All', 'Info', 'Warning', 'Critical'] as const;

const ALERTS_POLL_MS = 4000;

const severityConfig: Record<AlertSeverity, { icon: typeof Info; variant: 'success' | 'warning' | 'critical' | 'info' | 'neutral'; label: string; bg: string; border: string; text: string }> = {
  critical: { icon: ShieldAlert, variant: 'critical', label: 'CRITICAL', bg: 'bg-redx-500/10', border: 'border-redx-500/30', text: 'text-redx-400' },
  warning: { icon: AlertTriangle, variant: 'warning', label: 'WARNING', bg: 'bg-amberx-500/10', border: 'border-amberx-500/30', text: 'text-amberx-400' },
  info: { icon: Info, variant: 'info', label: 'INFO', bg: 'bg-accent-500/10', border: 'border-accent-500/30', text: 'text-accent-400' },
  system: { icon: Bell, variant: 'neutral', label: 'SYSTEM', bg: 'bg-space-800/40', border: 'border-space-700/50', text: 'text-space-300' },
};

export default function AlertsEvents() {
  const [filter, setFilter] = useState<typeof filters[number]>('All');
  const [search, setSearch] = useState('');
  const [acknowledging, setAcknowledging] = useState<number | null>(null);

  const { data: alertData, error, refetch } = useQuery(() => api.listAlerts(200), {
    intervalMs: ALERTS_POLL_MS,
  });
  const { data: summary, refetch: refetchSummary } = useQuery(() => api.getAlertSummary(), {
    intervalMs: ALERTS_POLL_MS,
  });

  const alerts = useMemo(() => (alertData ?? []).map((a) => toAlertEvent(a)), [alertData]);
  const acknowledgedIds = useMemo(
    () => new Set((alertData ?? []).filter((a) => a.acknowledged).map((a) => String(a.id))),
    [alertData],
  );

  const filtered = alerts.filter((a) => {
    const matchesFilter = (() => {
      if (filter === 'All') return true;
      if (filter === 'Info') return a.severity === 'info' || a.severity === 'system';
      if (filter === 'Warning') return a.severity === 'warning';
      if (filter === 'Critical') return a.severity === 'critical';
      return true;
    })();

    const matchesSearch = !search ||
      a.title.toLowerCase().includes(search.toLowerCase()) ||
      (a.action && a.action.toLowerCase().includes(search.toLowerCase())) ||
      a.time.includes(search);

    return matchesFilter && matchesSearch;
  });

  const handleAcknowledge = async (id: string) => {
    const numericId = Number(id);
    setAcknowledging(numericId);
    try {
      await api.acknowledgeAlert(numericId);
      refetch();
      refetchSummary();
    } finally {
      setAcknowledging(null);
    }
  };

  return (
    <AppLayout
      title="Alerts & Mission Events"
      subtitle="Real-time flight avionics telemetry alarms, hardware watchdog notices, and safety interrupts."
    >
      {error && (
        <div className="panel border-redx-500/30 p-3 mb-4 bg-redx-500/5">
          <p className="text-xs text-redx-400 font-mono">Telemetry link disrupted — {error}</p>
        </div>
      )}

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KpiCard
          label="Total Telemetry Events"
          value={summary?.total ?? 0}
          icon={<Bell className="w-4 h-4" />}
          change="+12/hr"
        />
        <KpiCard
          label="Active Alarms"
          value={summary?.active ?? 0}
          icon={<AlertTriangle className="w-4 h-4" />}
          variant={summary?.active ? 'warning' : 'default'}
        />
        <KpiCard
          label="Procedural Warnings"
          value={summary?.warnings ?? 0}
          icon={<AlertTriangle className="w-4 h-4" />}
          variant={summary?.warnings ? 'warning' : 'default'}
        />
        <KpiCard
          label="Critical Faults"
          value={summary?.critical ?? 0}
          icon={<ShieldAlert className="w-4 h-4" />}
          variant={(summary?.critical ?? 0) > 0 ? 'critical' : 'success'}
        />
      </div>

      {/* Filter and Search Bar */}
      <Panel hudCorners={true} className="mb-4 p-3">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 p-1 rounded-lg bg-space-950/80 border border-space-800">
            {filters.map((f) => (
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

          <div className="relative w-full sm:w-72">
            <Search className="w-3.5 h-3.5 text-space-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search telemetry events..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-field w-full pl-8 py-1.5 text-xs font-mono"
            />
          </div>
        </div>
      </Panel>

      {/* Alert Feed List */}
      <div className="space-y-3">
        {filtered.map((alert) => {
          const config = severityConfig[alert.severity];
          const Icon = config.icon;
          const isAcknowledged = acknowledgedIds.has(alert.id);

          return (
            <div
              key={alert.id}
              className={`panel p-4 transition-all duration-200 border ${
                alert.severity === 'critical'
                  ? 'border-redx-500/40 bg-redx-500/[0.04] shadow-glow-red/10'
                  : alert.severity === 'warning'
                  ? 'border-amberx-500/40 bg-amberx-500/[0.03]'
                  : alert.severity === 'info'
                  ? 'border-accent-500/40 bg-accent-500/[0.03]'
                  : 'border-white/[0.07]'
              }`}
            >
              <div className="flex items-start gap-3.5">
                <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 border ${config.bg} ${config.border}`}>
                  <Icon className={`w-4 h-4 ${config.text}`} />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <StatusBadge variant={config.variant}>{config.label}</StatusBadge>
                    <span className="text-[11px] font-mono text-space-400">{alert.time}</span>
                    <span className="text-[10px] font-mono text-space-500 uppercase">EVT-{alert.id.padStart(4, '0')}</span>
                    {isAcknowledged && (
                      <span className="badge bg-tealx-500/15 text-tealx-400 border border-tealx-500/30 flex items-center gap-1 text-[10px]">
                        <ShieldCheck className="w-3 h-3" />
                        ACKNOWLEDGED
                      </span>
                    )}
                  </div>
                  <div className="text-sm font-semibold text-white mb-1 tracking-wide font-sans">{alert.title}</div>
                  {alert.action && (
                    <div className="text-xs text-space-300 mt-1 font-mono p-2 rounded bg-space-950/70 border border-space-800/80">
                      <span className="text-accent-400 font-bold mr-1.5">[DIRECTIVE]:</span>
                      {alert.action}
                    </div>
                  )}
                </div>

                {!isAcknowledged && (
                  <button
                    onClick={() => void handleAcknowledge(alert.id)}
                    disabled={acknowledging === Number(alert.id)}
                    className="btn-telemetry shrink-0 text-tealx-400 hover:text-white hover:border-tealx-400"
                  >
                    <Check className="w-3.5 h-3.5 text-tealx-400" />
                    <span>ACK</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <Panel hudCorners={true} className="py-16 text-center">
          <Terminal className="w-10 h-10 text-space-600 mx-auto mb-3" />
          <p className="text-sm text-space-200 font-mono mb-1">
            Zero Telemetry Anomalies Detected
          </p>
          <p className="text-xs text-space-400 font-mono">
            Flight systems nominal. Switch scenario in Live Monitoring to inject test anomalies.
          </p>
        </Panel>
      )}
    </AppLayout>
  );
}

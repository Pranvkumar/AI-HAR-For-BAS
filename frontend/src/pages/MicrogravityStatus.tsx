import { Globe, Activity, Eye, Database, TrendingUp, Wind, Compass, Shield, Zap } from 'lucide-react';
import AppLayout from '@/components/layout/AppLayout';
import Panel from '@/components/common/Panel';
import KpiCard from '@/components/common/KpiCard';
import StatusDot from '@/components/common/StatusDot';
import Gauge from '@/components/charts/Gauge';
import MiniLineChart from '@/components/charts/MiniLineChart';
import { api } from '@/services/api';
import { useQuery } from '@/hooks/useApi';

const metricIcons: Record<string, typeof Globe> = {
  'Microgravity Status': Globe,
  'Experiment Stability': Activity,
  'Monitoring State': Eye,
  'Data Quality': Database,
};

const trendColors = ['#14b8a6', '#f59e0b', '#00d2ff', '#818cf8'];

const ENVIRONMENT_POLL_MS = 4000;

export default function MicrogravityStatus() {
  const { data, error } = useQuery(() => api.getEnvironment(), {
    intervalMs: ENVIRONMENT_POLL_MS,
  });

  const metrics = data?.metrics ?? [];
  const trends = data?.trends ?? [];
  const gauges = data?.gauges ?? [];

  return (
    <AppLayout
      title="Microgravity Environment & Dynamics"
      subtitle="Autonomous spacecraft rack acceleration, micro-g vibrational jitter, and environmental equilibrium."
    >
      {error && (
        <div className="panel border-redx-500/30 p-3 mb-4 bg-redx-500/5">
          <p className="text-xs text-redx-400 font-mono">Environmental bus offline — {error}</p>
        </div>
      )}

      {/* Top Telemetry KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {metrics.map((m) => {
          const Icon = metricIcons[m.label] ?? Globe;
          return (
            <KpiCard
              key={m.label}
              label={m.label}
              value={m.value}
              icon={<Icon className="w-4 h-4" />}
              variant="success"
              change="NOMINAL"
            />
          );
        })}
      </div>

      {/* Orbital Telemetry Banner */}
      <div className="panel p-4 mb-6 border-accent-500/20">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-accent-500/15 border border-accent-500/30 flex items-center justify-center">
              <Compass className="w-5 h-5 text-accent-400 animate-spin" style={{ animationDuration: '30s' }} />
            </div>
            <div>
              <div className="text-xs font-mono font-bold text-accent-300 uppercase tracking-wider">
                ORBITAL MICROGRAVITY EQUILIBRIUM: ~1.2 × 10⁻⁶ g
              </div>
              <p className="text-xs text-space-300">
                Onboard 3-axis accelerometer array synchronizing with European Drawer Rack (EDR-2) micro-vibration dampers.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="badge bg-tealx-500/15 text-tealx-400 border border-tealx-500/30 font-mono text-xs">
              <StatusDot variant="success" pulse />
              JITTER DAMPED
            </span>
          </div>
        </div>
      </div>

      {/* Large visual status panel */}
      <Panel
        hudCorners={true}
        title="Environmental Dynamics & Sensor Arrays"
        action={
          <span className="badge bg-space-800 text-tealx-400 border border-tealx-500/30 font-mono text-[10px]">
            ACTIVE TELEMETRY SYNC
          </span>
        }
      >
        {/* Gauges row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6 pb-6 border-b border-space-800">
          {gauges.map((g) => (
            <div key={g.label} className="panel bg-space-950/60 p-4 flex items-center justify-center border-space-800/80">
              <Gauge label={g.label} value={g.value} max={g.max} unit={g.unit} status="nominal" />
            </div>
          ))}
        </div>

        {/* Trend graphs row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {trends.map((trend, i) => (
            <div key={trend.label} className="panel bg-space-950/60 p-4 border-space-800/80">
              <div className="flex items-center gap-2 mb-2">
                {i === 0 && <TrendingUp className="w-3.5 h-3.5 text-tealx-400" />}
                {i === 1 && <Wind className="w-3.5 h-3.5 text-amberx-400" />}
                {i >= 2 && <Activity className="w-3.5 h-3.5 text-accent-400" />}
                <span className="text-[10px] font-mono font-semibold tracking-wider text-space-300 uppercase">{trend.label}</span>
              </div>
              <div className="flex items-end justify-between mb-2">
                <span className="text-xl font-mono font-bold text-white tracking-tight">
                  {trend.value}<span className="text-xs text-space-400 ml-1">{trend.unit}</span>
                </span>
                <span className="text-[10px] font-mono text-tealx-400">NOMINAL</span>
              </div>
              <MiniLineChart data={trend.data} color={trendColors[i % trendColors.length]} width={200} height={36} />
            </div>
          ))}
        </div>

        {/* Spacecraft Rack Environmental Matrix */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="panel bg-space-950/70 p-4 border-space-800/80">
            <div className="kpi-label mb-2">Environmental Stability</div>
            <div className="flex items-center justify-between">
              <span className="text-2xl font-mono font-bold text-tealx-400">
                {data ? `${Math.round(data.environmental_stability)}%` : '—'}
              </span>
              <StatusDot variant="success" pulse />
            </div>
            <div className="mt-2 text-[10px] font-mono text-space-400">
              Atmospheric & pressure delta ±0.01 kPa
            </div>
          </div>

          <div className="panel bg-space-950/70 p-4 border-space-800/80">
            <div className="kpi-label mb-2">Motion Disturbance Level</div>
            <div className="flex items-center justify-between">
              <span className="text-2xl font-mono font-bold text-white">
                {data?.motion_disturbance ?? '—'}
              </span>
              <StatusDot variant="success" pulse />
            </div>
            <div className="mt-2 text-[10px] font-mono text-space-400">
              Vibration isolation mounts engaged
            </div>
          </div>

          <div className="panel bg-space-950/70 p-4 border-space-800/80">
            <div className="kpi-label mb-2">Rack Biosphere Status</div>
            <div className="flex items-center justify-between">
              <span className="text-2xl font-mono font-bold text-accent-300">
                {data?.experiment_environment ?? '—'}
              </span>
              <StatusDot variant="success" pulse />
            </div>
            <div className="mt-2 text-[10px] font-mono text-space-400">
              Chamber temperature stable at 21.4°C
            </div>
          </div>
        </div>
      </Panel>
    </AppLayout>
  );
}

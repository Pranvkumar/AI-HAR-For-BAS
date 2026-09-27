import { useEffect, useState } from 'react';
import {
  Bell,
  User,
  Radio,
  Clock,
  WifiOff,
  Cpu,
  Zap,
} from 'lucide-react';
import { api } from '@/services/api';
import { useQuery } from '@/hooks/useApi';

interface TopHeaderProps {
  title?: string;
  subtitle?: string;
  experimentCode?: string | null;
  experimentTitle?: string | null;
}

const HEADER_POLL_MS = 5000;

function formatElapsed(startedAt: string | null): string {
  if (!startedAt) return 'T+ 00:00:00';
  const startMs = new Date(startedAt).getTime();
  if (Number.isNaN(startMs)) return 'T+ 00:00:00';

  const elapsed = Math.max(Date.now() - startMs, 0);
  const hours = Math.floor(elapsed / 3600000);
  const minutes = Math.floor((elapsed % 3600000) / 60000);
  const seconds = Math.floor((elapsed % 60000) / 1000);

  const pad = (n: number) => String(n).padStart(2, '0');
  return `T+ ${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

function useMissionTime(startedAt: string | null): string {
  const [time, setTime] = useState(() => formatElapsed(startedAt));

  useEffect(() => {
    setTime(formatElapsed(startedAt));
    if (!startedAt) return;

    const interval = setInterval(() => setTime(formatElapsed(startedAt)), 1000);
    return () => clearInterval(interval);
  }, [startedAt]);

  return time;
}

function useUtcClock(): string {
  const [utc, setUtc] = useState(() => new Date().toISOString().substring(11, 19));

  useEffect(() => {
    const timer = setInterval(() => {
      setUtc(new Date().toISOString().substring(11, 19));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return utc;
}

export default function TopHeader({
  title = 'Live Monitoring Deck',
  subtitle = 'Mission Operations Console',
  experimentCode = 'EXP-04',
  experimentTitle = 'In-Situ Bio-Crystallization & Fluid Agitation',
}: TopHeaderProps) {
  const { data: sessions } = useQuery(() => api.listSessions(), { intervalMs: HEADER_POLL_MS });
  const { data: status } = useQuery(() => api.getSystemStatus(), { intervalMs: HEADER_POLL_MS });
  const { data: alertSummary } = useQuery(() => api.getAlertSummary(), { intervalMs: HEADER_POLL_MS });

  const activeSession = sessions?.find((s) => s.status === 'IN_PROGRESS');
  const earliestStart = activeSession ? activeSession.started_at : sessions?.length ? sessions[0].started_at : null;
  const missionTime = useMissionTime(earliestStart);
  const utcTime = useUtcClock();

  const operational = status?.ai_engine_online && status?.database_connected;
  const alertCount = alertSummary?.active ?? 0;

  return (
    <header
      role="banner"
      className="h-14 shrink-0 bg-[#ede5dc] border-b border-[#ded2c5] flex items-center justify-between px-4 z-30 select-none font-mono"
    >
      {/* Left: System Identity & Protocol Identity */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded bg-[#964f19]/15 border border-[#964f19]/30 flex items-center justify-center">
            <Zap className="w-4 h-4 text-[#964f19]" />
          </div>
          <div>
            <div className="text-xs font-extrabold text-[#261912] tracking-widest uppercase font-mono flex items-center gap-1.5">
              <span>AEGIS-BAS</span>
              <span className="text-space-400">//</span>
              <span className="text-[#964f19]">MISSION OPERATIONS</span>
            </div>
            <div className="text-[10px] text-space-400 font-mono tracking-normal truncate flex items-center gap-1.5">
              <span className="text-[#166534] font-bold">[{experimentCode || 'EXP-04'}]</span>
              <span className="truncate max-w-[280px] sm:max-w-md text-[#261912]">
                {experimentTitle || 'In-Situ Bio-Crystallization'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Right: Operational Status, Offline Indicator, Clocks, Alerts, and Operator */}
      <div className="flex items-center gap-2.5">
        {/* Offline / Air-Gapped State */}
        <div
          title="Air-gapped local edge deployment with zero cloud egress"
          className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#ffffff] border border-[#ded2c5] text-[10px]"
        >
          <WifiOff className="w-3 h-3 text-[#166534]" />
          <span className="text-space-400">EDGE</span>
          <span className="text-[#166534] font-bold">AIR-GAPPED [127.0.0.1]</span>
        </div>

        {/* Model & FSM Status */}
        <div
          title="YOLO-HAR v4.2 Onboard Vision Engine + DO-178C Finite State Machine"
          className="hidden xl:flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#ffffff] border border-[#ded2c5] text-[10px]"
        >
          <Cpu className="w-3 h-3 text-[#964f19]" />
          <span className="text-space-400">HAR v4.2</span>
          <span className="text-space-400">|</span>
          <span className="text-[#964f19] font-bold">FSM ARMED</span>
        </div>

        {/* Real-time UTC Clock */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#ffffff] border border-[#ded2c5] text-[11px] tabular-nums">
          <Clock className="w-3 h-3 text-space-400" />
          <span className="text-[#261912] font-semibold">{utcTime}</span>
          <span className="text-[9px] text-space-400">UTC</span>
        </div>

        {/* Mission Elapsed Time (MET) */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#964f19]/10 border border-[#964f19]/30 text-[11px] tabular-nums">
          <Radio className="w-3 h-3 text-[#964f19]" />
          <span className="text-[10px] font-bold text-[#964f19] uppercase hidden md:inline">
            MET
          </span>
          <span className="font-bold text-[#261912] tracking-wider">
            {missionTime}
          </span>
        </div>

        {/* System Health Status Indicator */}
        <div
          title={operational ? 'All primary avionics operational' : 'Degraded subsystem health'}
          className="hidden sm:flex items-center gap-1.5 px-2 py-1 rounded bg-[#ffffff] border border-[#ded2c5] text-[10px]"
        >
          <span
            className={`status-dot ${
              operational ? 'bg-tealx-500' : 'bg-amberx-500'
            }`}
          />
          <span className="text-space-300 font-bold">
            {operational ? 'NOMINAL' : 'DEGRADED'}
          </span>
        </div>

        {/* Active Alert Notification Bell */}
        <button
          aria-label="Mission alerts indicator"
          className="relative p-1.5 rounded bg-[#ffffff] border border-[#ded2c5] hover:bg-[#ede2d6] text-space-400 hover:text-[#261912] transition-colors"
          title={`Active mission alerts: ${alertCount}`}
        >
          <Bell className="w-3.5 h-3.5" />
          {alertCount > 0 && (
            <span className="absolute -top-1 -right-1 px-1 rounded-full text-[9px] font-bold bg-redx-500 text-white font-mono">
              {alertCount}
            </span>
          )}
        </button>

        {/* Biometric-Authenticated Operator Badge */}
        <div
          title="Mission Bio-Astronaut Specialist CDR-01 (Biometrically Authenticated)"
          className="flex items-center gap-1.5 pl-1.5 pr-2 py-0.5 rounded bg-[#ffffff] border border-[#ded2c5]"
        >
          <div className="w-5 h-5 rounded bg-gradient-to-tr from-[#964f19] to-[#b45f23] flex items-center justify-center text-white text-[10px]">
            <User className="w-3 h-3" />
          </div>
          <span className="text-[10px] font-bold text-[#261912]">
            CDR-01
          </span>
        </div>
      </div>
    </header>
  );
}

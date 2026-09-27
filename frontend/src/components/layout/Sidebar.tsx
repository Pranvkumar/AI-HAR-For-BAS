import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Radio,
  FlaskConical,
  Globe,
  Bell,
  ScrollText,
  Activity,
  Camera,
  Bot,
  Satellite,
  Cpu,
} from 'lucide-react';
import { api } from '@/services/api';
import { useQuery } from '@/hooks/useApi';

const STATUS_POLL_MS = 5000;

const navItems = [
  { to: '/', label: 'Mission Overview', icon: LayoutDashboard, badge: null },
  { to: '/monitoring', label: 'Live Operations Deck', icon: Radio, badge: 'ACTIVE' },
  { to: '/experiments', label: 'Flight Protocols', icon: FlaskConical, badge: null },
  { to: '/microgravity', label: 'Microgravity Dynamics', icon: Globe, badge: null },
  { to: '/alerts', label: 'Anomalies & Events', icon: Bell, badge: null },
  { to: '/logs', label: 'Telemetry Logs', icon: ScrollText, badge: null },
];

export default function Sidebar() {
  const { data: status } = useQuery(() => api.getSystemStatus(), {
    intervalMs: STATUS_POLL_MS,
  });

  const systemStatus = [
    { label: 'Vision HAR Pipeline', active: Boolean(status?.ai_engine_online), icon: Activity },
    { label: 'Optical Hardware Sensor', active: Boolean(status?.camera_stream_active), icon: Camera },
    { label: 'Autonomous Voice Copilot', active: Boolean(status?.model_loaded), icon: Bot },
    { label: 'Offline Flight Mode', active: Boolean(status?.demo_mode), icon: Satellite },
  ];

  return (
    <aside className="w-60 shrink-0 bg-[#f3ebe2] border-r border-[#ded2c5] flex flex-col h-full z-20 select-none font-mono">
      {/* Brand Header */}
      <div className="px-4 py-3.5 border-b border-[#ded2c5] bg-[#ece2d6]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded bg-[#964f19]/15 border border-[#964f19]/30 flex items-center justify-center">
            <Satellite className="w-4 h-4 text-[#964f19]" />
          </div>
          <div>
            <div className="text-xs font-extrabold text-[#261912] tracking-widest font-mono">
              AEGIS AI-HAR
            </div>
            <div className="text-[9px] text-space-400 tracking-wider uppercase flex items-center gap-1.5">
              <span>AVIONICS OPS</span>
              <span className="text-[#166534] font-bold">• v2.4</span>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-2.5 py-3 space-y-1 overflow-y-auto">
        <div className="px-2 py-1 text-[9px] font-bold tracking-[0.16em] text-space-400 uppercase font-mono">
          Flight Operations Navigation
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `nav-item ${isActive ? 'nav-item-active' : ''}`
              }
            >
              <Icon className="w-3.5 h-3.5 shrink-0" />
              <span className="flex-1 truncate text-[11px]">{item.label}</span>
              {item.badge && (
                <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-[#166534]/15 text-[#166534] border border-[#166534]/30">
                  {item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Subsystem Readiness Matrix */}
      <div className="p-3 border-t border-[#ded2c5] bg-[#ece2d6]">
        <div className="flex items-center justify-between mb-2 px-0.5">
          <span className="text-[9px] font-bold tracking-[0.14em] text-space-400 uppercase font-mono flex items-center gap-1">
            <Cpu className="w-3 h-3 text-[#964f19]" />
            Core Engines
          </span>
          <span className="text-[9px] font-mono text-[#166534] px-1 py-0.2 rounded bg-[#166534]/10 border border-[#166534]/20 font-bold">
            NOMINAL
          </span>
        </div>

        <div className="space-y-1.5">
          {systemStatus.map((s) => {
            const Icon = s.icon;
            return (
              <div
                key={s.label}
                className="flex items-center justify-between px-2 py-1 rounded bg-[#ffffff] border border-[#ded2c5] text-[10px]"
              >
                <div className="flex items-center gap-1.5 min-w-0">
                  <Icon className="w-3 h-3 text-space-400 shrink-0" />
                  <span className="text-[#261912] font-medium truncate">{s.label}</span>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <span
                    className={`status-dot ${
                      s.active ? 'bg-tealx-500' : 'bg-space-600'
                    }`}
                  />
                  <span className="text-[9px] font-mono text-space-400">
                    {s.active ? 'ARM' : 'OFF'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}

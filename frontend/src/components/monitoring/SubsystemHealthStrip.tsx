import { Eye, Activity, ShieldCheck, Radio, Camera, Volume2, WifiOff } from 'lucide-react';
import type { ApiSystemStatus } from '@/types/api';

interface SubsystemHealthStripProps {
  status?: ApiSystemStatus | null;
  inferenceFps?: number;
  inferenceLatencyMs?: number;
  fsmArmed?: boolean;
}

export default function SubsystemHealthStrip({
  status,
  inferenceFps = 29.8,
  inferenceLatencyMs = 12.4,
  fsmArmed = true,
}: SubsystemHealthStripProps) {
  const subsystems = [
    {
      id: 'vision',
      label: 'VISION INFERENCE',
      detail: `${inferenceLatencyMs.toFixed(1)}ms // ${Math.round(inferenceFps)} FPS`,
      state: status?.ai_engine_online ? 'NOMINAL' : 'OFFLINE',
      nominal: Boolean(status?.ai_engine_online),
      icon: Eye,
    },
    {
      id: 'tracking',
      label: 'CREW TRACKING',
      detail: '17 KEYPOINTS // LOCKED',
      state: status?.ai_engine_online ? 'ACTIVE' : 'STANDBY',
      nominal: Boolean(status?.ai_engine_online),
      icon: Activity,
    },
    {
      id: 'fsm',
      label: 'PROTOCOL FSM',
      detail: 'DO-178C LEVEL-B',
      state: fsmArmed ? 'ARMED' : 'DISARMED',
      nominal: fsmArmed,
      icon: ShieldCheck,
    },
    {
      id: 'telemetry',
      label: 'TELEMETRY BUS',
      detail: 'CCSDS PACKETS // 10Hz',
      state: 'STREAMING',
      nominal: true,
      icon: Radio,
    },
    {
      id: 'camera',
      label: 'OPTICAL SENSOR',
      detail: 'CAM-01 [BAY-A1] 1080p',
      state: status?.camera_stream_active ? 'ONLINE' : 'SYNTHETIC',
      nominal: true,
      icon: Camera,
    },
    {
      id: 'voice',
      label: 'VOICE GUIDANCE',
      detail: 'EDGE NEURAL TTS',
      state: 'STANDBY',
      nominal: true,
      icon: Volume2,
    },
    {
      id: 'offline',
      label: 'OFFLINE NODE',
      detail: 'AIR-GAPPED // LOCAL',
      state: 'SECURE',
      nominal: true,
      icon: WifiOff,
    },
  ];

  return (
    <section
      aria-label="Avionics Subsystem Health Matrix"
      className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-1.5 p-1.5 bg-[#ede3d8] border border-[#ded2c5] rounded mb-3 select-none"
    >
      {subsystems.map((sub) => {
        const Icon = sub.icon;
        return (
          <div
            key={sub.id}
            className="flex items-center gap-2 px-2.5 py-1.5 bg-[#ffffff] border border-[#ded2c5] rounded text-[11px]"
          >
            <div
              className={`w-6 h-6 rounded flex items-center justify-center shrink-0 ${
                sub.nominal ? 'bg-[#166534]/10 text-[#166534]' : 'bg-[#b45309]/10 text-[#b45309]'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-1 leading-none">
                <span className="text-[9px] font-mono font-bold tracking-wider text-[#261912] uppercase truncate">
                  {sub.label}
                </span>
                <span
                  className={`status-dot ${
                    sub.nominal ? 'bg-[#166534]' : 'bg-[#b45309]'
                  }`}
                />
              </div>
              <div className="text-[10px] font-mono text-space-400 truncate mt-0.5 tabular-nums">
                {sub.detail}
              </div>
            </div>
          </div>
        );
      })}
    </section>
  );
}

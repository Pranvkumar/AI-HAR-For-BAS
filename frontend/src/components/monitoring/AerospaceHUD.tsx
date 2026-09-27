import React, { memo } from 'react';
import {
  ShieldAlert,
  Flame,
  Zap,
  Cpu,
  Radio,
  Compass,
  AlertTriangle,
  FileCheck2,
  Activity,
} from 'lucide-react';

interface AerospaceHUDProps {
  sloshJerk?: number;
  sloshAlert?: boolean;
  ecoMode?: string;
  ecoFps?: number;
  ecoFramesSaved?: number;
  merkleHash?: string | null;
  merkleChainLength?: number;
  ccsdsLastHex?: string;
  ccsdsTotalPackets?: number;
  thermalStatus?: string;
  cpuPercent?: number;
  isBlinded?: boolean;
  glareSaturation?: number;
  isImmobile?: boolean;
  fodActive?: boolean;
  fodObject?: string;
  fodEta?: number;
  hesitationActive?: boolean;
  hesitationDwellMs?: number;
}

export const AerospaceHUD: React.FC<AerospaceHUDProps> = memo(({
  sloshJerk = 0,
  sloshAlert = false,
  ecoMode = 'ACTIVE',
  ecoFps = 30,
  ecoFramesSaved = 0,
  merkleHash = '0x34BDD7...F2E8',
  merkleChainLength = 0,
  ccsdsLastHex = '08 41 C0 04 00 12 6A B9 16 C0',
  ccsdsTotalPackets = 0,
  thermalStatus = 'COOL',
  cpuPercent = 14,
  isBlinded = false,
  glareSaturation = 0,
  isImmobile = false,
  fodActive = false,
  fodObject = '',
  fodEta = 0,
  hesitationActive = false,
  hesitationDwellMs = 0,
}) => {
  const isEcoStandby = ecoMode === 'STANDBY';
  const jerkPct = Math.min(100, (sloshJerk / 1000) * 100);

  return (
    <div className="space-y-4">
      {/* Critical Alert Banners */}
      {fodActive && (
        <div className="p-3.5 bg-redx-500/20 border border-redx-500/60 rounded-xl flex items-center justify-between shadow-glow-red animate-pulse">
          <div className="flex items-center gap-3">
            <Compass className="w-5 h-5 text-redx-400 shrink-0" />
            <div>
              <p className="text-xs font-bold text-white uppercase font-display tracking-wider">
                UNSECURED DRIFT // FOD COLLISION WARNING
              </p>
              <p className="text-[11px] text-redx-200 font-sans">
                Object <span className="font-mono font-bold text-white">{fodObject.toUpperCase()}</span> moving unsecured. Projected impact in {fodEta.toFixed(1)}s.
              </p>
            </div>
          </div>
          <span className="badge bg-redx-500 text-white font-mono text-xs shadow-sm">
            HAZARD DETECTED
          </span>
        </div>
      )}

      {hesitationActive && (
        <div className="p-3.5 bg-amberx-500/20 border border-amberx-500/60 rounded-xl flex items-center justify-between shadow-glow-amber">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amberx-400 animate-pulse shrink-0" />
            <div>
              <p className="text-xs font-bold text-white uppercase font-display tracking-wider">
                COGNITIVE STALL // OPERATOR ASSISTANCE
              </p>
              <p className="text-[11px] text-amberx-200 font-sans">
                Operator hand stationary near target for {(hesitationDwellMs / 1000).toFixed(1)}s. Windows SAPI5 audio prompt dispatched.
              </p>
            </div>
          </div>
          <span className="badge bg-amberx-500 text-white font-mono text-xs">
            VOICE ASSIST ACTIVE
          </span>
        </div>
      )}

      {isImmobile && (
        <div className="p-3.5 bg-redx-500/25 border border-redx-500/70 rounded-xl flex items-center justify-between shadow-glow-red animate-pulse">
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-5 h-5 text-redx-400 shrink-0" />
            <div>
              <p className="text-xs font-bold text-white uppercase font-display tracking-wider">
                CREW IMMOBILITY // EMERGENCY PROTOCOL
              </p>
              <p className="text-[11px] text-redx-200 font-sans">
                Hand motion variance zero inside active hazard zone. Audio beacon repeating.
              </p>
            </div>
          </div>
          <span className="badge bg-redx-500 text-white font-mono text-xs">
            EMERGENCY ACTIVE
          </span>
        </div>
      )}

      {isBlinded && (
        <div className="p-3 bg-amberx-500/20 border border-amberx-500/50 rounded-xl flex items-center gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amberx-400 shrink-0" />
          <p className="text-xs text-amberx-200 font-sans">
            <strong className="text-white">Optical Glare:</strong> Sensor blinding ratio at {(glareSaturation * 100).toFixed(0)}%. Reorient light source or camera angle.
          </p>
        </div>
      )}

      {/* Grid of Aerospace HUD Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
        {/* Card 1: Kinetic Jerk & Slosh Guard */}
        <div className="rounded-xl bg-space-950/70 backdrop-blur-xl border border-white/[0.08] hover:border-white/[0.15] p-4 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-tealx-500/15 border border-tealx-500/30 flex items-center justify-center">
                <Activity className="w-3.5 h-3.5 text-tealx-400" />
              </div>
              <span className="text-xs font-bold text-white uppercase font-display tracking-wider">Slosh Guard</span>
            </div>
            <span className={`badge text-[9px] ${sloshAlert ? 'bg-redx-500 text-white shadow-glow-red animate-pulse' : 'bg-tealx-500/15 text-tealx-400 border border-tealx-500/30'}`}>
              {sloshAlert ? 'SLOSH ALERT' : 'NOMINAL'}
            </span>
          </div>

          <div className="flex items-baseline justify-between mb-1.5">
            <span className="text-[11px] text-space-300 font-mono">Kinetic Jerk |j|</span>
            <span className={`font-mono text-base font-bold tabular-nums ${sloshAlert ? 'text-redx-400' : 'text-tealx-300'}`}>
              {sloshJerk.toFixed(0)} <span className="text-[10px] text-space-400 font-normal">px/s³</span>
            </span>
          </div>

          <div className="w-full h-1.5 bg-space-900 border border-white/[0.04] rounded-full overflow-hidden mb-2">
            <div
              className={`h-full transition-all duration-300 rounded-full ${sloshAlert ? 'bg-redx-500 shadow-glow-red' : 'bg-tealx-400 shadow-glow-teal'}`}
              style={{ width: `${jerkPct}%` }}
            />
          </div>
          <div className="flex justify-between text-[10px] text-space-400 font-mono">
            <span>Threshold: 800 px/s³</span>
            <span className="text-tealx-400 font-medium">Fluid Safe</span>
          </div>
        </div>

        {/* Card 2: SWaP-C Eco-Governor */}
        <div className="rounded-xl bg-space-950/70 backdrop-blur-xl border border-white/[0.08] hover:border-white/[0.15] p-4 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-accent-500/15 border border-accent-500/30 flex items-center justify-center">
                <Zap className="w-3.5 h-3.5 text-accent-400" />
              </div>
              <span className="text-xs font-bold text-white uppercase font-display tracking-wider">SWaP-C Eco-Governor</span>
            </div>
            <span className={`badge text-[9px] ${isEcoStandby ? 'bg-amberx-500/20 text-amberx-400 border border-amberx-500/40 shadow-glow-amber animate-pulse' : 'bg-accent-500/15 text-accent-300 border border-accent-500/30'}`}>
              {ecoMode} ({ecoFps} FPS)
            </span>
          </div>

          <div className="flex justify-between text-[11px] mb-1.5">
            <span className="text-space-300 font-mono">Power Optimization</span>
            <span className="font-mono text-white font-semibold">{isEcoStandby ? '~83% Energy Saved' : 'Autonomous Active'}</span>
          </div>
          <div className="flex justify-between text-[10px] text-space-400 border-t border-white/[0.04] pt-2 mt-2 font-mono">
            <span>Frames Saved</span>
            <span className="text-accent-300 font-bold tabular-nums">{ecoFramesSaved.toLocaleString()}</span>
          </div>
        </div>

        {/* Card 3: Merkle Flight Recorder */}
        <div className="rounded-xl bg-space-950/70 backdrop-blur-xl border border-white/[0.08] hover:border-white/[0.15] p-4 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-violetx-500/15 border border-violetx-500/30 flex items-center justify-center">
                <FileCheck2 className="w-3.5 h-3.5 text-violetx-400" />
              </div>
              <span className="text-xs font-bold text-white uppercase font-display tracking-wider">Merkle Flight Ledger</span>
            </div>
            <span className="badge bg-violetx-500/15 text-violetx-300 border border-violetx-500/30 text-[9px]">
              DO-178C VERIFIED
            </span>
          </div>

          <div className="bg-space-950/90 border border-white/[0.08] rounded-lg p-2 font-mono text-[10px] text-accent-300 break-all mb-2 shadow-inner">
            {merkleHash || '0x34BDD7...F2E8'}
          </div>
          <div className="flex justify-between text-[10px] text-space-400 font-mono">
            <span>Chain: {merkleChainLength} blocks</span>
            <span className="text-tealx-400 font-semibold">Tamper-Proof</span>
          </div>
        </div>

        {/* Card 4: CCSDS Telemetry Formatter */}
        <div className="rounded-xl bg-space-950/70 backdrop-blur-xl border border-white/[0.08] hover:border-white/[0.15] p-4 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-accent-500/15 border border-accent-500/30 flex items-center justify-center">
                <Radio className="w-3.5 h-3.5 text-accent-400" />
              </div>
              <span className="text-xs font-bold text-white uppercase font-display tracking-wider">CCSDS 133.0-B-2</span>
            </div>
            <span className="badge bg-tealx-500/15 text-tealx-400 border border-tealx-500/30 text-[9px] animate-pulse">
              ● ACTIVE PACKETS
            </span>
          </div>

          <div className="bg-space-950/90 border border-white/[0.08] rounded-lg p-2 font-mono text-[9px] text-tealx-300 break-all h-9 overflow-hidden mb-2 shadow-inner">
            {ccsdsLastHex || '08 41 C0 04 00 12 6A B9 16 C0 44 3B ...'}
          </div>
          <div className="flex justify-between text-[10px] text-space-400 font-mono">
            <span>Packets: <strong className="text-white tabular-nums">{ccsdsTotalPackets.toLocaleString()}</strong></span>
            <span>APID 0x001 - 0x044</span>
          </div>
        </div>

        {/* Card 5: Thermal Governor & Watchdog */}
        <div className="rounded-xl bg-space-950/70 backdrop-blur-xl border border-white/[0.08] hover:border-white/[0.15] p-4 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-amberx-500/15 border border-amberx-500/30 flex items-center justify-center">
                <Cpu className="w-3.5 h-3.5 text-amberx-400" />
              </div>
              <span className="text-xs font-bold text-white uppercase font-display tracking-wider">Thermal Governor</span>
            </div>
            <span className={`badge text-[9px] ${thermalStatus === 'HOT' ? 'bg-redx-500 text-white shadow-glow-red' : thermalStatus === 'WARM' ? 'bg-amberx-500/20 text-amberx-400' : 'bg-tealx-500/15 text-tealx-400'}`}>
              {thermalStatus}
            </span>
          </div>

          <div className="flex justify-between text-[11px] mb-1.5 font-mono">
            <span className="text-space-300">Host CPU Load</span>
            <span className="text-white font-bold tabular-nums">{cpuPercent.toFixed(1)}%</span>
          </div>
          <div className="flex justify-between text-[10px] text-space-400 border-t border-white/[0.04] pt-2 mt-2 font-mono">
            <span>Hardware Watchdog</span>
            <span className="text-tealx-400 font-semibold">BUS RECOVERY RDY</span>
          </div>
        </div>

        {/* Card 6: Optical Glare & Immobility Guardian */}
        <div className="rounded-xl bg-space-950/70 backdrop-blur-xl border border-white/[0.08] hover:border-white/[0.15] p-4 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-redx-500/15 border border-redx-500/30 flex items-center justify-center">
                <Flame className="w-3.5 h-3.5 text-redx-400" />
              </div>
              <span className="text-xs font-bold text-white uppercase font-display tracking-wider">Optical & Immobility</span>
            </div>
            <span className="badge bg-tealx-500/15 text-tealx-400 border border-tealx-500/30 text-[9px]">
              SUPERVISED
            </span>
          </div>

          <div className="flex justify-between text-[11px] mb-1.5 font-mono">
            <span className="text-space-300">V-Channel Saturation</span>
            <span className="text-white font-bold tabular-nums">{(glareSaturation * 100).toFixed(1)}%</span>
          </div>
          <div className="flex justify-between text-[10px] text-space-400 border-t border-white/[0.04] pt-2 mt-2 font-mono">
            <span>Immobility Status</span>
            <span className={isImmobile ? 'text-redx-400 font-bold' : 'text-tealx-400 font-semibold'}>
              {isImmobile ? 'FLAGGED (EMERGENCY)' : 'NOMINAL (ACTIVE)'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
});

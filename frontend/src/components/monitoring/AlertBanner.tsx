import { AlertTriangle, ShieldAlert, CheckCircle2, Volume2, Check } from 'lucide-react';
import type { AlertSeverityApi } from '@/types/api';

interface AlertBannerProps {
  alert?: { id: number; severity: AlertSeverityApi; message: string } | null;
  isImmobile?: boolean;
  isBlinded?: boolean;
  sloshAlert?: boolean;
  fodActive?: boolean;
  fodObject?: string;
  hesitationActive?: boolean;
  isViolation?: boolean;
  onAcknowledge?: () => void;
  onDispatchVoice?: () => void;
}

export default function AlertBanner({
  alert,
  isImmobile,
  isBlinded,
  sloshAlert,
  fodActive,
  fodObject,
  hesitationActive,
  isViolation,
  onAcknowledge,
  onDispatchVoice,
}: AlertBannerProps) {
  const hasAnomaly =
    Boolean(alert) ||
    isImmobile ||
    isBlinded ||
    sloshAlert ||
    fodActive ||
    hesitationActive ||
    isViolation;

  if (!hasAnomaly) {
    return (
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#f0fdf4] border border-[#bbf7d0] rounded mb-3 text-[11px] font-mono text-[#166534]">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-3.5 h-3.5 text-[#166534] shrink-0" />
          <span className="text-[#166534] font-bold">ALL FLIGHT SAFETY BOUNDARIES NOMINAL</span>
          <span className="text-[#86efac]">|</span>
          <span className="text-[#14532d]">Zero Active Deviations or Anomalies</span>
        </div>
        <span className="text-[10px] text-[#166534] font-bold">NORMAL OPS</span>
      </div>
    );
  }

  let title = 'MISSION SAFETY DEVIATION';
  let detail = alert?.message ?? 'Anomaly condition triggered in experiment environment.';
  let isCritical = alert?.severity === 'CRITICAL' || isImmobile || isViolation || fodActive;

  if (isImmobile) {
    title = 'CRITICAL // CREW IMMOBILITY DETECTED';
    detail = 'Astronaut motion halted for >15s during active protocol. Verify crew responsiveness.';
    isCritical = true;
  } else if (isViolation) {
    title = 'CRITICAL // PROTOCOL SEQUENCE VIOLATION';
    detail = 'Detected action violates approved scientific procedure sequence order. Realign astronaut immediately.';
    isCritical = true;
  } else if (fodActive) {
    title = 'COLLISION HAZARD // UNSECURED FLOATING OBJECT';
    detail = `Unsecured drift trajectory detected (${fodObject ?? 'OBJECT'}). Potential workspace collision.`;
    isCritical = true;
  } else if (isBlinded) {
    title = 'SENSOR DEGRADATION // OPTICAL GLARE';
    detail = 'High sensor saturation / glare blocking primary optical camera. Adjust workspace illumination.';
    isCritical = false;
  } else if (sloshAlert) {
    title = 'SAFETY CAUTION // KINETIC JERK EXCEEDED';
    detail = 'Rapid acceleration spike detected. High risk of fluid slosh or containment breach.';
    isCritical = false;
  } else if (hesitationActive) {
    title = 'COGNITIVE STALL // OPERATOR HESITATION';
    detail = 'Extended dwell time without manipulation. Astronaut may require procedure clarification.';
    isCritical = false;
  }

  return (
    <div
      role="alert"
      className={`p-2.5 rounded border mb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
        isCritical
          ? 'bg-[#fef2f2] border-[#fecaca] text-[#b91c1c]'
          : 'bg-[#fffbeb] border-[#fed7aa] text-[#b45309]'
      }`}
    >
      <div className="flex items-start gap-2.5">
        <div className="mt-0.5">
          {isCritical ? (
            <ShieldAlert className="w-5 h-5 text-[#b91c1c] shrink-0" />
          ) : (
            <AlertTriangle className="w-5 h-5 text-[#b45309] shrink-0" />
          )}
        </div>
        <div>
          <div className="text-xs font-mono font-bold tracking-wider flex items-center gap-2">
            <span className={isCritical ? 'text-[#b91c1c]' : 'text-[#b45309]'}>
              {title}
            </span>
          </div>
          <div className="text-[11px] font-mono mt-0.5 leading-tight text-[#261912]">
            {detail}
          </div>
        </div>
      </div>

      {/* Operator Actions */}
      <div className="flex items-center gap-2 shrink-0">
        {onDispatchVoice && (
          <button
            onClick={onDispatchVoice}
            className="btn-secondary text-[10px] py-1 px-2.5 flex items-center gap-1"
            title="Dispatch synthesized speech instruction to astronaut headset"
          >
            <Volume2 className="w-3 h-3 text-[#964f19]" />
            VOICE OVERRIDE
          </button>
        )}
        {onAcknowledge && (
          <button
            onClick={onAcknowledge}
            className={`btn-primary text-[10px] py-1 px-3 flex items-center gap-1 ${
              isCritical
                ? 'bg-[#b91c1c] hover:bg-[#991b1b] border-[#7f1d1d]'
                : 'bg-[#b45309] hover:bg-[#92400e] border-[#78350f]'
            }`}
          >
            <Check className="w-3 h-3" />
            ACKNOWLEDGE
          </button>
        )}
      </div>
    </div>
  );
}

interface GaugeProps {
  label: string;
  value: number;
  max: number;
  unit: string;
  status?: 'nominal' | 'warning' | 'critical';
}

export default function Gauge({ label, value, max, unit, status = 'nominal' }: GaugeProps) {
  const pct = Math.min(100, (value / max) * 100);
  const radius = 40;
  const circumference = Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;

  const color =
    status === 'critical' ? '#ef4444' :
    status === 'warning' ? '#f59e0b' :
    '#14b8a6';

  return (
    <div className="flex flex-col items-center">
      <svg width="100" height="60" viewBox="0 0 100 60">
        <path
          d={`M 10 50 A ${radius} ${radius} 0 0 1 90 50`}
          fill="none"
          stroke="#1e3559"
          strokeWidth="6"
          strokeLinecap="round"
        />
        <path
          d={`M 10 50 A ${radius} ${radius} 0 0 1 90 50`}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
      </svg>
      <div className="text-lg font-mono font-bold text-white -mt-2">{value}<span className="text-xs text-space-300 ml-1">{unit}</span></div>
      <div className="text-[10px] text-space-400 tracking-wider uppercase mt-0.5">{label}</div>
    </div>
  );
}

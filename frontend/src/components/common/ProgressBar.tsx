interface ProgressBarProps {
  value: number;
  max?: number;
  variant?: 'accent' | 'success' | 'warning' | 'violet';
  showLabel?: boolean;
  height?: string;
}

export default function ProgressBar({
  value,
  max = 100,
  variant = 'accent',
  showLabel = false,
  height = 'h-2',
}: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));

  const barGradient =
    variant === 'success'
      ? 'from-tealx-500 to-tealx-400 shadow-[0_0_12px_rgba(20,184,166,0.6)]'
      : variant === 'warning'
      ? 'from-amberx-500 to-amberx-400 shadow-[0_0_12px_rgba(245,158,11,0.6)]'
      : variant === 'violet'
      ? 'from-violetx-500 to-violetx-400 shadow-[0_0_12px_rgba(139,92,246,0.6)]'
      : 'from-accent-600 to-accent-400 shadow-[0_0_12px_rgba(14,165,233,0.6)]';

  return (
    <div className="w-full">
      {showLabel && (
        <div className="flex items-center justify-between mb-1.5 font-mono">
          <span className="text-[10px] tracking-wider uppercase text-space-300">Procedure Progress</span>
          <span className="text-xs font-semibold text-white">{Math.round(pct)}%</span>
        </div>
      )}
      <div className={`w-full ${height} bg-space-950/80 border border-white/[0.06] rounded-full overflow-hidden p-0.5`}>
        <div
          className={`h-full bg-gradient-to-r ${barGradient} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

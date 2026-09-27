import type { ReactNode } from 'react';

interface KpiCardProps {
  label: string;
  value: string | number;
  icon?: ReactNode;
  variant?: 'default' | 'accent' | 'success' | 'warning' | 'violet';
  subtitle?: string;
  trend?: string;
}

const variantStyles: Record<
  string,
  {
    border: string;
    glow: string;
    iconBg: string;
    iconColor: string;
    valueColor: string;
  }
> = {
  default: {
    border: 'border-white/[0.08] hover:border-white/[0.18]',
    glow: 'hover:shadow-[0_0_20px_-5px_rgba(255,255,255,0.1)]',
    iconBg: 'bg-space-800/80 border-white/[0.08]',
    iconColor: 'text-space-300',
    valueColor: 'text-white',
  },
  accent: {
    border: 'border-accent-500/25 hover:border-accent-400/50',
    glow: 'hover:shadow-glow-accent',
    iconBg: 'bg-accent-500/15 border-accent-400/30',
    iconColor: 'text-accent-400',
    valueColor: 'text-white',
  },
  success: {
    border: 'border-tealx-500/25 hover:border-tealx-400/50',
    glow: 'hover:shadow-glow-teal',
    iconBg: 'bg-tealx-500/15 border-tealx-400/30',
    iconColor: 'text-tealx-400',
    valueColor: 'text-white',
  },
  warning: {
    border: 'border-amberx-500/25 hover:border-amberx-400/50',
    glow: 'hover:shadow-glow-amber',
    iconBg: 'bg-amberx-500/15 border-amberx-400/30',
    iconColor: 'text-amberx-400',
    valueColor: 'text-white',
  },
  violet: {
    border: 'border-violetx-500/25 hover:border-violetx-400/50',
    glow: 'hover:shadow-[0_0_20px_-3px_rgba(139,92,246,0.35)]',
    iconBg: 'bg-violetx-500/15 border-violetx-400/30',
    iconColor: 'text-violetx-400',
    valueColor: 'text-white',
  },
};

export default function KpiCard({
  label,
  value,
  icon,
  variant = 'default',
  subtitle,
  trend,
}: KpiCardProps) {
  const s = variantStyles[variant] || variantStyles.default;

  return (
    <div
      className={`relative overflow-hidden rounded-xl bg-gradient-to-b from-space-900/80 to-space-950/80 backdrop-blur-xl border ${s.border} ${s.glow} p-5 transition-all duration-200 group`}
    >
      {/* Subtle ambient light dot in top corner */}
      <div className="absolute top-0 right-0 w-24 h-24 bg-white/[0.02] rounded-full blur-xl pointer-events-none" />

      <div className="flex items-start justify-between mb-3.5">
        <span className="kpi-label">{label}</span>
        {icon && (
          <div
            className={`w-8 h-8 rounded-lg flex items-center justify-center border ${s.iconBg} ${s.iconColor} transition-transform group-hover:scale-105`}
          >
            {icon}
          </div>
        )}
      </div>

      <div className="flex items-baseline justify-between gap-2">
        <div className={`text-2xl font-bold font-mono tracking-tight ${s.valueColor}`}>
          {value}
        </div>
        {trend && (
          <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-tealx-500/10 text-tealx-400 border border-tealx-500/20">
            {trend}
          </span>
        )}
      </div>

      {subtitle && (
        <p className="text-[11px] text-space-400 mt-1 font-mono truncate">
          {subtitle}
        </p>
      )}
    </div>
  );
}

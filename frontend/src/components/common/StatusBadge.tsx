import type { ReactNode } from 'react';

interface StatusBadgeProps {
  status?: string;
  variant?: 'success' | 'warning' | 'critical' | 'info' | 'neutral' | 'violet';
  children?: ReactNode;
  pulse?: boolean;
}

const variantStyles: Record<string, { bg: string; dot: string; glow: string }> = {
  success: {
    bg: 'bg-tealx-500/15 text-tealx-400 border-tealx-500/35',
    dot: 'bg-tealx-400',
    glow: 'shadow-[0_0_8px_rgba(20,184,166,0.5)]',
  },
  warning: {
    bg: 'bg-amberx-500/15 text-amberx-400 border-amberx-500/35',
    dot: 'bg-amberx-400',
    glow: 'shadow-[0_0_8px_rgba(245,158,11,0.5)]',
  },
  critical: {
    bg: 'bg-redx-500/15 text-redx-400 border-redx-500/35',
    dot: 'bg-redx-500',
    glow: 'shadow-[0_0_10px_rgba(239,68,68,0.7)]',
  },
  info: {
    bg: 'bg-accent-500/15 text-accent-400 border-accent-500/35',
    dot: 'bg-accent-400',
    glow: 'shadow-[0_0_8px_rgba(14,165,233,0.5)]',
  },
  violet: {
    bg: 'bg-violetx-500/15 text-violetx-300 border-violetx-500/35',
    dot: 'bg-violetx-400',
    glow: 'shadow-[0_0_8px_rgba(139,92,246,0.5)]',
  },
  neutral: {
    bg: 'bg-space-800/80 text-space-300 border-white/[0.08]',
    dot: 'bg-space-400',
    glow: '',
  },
};

export default function StatusBadge({
  status,
  variant = 'neutral',
  children,
  pulse = true,
}: StatusBadgeProps) {
  const s = variantStyles[variant] || variantStyles.neutral;

  return (
    <span className={`badge ${s.bg} border backdrop-blur-sm`}>
      <span
        className={`status-dot ${s.dot} ${s.glow} ${
          pulse && variant !== 'neutral' ? 'animate-pulse' : ''
        }`}
      />
      {children ?? status}
    </span>
  );
}

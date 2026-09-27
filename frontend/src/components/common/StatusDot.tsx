interface StatusDotProps {
  variant?: 'success' | 'warning' | 'critical' | 'info' | 'neutral';
  pulse?: boolean;
}

const dotColors: Record<string, string> = {
  success: 'bg-tealx-500',
  warning: 'bg-amberx-500',
  critical: 'bg-redx-500',
  info: 'bg-accent-400',
  neutral: 'bg-space-300',
};

export default function StatusDot({ variant = 'neutral', pulse = false }: StatusDotProps) {
  return (
    <span
      className={`status-dot ${dotColors[variant]} ${pulse ? 'animate-pulse-slow' : ''}`}
    />
  );
}

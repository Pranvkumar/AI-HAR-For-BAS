import type { ReactNode } from 'react';

interface PanelProps {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  hudCorners?: boolean;
}

export default function Panel({
  title,
  subtitle,
  action,
  children,
  className = '',
  hudCorners = false,
}: PanelProps) {
  return (
    <div className={`relative panel ${className}`}>
      {hudCorners && (
        <>
          <span className="hud-corner-tl" />
          <span className="hud-corner-tr" />
          <span className="hud-corner-bl" />
          <span className="hud-corner-br" />
        </>
      )}

      {title && (
        <div className="panel-header">
          <div>
            <span className="panel-title">{title}</span>
            {subtitle && (
              <span className="block text-[10px] text-space-400 font-mono tracking-normal normal-case mt-0.5">
                {subtitle}
              </span>
            )}
          </div>
          {action && <div className="flex items-center gap-2">{action}</div>}
        </div>
      )}
      <div className="p-4 sm:p-5">{children}</div>
    </div>
  );
}

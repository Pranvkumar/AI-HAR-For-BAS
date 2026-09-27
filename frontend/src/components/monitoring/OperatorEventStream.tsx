import { useState, useRef, useEffect } from 'react';
import { Terminal, ShieldAlert, AlertTriangle, CheckCircle2, Pause, Play, Trash2, Filter } from 'lucide-react';

export interface OperatorEvent {
  id: string;
  timestamp: string;
  category: 'FSM' | 'VISION' | 'SAFETY' | 'ANOMALY' | 'CREW' | 'TELEMETRY';
  severity: 'NOMINAL' | 'WARNING' | 'CRITICAL' | 'INFO';
  message: string;
  meta?: string;
}

interface OperatorEventStreamProps {
  events: OperatorEvent[];
  onClear?: () => void;
}

export default function OperatorEventStream({ events, onClear }: OperatorEventStreamProps) {
  const [filter, setFilter] = useState<'ALL' | 'ANOMALIES' | 'FSM' | 'VISION'>('ALL');
  const [isPaused, setIsPaused] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isPaused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events, isPaused]);

  const filteredEvents = events.filter((ev) => {
    if (filter === 'ALL') return true;
    if (filter === 'ANOMALIES') return ev.severity === 'WARNING' || ev.severity === 'CRITICAL' || ev.category === 'ANOMALY';
    if (filter === 'FSM') return ev.category === 'FSM';
    if (filter === 'VISION') return ev.category === 'VISION' || ev.category === 'CREW';
    return true;
  });

  const getCategoryColor = (cat: OperatorEvent['category']) => {
    switch (cat) {
      case 'FSM':
        return 'text-[#166534] bg-[#f0fdf4] border-[#bbf7d0]';
      case 'VISION':
        return 'text-[#964f19] bg-[#faefe6] border-[#fed7aa]';
      case 'SAFETY':
      case 'ANOMALY':
        return 'text-[#b91c1c] bg-[#fef2f2] border-[#fecaca]';
      case 'CREW':
        return 'text-[#582f0e] bg-[#f5ede5] border-[#dfd2c4]';
      default:
        return 'text-space-300 bg-[#ede3d8] border-[#ded2c5]';
    }
  };

  const getSeverityIcon = (sev: OperatorEvent['severity']) => {
    switch (sev) {
      case 'CRITICAL':
        return <ShieldAlert className="w-3.5 h-3.5 text-[#b91c1c] shrink-0" />;
      case 'WARNING':
        return <AlertTriangle className="w-3.5 h-3.5 text-[#b45309] shrink-0" />;
      case 'NOMINAL':
        return <CheckCircle2 className="w-3.5 h-3.5 text-[#166534] shrink-0" />;
      default:
        return <span className="w-1.5 h-1.5 rounded-full bg-space-400 shrink-0" />;
    }
  };

  return (
    <div className="panel p-3 flex flex-col h-[320px]">
      {/* Header with Controls */}
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-[#ded2c5] shrink-0">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-[#964f19]" />
          <span className="text-[11px] font-mono font-bold tracking-[0.14em] text-[#261912] uppercase">
            Real-Time Mission Event Stream
          </span>
          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-[#ede3d8] border border-[#d8cbbe] text-[#261912] tabular-nums font-bold">
            {events.length} EVENTS
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Pause / Resume scroll */}
          <button
            onClick={() => setIsPaused(!isPaused)}
            className={`px-2 py-0.5 rounded text-[10px] font-mono flex items-center gap-1 border transition-colors ${
              isPaused
                ? 'bg-[#fffbeb] text-[#b45309] border-[#fde68a] font-bold'
                : 'bg-[#ede3d8] text-[#261912] hover:bg-[#e4d7ca] border-[#d8cbbe]'
            }`}
            title={isPaused ? 'Auto-scroll is paused' : 'Click to pause auto-scroll'}
          >
            {isPaused ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
            {isPaused ? 'PAUSED' : 'LIVE'}
          </button>

          {/* Clear stream */}
          {onClear && (
            <button
              onClick={onClear}
              className="p-1 rounded text-space-400 hover:text-[#261912] bg-[#ede3d8] border border-[#d8cbbe] transition-colors"
              title="Clear event stream"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* Filter Chips */}
      <div className="flex items-center gap-1.5 mb-2 pb-1.5 border-b border-[#ded2c5] shrink-0 text-[10px] font-mono">
        <Filter className="w-3 h-3 text-space-400 mr-0.5" />
        {(['ALL', 'ANOMALIES', 'FSM', 'VISION'] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => setFilter(mode)}
            className={`px-2 py-0.5 rounded transition-colors ${
              filter === mode
                ? 'bg-[#964f19] text-white border border-[#7c3d10] font-bold shadow-sm'
                : 'bg-[#f4eae0] text-[#261912] hover:bg-[#ede2d6] border border-[#ded2c5]'
            }`}
          >
            {mode}
          </button>
        ))}
      </div>

      {/* Scannable Scrollable Event List */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-1 pr-1 font-mono text-[11px]"
      >
        {filteredEvents.length === 0 ? (
          <div className="h-full flex items-center justify-center text-space-400 text-xs">
            Awaiting session telemetry events...
          </div>
        ) : (
          filteredEvents.map((ev) => (
            <div
              key={ev.id}
              className={`flex items-start gap-2 p-1.5 rounded border transition-colors ${
                ev.severity === 'CRITICAL'
                  ? 'bg-[#fef2f2] border-[#fecaca] text-[#b91c1c]'
                  : ev.severity === 'WARNING'
                  ? 'bg-[#fffbeb] border-[#fde68a] text-[#b45309]'
                  : 'bg-[#fbf9f6] border-[#ded2c5] text-[#261912] hover:bg-[#f3eae0]'
              }`}
            >
              <div className="mt-0.5">{getSeverityIcon(ev.severity)}</div>

              <span className="text-[10px] text-space-400 shrink-0 tabular-nums">
                {ev.timestamp}
              </span>

              <span
                className={`px-1.5 py-0.2 rounded text-[9px] font-bold border shrink-0 ${getCategoryColor(
                  ev.category
                )}`}
              >
                {ev.category}
              </span>

              <span className="flex-1 min-w-0 break-words leading-tight">
                {ev.message}
              </span>

              {ev.meta && (
                <span className="text-[9px] text-space-400 shrink-0 font-normal">
                  {ev.meta}
                </span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

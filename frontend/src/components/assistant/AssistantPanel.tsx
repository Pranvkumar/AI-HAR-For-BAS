import { useState, useRef, useEffect } from 'react';
import { Bot, X, Send, Sparkles, Terminal, CheckCircle2, ShieldCheck } from 'lucide-react';
import { api } from '@/services/api';

interface AssistantPanelProps {
  open: boolean;
  onClose: () => void;
  /** Scopes replies to a running session's FSM state. */
  sessionId?: number | null;
}

interface Message {
  role: 'user' | 'assistant';
  text: string;
  time: string;
}

const FALLBACK_SUGGESTIONS = [
  'What is the current experiment step?',
  'What should I do next?',
  'Show current experiment status.',
  'Show the full procedure.',
];

export default function AssistantPanel({ open, onClose, sessionId }: AssistantPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>(FALLBACK_SUGGESTIONS);
  const [pending, setPending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const getCurrentTime = () => {
    return new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, pending]);

  // Suggestions come from the backend so they track the real procedure.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    api
      .getSuggestions()
      .then((list) => {
        if (!cancelled && list.length) setSuggestions(list);
      })
      .catch(() => {
        // Keep the fallback list if the backend is unreachable.
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const ask = async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || pending) return;

    const time = getCurrentTime();
    setMessages((prev) => [...prev, { role: 'user', text: trimmed, time }]);
    setInput('');
    setPending(true);

    try {
      const response = await api.chat(trimmed, sessionId);
      setMessages((prev) => [...prev, { role: 'assistant', text: response.reply, time: getCurrentTime() }]);
    } catch (err) {
      const detail = err instanceof Error ? err.message : 'request failed';
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: `Copilot offline or unreachable — ${detail}`, time: getCurrentTime() },
      ]);
    } finally {
      setPending(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={`fixed right-0 top-0 bottom-0 w-full sm:w-[420px] bg-space-950/95 backdrop-blur-md border-l border-space-800 z-50 flex flex-col shadow-2xl transition-transform duration-300 ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-space-800 bg-space-900/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-accent-500/15 border border-accent-500/30 flex items-center justify-center shadow-glow-accent">
              <Bot className="w-4 h-4 text-accent-400" />
            </div>
            <div>
              <div className="text-xs font-mono font-bold tracking-wider text-white">AVIONICS COPILOT</div>
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-tealx-400 animate-pulse" />
                <span className="text-[10px] font-mono text-tealx-400">DO-178C Grounded</span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-space-800 text-space-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Telemetry grounding banner */}
        <div className="px-4 py-2 bg-accent-500/10 border-b border-accent-500/20 flex items-center justify-between">
          <span className="text-[10px] font-mono text-accent-300 flex items-center gap-1.5 font-semibold">
            <Sparkles className="w-3 h-3 text-accent-400" />
            SYNCHRONIZED WITH TELEMETRY STREAM
          </span>
          <span className="text-[9px] font-mono text-space-400">LATENCY &lt; 20ms</span>
        </div>

        {/* Message Log */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3.5">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <div className="w-12 h-12 rounded-xl bg-space-900/80 border border-space-800 flex items-center justify-center mx-auto mb-3 shadow-inner">
                <Bot className="w-6 h-6 text-space-500" />
              </div>
              <p className="text-xs font-mono font-bold text-space-200 mb-1 uppercase tracking-wider">
                Autonomous Copilot Online
              </p>
              <p className="text-[11px] text-space-400 max-w-xs mx-auto">
                Ready for procedural inquiries, step validations, and microgravity safety checks.
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[88%] rounded-lg p-3 text-xs leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-accent-600/20 text-accent-100 border border-accent-500/30 font-sans'
                    : 'bg-space-900/80 text-space-100 border border-space-800 shadow-md font-mono'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5 pb-1 border-b border-white/5">
                  <div className="flex items-center gap-1 text-[10px] font-mono font-bold">
                    {msg.role === 'assistant' ? (
                      <>
                        <Bot className="w-3 h-3 text-accent-400" />
                        <span className="text-accent-400">COPILOT</span>
                      </>
                    ) : (
                      <span className="text-space-300">OPERATOR</span>
                    )}
                  </div>
                  <span className="text-[9px] font-mono text-space-500">{msg.time}</span>
                </div>
                <p className="whitespace-pre-line">{msg.text}</p>
              </div>
            </div>
          ))}

          {pending && (
            <div className="flex justify-start">
              <div className="bg-space-900/80 border border-space-800 rounded-lg p-3 flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-accent-400 animate-ping" />
                <span className="text-xs font-mono text-space-400">Evaluating flight state...</span>
              </div>
            </div>
          )}
        </div>

        {/* Suggested Queries */}
        {messages.length === 0 && (
          <div className="px-4 pb-3 space-y-1.5">
            <div className="text-[10px] font-mono font-bold tracking-wider text-space-400 uppercase mb-2">
              Recommended Procedure Prompts
            </div>
            {suggestions.map((q) => (
              <button
                key={q}
                onClick={() => void ask(q)}
                className="w-full text-left px-3 py-2 rounded-lg bg-space-900/60 border border-space-800 text-xs text-space-300 hover:border-accent-500/40 hover:text-white transition-all duration-200 font-mono"
              >
                &gt; {q}
              </button>
            ))}
          </div>
        )}

        {/* Input Bar */}
        <div className="p-3.5 border-t border-space-800 bg-space-900/40">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void ask(input)}
              placeholder="Inquire with copilot..."
              className="input-field flex-1 text-xs font-mono py-2"
            />
            <button
              onClick={() => void ask(input)}
              disabled={pending}
              className="btn-primary py-2 px-3 text-xs disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

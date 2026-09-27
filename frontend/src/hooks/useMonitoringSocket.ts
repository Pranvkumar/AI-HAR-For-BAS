/**
 * Live monitoring WebSocket hook.
 *
 * Holds the most recent frame plus a rolling window of recent frames, and
 * reconnects with backoff so a backend restart doesn't require a page reload.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { monitoringSocketUrl } from '@/services/api';
import type { ApiMonitoringFrame } from '@/types/api';

export type ConnectionState = 'connecting' | 'open' | 'closed';

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 15000;
const FRAME_HISTORY = 30;

export interface MonitoringStream {
  frame: ApiMonitoringFrame | null;
  history: ApiMonitoringFrame[];
  connection: ConnectionState;
}

export function useMonitoringSocket(): MonitoringStream {
  const [frame, setFrame] = useState<ApiMonitoringFrame | null>(null);
  const [history, setHistory] = useState<ApiMonitoringFrame[]>([]);
  const [connection, setConnection] = useState<ConnectionState>('connecting');

  const socketRef = useRef<WebSocket | null>(null);
  const attemptsRef = useRef(0);
  const timerRef = useRef<number | null>(null);
  const closedByUsRef = useRef(false);

  const connect = useCallback(() => {
    if (closedByUsRef.current) return;

    setConnection('connecting');
    const socket = new WebSocket(monitoringSocketUrl());
    socketRef.current = socket;

    socket.onopen = () => {
      attemptsRef.current = 0;
      setConnection('open');
    };

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data as string);
        // The server sends keepalive pings between inference frames.
        if (payload?.type === 'ping') return;

        const next = payload as ApiMonitoringFrame;
        setFrame(next);
        setHistory((prev) => [...prev, next].slice(-FRAME_HISTORY));
      } catch {
        // Ignore malformed frames rather than tearing down the socket.
      }
    };

    socket.onclose = () => {
      setConnection('closed');
      if (closedByUsRef.current) return;

      // Exponential backoff, capped, so a downed backend is retried politely.
      const delay = Math.min(
        RECONNECT_BASE_MS * 2 ** attemptsRef.current,
        RECONNECT_MAX_MS,
      );
      attemptsRef.current += 1;
      timerRef.current = window.setTimeout(connect, delay);
    };

    socket.onerror = () => socket.close();
  }, []);

  useEffect(() => {
    closedByUsRef.current = false;
    connect();

    return () => {
      closedByUsRef.current = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
      socketRef.current?.close();
    };
  }, [connect]);

  return { frame, history, connection };
}

/**
 * Data-fetching hooks with optional polling.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

export interface QueryState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Fetch on mount and optionally re-fetch on an interval.
 *
 * `deps` controls when the fetcher is considered new — pass values the fetcher
 * closes over, the same way you would for useEffect.
 */
export function useQuery<T>(
  fetcher: () => Promise<T>,
  options: { intervalMs?: number; deps?: unknown[]; enabled?: boolean } = {},
): QueryState<T> {
  const { intervalMs, deps = [], enabled = true } = options;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  // Keep the latest fetcher without making it a re-render trigger.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const cancelledRef = useRef(false);

  const load = useCallback(async () => {
    try {
      const result = await fetcherRef.current();
      if (cancelledRef.current) return;
      setData(result);
      setError(null);
    } catch (err) {
      if (cancelledRef.current) return;
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      if (!cancelledRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    cancelledRef.current = false;
    setLoading(true);
    void load();

    if (!intervalMs) {
      return () => {
        cancelledRef.current = true;
      };
    }

    const timer = setInterval(() => void load(), intervalMs);
    return () => {
      cancelledRef.current = true;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, intervalMs, load, ...deps]);

  return { data, loading, error, refetch: () => void load() };
}

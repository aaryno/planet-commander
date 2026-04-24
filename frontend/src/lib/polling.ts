"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const ERROR_RETRY_MS = 10_000; // Retry every 10s on error

export function usePoll<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  enabled = true,
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const hasData = useRef(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const result = await fetcher();
      setData(result);
      setError(null);
      hasData.current = true;
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [fetcher]);

  useEffect(() => {
    // Always fetch once when fetcher changes (e.g., lookback changed)
    refresh();

    if (!enabled) return;

    // Schedule periodic refreshes
    const scheduleNext = () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      const delay = hasData.current ? intervalMs : ERROR_RETRY_MS;
      intervalRef.current = setInterval(() => {
        refresh().then(() => {
          if (hasData.current) {
            if (intervalRef.current) clearInterval(intervalRef.current);
            intervalRef.current = setInterval(refresh, intervalMs);
          }
        });
      }, delay);
    };

    scheduleNext();

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [refresh, intervalMs, enabled]);

  return { data, loading, refreshing, error, refresh };
}

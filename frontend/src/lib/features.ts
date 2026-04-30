"use client";

import { useEffect, useState } from "react";

import { api } from "./api";
import type { FeatureFlags } from "./api";

const DEFAULT: FeatureFlags = {
  pcg_integration: false,
};

// Module-level cache so multiple useFeatures() callers share one fetch.
let _cache: FeatureFlags | null = null;
let _inflight: Promise<FeatureFlags> | null = null;

async function _fetchFeatures(): Promise<FeatureFlags> {
  if (_cache) return _cache;
  if (_inflight) return _inflight;
  _inflight = api
    .configFeatures()
    .then((flags) => {
      _cache = flags;
      _inflight = null;
      return flags;
    })
    .catch((err) => {
      // Treat fetch failures as "all features off" — safer than crashing
      // the UI when the backend is partially unavailable.
      _inflight = null;
      console.warn("configFeatures fetch failed, defaulting to off:", err);
      _cache = DEFAULT;
      return DEFAULT;
    });
  return _inflight;
}

/**
 * Read the backend-provided feature flags. Cached process-wide so the same
 * call doesn't fire on every render. Returns DEFAULT (everything off)
 * until the fetch completes.
 */
export function useFeatures(): FeatureFlags {
  const [flags, setFlags] = useState<FeatureFlags>(_cache ?? DEFAULT);

  useEffect(() => {
    if (_cache) {
      setFlags(_cache);
      return;
    }
    let cancelled = false;
    _fetchFeatures().then((f) => {
      if (!cancelled) setFlags(f);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return flags;
}

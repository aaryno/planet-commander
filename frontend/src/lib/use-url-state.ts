"use client";

import { useCallback, useMemo, useState, useEffect, useRef } from "react";
import { useSearchParams, usePathname } from "next/navigation";

/**
 * Hook that syncs state to URL search params for permalinking.
 *
 * Uses window.history.replaceState (not router.replace) to avoid
 * triggering Next.js re-renders on every state change.
 *
 * Usage:
 *   const [value, setValue] = useUrlParam("filter", "all");
 *   const [items, setItems] = useUrlArrayParam("statuses", ["a", "b"]);
 *   const [flag, setFlag] = useUrlBoolParam("showHidden", false);
 */

/** Read current URL search params directly from window (avoids stale closure). */
function getCurrentParams(): URLSearchParams {
  if (typeof window === "undefined") return new URLSearchParams();
  return new URLSearchParams(window.location.search);
}

/** Update a single URL param without triggering Next.js navigation. */
function updateUrlParam(pathname: string, key: string, value: string | null) {
  const params = getCurrentParams();
  if (value === null || value === "") {
    params.delete(key);
  } else {
    params.set(key, value);
  }
  const qs = params.toString();
  const url = `${pathname}${qs ? `?${qs}` : ""}`;
  window.history.replaceState(window.history.state, "", url);
}

/** String param — `null` maps to default. */
export function useUrlParam(
  key: string,
  defaultValue: string,
): [string, (v: string) => void] {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const initial = searchParams.get(key) ?? defaultValue;
  const [value, setValueState] = useState(initial);

  // Sync from URL on external navigation (back/forward)
  const urlValue = searchParams.get(key) ?? defaultValue;
  const prevUrlValue = useRef(urlValue);
  useEffect(() => {
    if (urlValue !== prevUrlValue.current) {
      prevUrlValue.current = urlValue;
      setValueState(urlValue);
    }
  }, [urlValue]);

  const setValue = useCallback(
    (v: string) => {
      setValueState(v);
      updateUrlParam(pathname, key, v === defaultValue ? null : v);
    },
    [key, defaultValue, pathname],
  );

  return [value, setValue];
}

/** Nullable string param — `null` is a valid state (no param in URL). */
export function useUrlNullableParam(
  key: string,
): [string | null, (v: string | null) => void] {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const initial = searchParams.get(key);
  const [value, setValueState] = useState<string | null>(initial);

  const urlValue = searchParams.get(key);
  const prevUrlValue = useRef(urlValue);
  useEffect(() => {
    if (urlValue !== prevUrlValue.current) {
      prevUrlValue.current = urlValue;
      setValueState(urlValue);
    }
  }, [urlValue]);

  const setValue = useCallback(
    (v: string | null) => {
      setValueState(v);
      updateUrlParam(pathname, key, v);
    },
    [key, pathname],
  );

  return [value, setValue];
}

/** Boolean param — only written to URL when different from default. */
export function useUrlBoolParam(
  key: string,
  defaultValue: boolean = false,
): [boolean, (v: boolean) => void] {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const raw = searchParams.get(key);
  const initial = raw !== null ? raw === "true" || raw === "1" : defaultValue;
  const [value, setValueState] = useState(initial);

  const urlRaw = searchParams.get(key);
  const urlValue = urlRaw !== null ? urlRaw === "true" || urlRaw === "1" : defaultValue;
  const prevUrlValue = useRef(urlValue);
  useEffect(() => {
    if (urlValue !== prevUrlValue.current) {
      prevUrlValue.current = urlValue;
      setValueState(urlValue);
    }
  }, [urlValue]);

  const setValue = useCallback(
    (v: boolean) => {
      setValueState(v);
      updateUrlParam(pathname, key, v === defaultValue ? null : String(v));
    },
    [key, defaultValue, pathname],
  );

  return [value, setValue];
}

/** Array param — comma-separated in URL. */
export function useUrlArrayParam(
  key: string,
  defaultValue: string[],
): [string[], (v: string[]) => void] {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const raw = searchParams.get(key);
  const initial = useMemo(() => {
    if (raw === null) return defaultValue;
    if (raw === "") return [];
    return raw.split(",");
  }, []); // Only compute on mount
  const [value, setValueState] = useState<string[]>(initial);

  // Sync from URL on external navigation
  const urlRaw = searchParams.get(key);
  const prevUrlRaw = useRef(urlRaw);
  useEffect(() => {
    if (urlRaw !== prevUrlRaw.current) {
      prevUrlRaw.current = urlRaw;
      if (urlRaw === null) {
        setValueState(defaultValue);
      } else if (urlRaw === "") {
        setValueState([]);
      } else {
        setValueState(urlRaw.split(","));
      }
    }
  }, [urlRaw, defaultValue]);

  const setValue = useCallback(
    (v: string[]) => {
      setValueState(v);
      const isDefault =
        v.length === defaultValue.length &&
        defaultValue.every((item, i) => item === v[i]);
      updateUrlParam(pathname, key, isDefault ? null : v.join(","));
    },
    [key, defaultValue, pathname],
  );

  return [value, setValue];
}

/** Number param. */
export function useUrlNumberParam(
  key: string,
  defaultValue: number,
): [number, (v: number) => void] {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const raw = searchParams.get(key);
  const initial = raw !== null ? Number(raw) : defaultValue;
  const [value, setValueState] = useState(initial);

  const urlRaw = searchParams.get(key);
  const urlValue = urlRaw !== null ? Number(urlRaw) : defaultValue;
  const prevUrlValue = useRef(urlValue);
  useEffect(() => {
    if (urlValue !== prevUrlValue.current) {
      prevUrlValue.current = urlValue;
      setValueState(urlValue);
    }
  }, [urlValue]);

  const setValue = useCallback(
    (v: number) => {
      setValueState(v);
      updateUrlParam(pathname, key, v === defaultValue ? null : String(v));
    },
    [key, defaultValue, pathname],
  );

  return [value, setValue];
}

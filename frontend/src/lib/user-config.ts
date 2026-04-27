"use client";

import { useEffect, useState } from "react";

interface UserConfig {
  display_name: string;
}

let _cache: UserConfig | null = null;

export function useUserConfig(): UserConfig {
  const [config, setConfig] = useState<UserConfig>(_cache || { display_name: "" });

  useEffect(() => {
    if (_cache) return;
    fetch("/api/config/user")
      .then((r) => r.json())
      .then((data) => {
        _cache = data;
        setConfig(data);
      })
      .catch(() => {});
  }, []);

  return config;
}

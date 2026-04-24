"use client";

import { useState, useEffect } from "react";

export interface Settings {
  terminal: {
    app: string;
    customCommand?: string;
  };
}

const DEFAULT_SETTINGS: Settings = {
  terminal: {
    app: "ghostty",
  },
};

const STORAGE_KEY = "dashboard-settings";

export function useSettings() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);

  useEffect(() => {
    // Load settings from localStorage
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        setSettings(JSON.parse(stored));
      } catch (e) {
        console.error("Failed to parse settings:", e);
      }
    }
  }, []);

  const updateSettings = (updates: Partial<Settings>) => {
    const newSettings = { ...settings, ...updates };
    setSettings(newSettings);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newSettings));
  };

  const updateTerminalApp = (app: string, customCommand?: string) => {
    updateSettings({
      terminal: { app, customCommand },
    });
  };

  return {
    settings,
    updateSettings,
    updateTerminalApp,
  };
}

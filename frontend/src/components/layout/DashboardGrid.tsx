"use client";

import { useCallback, useState, useRef, useEffect } from "react";
import { ResponsiveGridLayout, useContainerWidth, verticalCompactor } from "react-grid-layout";
import type { LayoutItem } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

const STORAGE_KEY_PREFIX = "commander-layout-v4-";

interface DashboardGridProps {
  page: string;
  cards: Record<string, React.ReactNode>;
  defaultLayout: LayoutItem[];
}

export function DashboardGrid({ page, cards, defaultLayout }: DashboardGridProps) {
  const { containerRef, width } = useContainerWidth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const [layouts, setLayouts] = useState<{ lg: LayoutItem[] }>(() => {
    if (typeof window === "undefined") return { lg: defaultLayout };
    const saved = localStorage.getItem(`${STORAGE_KEY_PREFIX}${page}`);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return { lg: defaultLayout };
      }
    }
    return { lg: defaultLayout };
  });

  const saveTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleLayoutChange = useCallback((_current: any, allLayouts: any) => {
    setLayouts({ lg: [...(allLayouts?.lg || _current)] });
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      localStorage.setItem(`${STORAGE_KEY_PREFIX}${page}`, JSON.stringify(allLayouts));
    }, 500);
  }, [page]);

  const handleResetLayout = useCallback(() => {
    setLayouts({ lg: defaultLayout });
    localStorage.removeItem(`${STORAGE_KEY_PREFIX}${page}`);
  }, [page, defaultLayout]);

  if (!mounted || width <= 0) {
    return <div className="p-4 text-zinc-500">Loading...</div>;
  }

  return (
    <div ref={containerRef} className="relative w-full h-full">
      <button
        onClick={handleResetLayout}
        className="absolute top-0 right-0 z-10 text-[10px] text-zinc-600 hover:text-zinc-400 px-2 py-1"
        title="Reset layout to default"
      >
        Reset Layout
      </button>
      <ResponsiveGridLayout
        className="layout"
        layouts={layouts}
        breakpoints={{ lg: 900, md: 600, sm: 400, xs: 0 }}
        cols={{ lg: 12, md: 12, sm: 6, xs: 4 }}
        rowHeight={80}
        width={width}
        onLayoutChange={handleLayoutChange}
        dragConfig={{ enabled: true, bounded: false, handle: ".cursor-move", threshold: 3 }}
        resizeConfig={{
          enabled: true,
          handles: ["se"] as const,
        }}
        compactor={verticalCompactor}
        margin={[12, 12] as const}
        containerPadding={[0, 0] as const}
      >
        {Object.entries(cards).map(([id, content]) => (
          <div key={id} className="h-full">
            {content}
          </div>
        ))}
      </ResponsiveGridLayout>
    </div>
  );
}

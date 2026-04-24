"use client";
import { useState, useEffect, createContext, useContext, useCallback } from "react";
import { X } from "lucide-react";
import Link from "next/link";

interface Toast {
  id: string;
  message: string;
  link?: { label: string; href: string };
  duration?: number;
}

interface ToastContextType {
  showToast: (toast: Omit<Toast, "id">) => void;
}

export const ToastContext = createContext<ToastContextType>({ showToast: () => {} });
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((toast: Omit<Toast, "id">) => {
    const id = Math.random().toString(36).slice(2);
    setToasts(prev => [...prev, { ...toast, id }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, toast.duration || 4000);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {/* Toast container */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map(toast => (
          <div key={toast.id} className="bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl px-4 py-3 flex items-center gap-3 animate-in slide-in-from-bottom-2 min-w-[280px]">
            <span className="text-sm text-zinc-200 flex-1">{toast.message}</span>
            {toast.link && (
              <Link href={toast.link.href} className="text-sm text-blue-400 hover:text-blue-300 font-medium whitespace-nowrap">
                {toast.link.label}
              </Link>
            )}
            <button onClick={() => dismiss(toast.id)} className="text-zinc-500 hover:text-zinc-300">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

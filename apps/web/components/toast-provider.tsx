"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

type ToastTone = "success" | "error" | "info";

type ToastInput = {
  title?: string;
  message: string;
  tone?: ToastTone;
  durationMs?: number;
};

type ToastItem = Required<Pick<ToastInput, "message" | "tone" | "durationMs">> & {
  id: string;
  title?: string;
};

type ToastContextValue = {
  notify: (toast: ToastInput) => void;
  success: (message: string, title?: string) => void;
  error: (message: string, title?: string) => void;
  info: (message: string, title?: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);
const TOAST_EVENT = "optigrade:toast";

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const notify = useCallback((toast: ToastInput) => {
    const item: ToastItem = {
      id: newToastId(),
      message: toast.message,
      title: toast.title,
      tone: toast.tone ?? "info",
      durationMs: toast.durationMs ?? 5200
    };
    setItems((current) => [...current.slice(-3), item]);
  }, []);

  useEffect(() => {
    const onToast = (event: Event) => {
      const detail = (event as CustomEvent<ToastInput>).detail;
      if (detail?.message) notify(detail);
    };
    window.addEventListener(TOAST_EVENT, onToast);
    return () => window.removeEventListener(TOAST_EVENT, onToast);
  }, [notify]);

  useEffect(() => {
    if (!items.length) return;
    const timers = items.map((item) => window.setTimeout(() => dismiss(item.id), item.durationMs));
    return () => timers.forEach(window.clearTimeout);
  }, [dismiss, items]);

  const value = useMemo<ToastContextValue>(
    () => ({
      notify,
      success: (message, title) => notify({ message, title, tone: "success" }),
      error: (message, title) => notify({ message, title, tone: "error", durationMs: 7200 }),
      info: (message, title) => notify({ message, title, tone: "info" })
    }),
    [notify]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed inset-x-3 bottom-3 z-[200] grid justify-items-stretch gap-2 sm:inset-x-auto sm:right-4 sm:bottom-4 sm:w-[380px]">
        <AnimatePresence initial={false}>
          {items.map((item) => (
            <ToastCard key={item.id} item={item} onDismiss={() => dismiss(item.id)} />
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast deve ser usado dentro de ToastProvider");
  }
  return context;
}

export function pushToast(toast: ToastInput) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(TOAST_EVENT, { detail: toast }));
}

function ToastCard({ item, onDismiss }: { item: ToastItem; onDismiss: () => void }) {
  const Icon = item.tone === "success" ? CheckCircle2 : item.tone === "error" ? AlertTriangle : Info;
  const toneClass =
    item.tone === "success"
      ? "border-moss/35 bg-moss/10 text-moss"
      : item.tone === "error"
        ? "border-rose/35 bg-rose/10 text-rose"
        : "border-lake/35 bg-lake/10 text-lake";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 18, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: 24, scale: 0.98 }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
      className="pointer-events-auto overflow-hidden rounded-lg border border-slateLine bg-white shadow-2xl"
    >
      <div className="grid grid-cols-[auto_1fr_auto] gap-3 p-3">
        <div className={`mt-0.5 grid h-9 w-9 place-items-center rounded-md border ${toneClass}`}>
          <Icon size={18} />
        </div>
        <div className="min-w-0">
          {item.title ? <div className="text-sm font-semibold text-ink">{item.title}</div> : null}
          <div className="text-sm leading-relaxed text-slate-700">{item.message}</div>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="focus-ring grid h-8 w-8 place-items-center rounded-md text-slate-500 transition hover:bg-slate-100 hover:text-ink"
          aria-label="Fechar notificação"
        >
          <X size={16} />
        </button>
      </div>
    </motion.div>
  );
}

function newToastId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

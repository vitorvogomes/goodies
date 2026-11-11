"use client";

// Media query como estado React (useSyncExternalStore): o shell só renderiza no cliente, depois do
// gate de sessão, então não há diferença de hidratação. No servidor vale o layout de desktop.
import { useSyncExternalStore } from "react";

export function useMedia(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mq = window.matchMedia(query);
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}

/** Celular: abaixo do `sm` (640px) — tabelas viram cartões. */
export const PHONE = "(max-width: 639.98px)";
/** Abaixo do `lg` (1024px) — a barra lateral dá lugar à navegação inferior. */
export const BELOW_LG = "(max-width: 1023.98px)";

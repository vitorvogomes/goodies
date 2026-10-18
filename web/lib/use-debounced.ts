"use client";

import { useEffect, useState } from "react";

/** O valor só muda depois de `ms` sem alteração (prévia ao vivo sem uma chamada por tecla). */
export function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

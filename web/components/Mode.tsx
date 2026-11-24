"use client";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const Mode = createContext<boolean | undefined>(undefined);
export const useReadOnly = () => useContext(Mode);

export default function ModeProvider({children}: {children: ReactNode}) {
  const [readOnly, set] = useState<boolean>();
  const [error, fail] = useState(false);
  const [attempt, retry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/mode", {signal: controller.signal, cache:"no-store"})
      .then(async r => {
        if (!r.ok) throw Error();
        set((await r.json()).read_only === false ? false : true);
        fail(false);
      }).catch(() => { if (!controller.signal.aborted) fail(true); });
    return () => controller.abort();
  }, [attempt]);
  return <Mode.Provider value={readOnly}>
    {error && <p role="alert">Could not check compute availability. <button onClick={() => retry(attempt+1)}>Retry connection</button></p>}
    {readOnly && <p className="demo-mode">Public demo · Explore archived simulations, observed tracks and model predictions. Live calculations are available in a local installation.</p>}
    {children}
  </Mode.Provider>;
}

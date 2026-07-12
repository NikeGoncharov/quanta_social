// One SSE stream for the whole cabinet. Opening it counts as a viewer, so the world keeps
// ticking while you move between pages (grid, reporting, detail) — not only on the Live tab.
import { createContext, useContext, type ReactNode } from "react";

import { useSimStream, type SimStream } from "./useSimStream";

const SimCtx = createContext<SimStream | null>(null);

export function SimProvider({ children }: { children: ReactNode }) {
  const sim = useSimStream();
  return <SimCtx.Provider value={sim}>{children}</SimCtx.Provider>;
}

export function useSim(): SimStream {
  const v = useContext(SimCtx);
  if (!v) throw new Error("useSim must be used within a SimProvider");
  return v;
}

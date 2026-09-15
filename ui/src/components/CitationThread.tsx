import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

/**
 * Signature interaction #1 (design spec E): focusing or clicking a citation
 * draws a real SVG path from the claim to the exact Exhibit card(s) behind
 * it. This is the Phase 3 citation-validation system made visible, not
 * decoration -- so the connector always points at a real fact_id already
 * checked against the evidence bundle server-side.
 */

interface CitationThreadContextValue {
  registerExhibit: (factId: string, el: HTMLElement | null) => void;
  activate: (chipEl: HTMLElement, factIds: string[]) => void;
  deactivate: () => void;
  activeFactIds: string[];
}

const CitationThreadContext = createContext<CitationThreadContextValue | null>(null);

export function useCitationThread(): CitationThreadContextValue {
  const ctx = useContext(CitationThreadContext);
  if (!ctx) throw new Error("useCitationThread must be used within a CitationThreadProvider");
  return ctx;
}

export function CitationThreadProvider({ children }: { children: ReactNode }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const exhibitRefs = useRef(new Map<string, HTMLElement>());
  const [paths, setPaths] = useState<{ d: string; factId: string }[]>([]);
  const [activeFactIds, setActiveFactIds] = useState<string[]>([]);
  const [svgSize, setSvgSize] = useState({ width: 0, height: 0 });

  const registerExhibit = useCallback((factId: string, el: HTMLElement | null) => {
    if (el) exhibitRefs.current.set(factId, el);
    else exhibitRefs.current.delete(factId);
  }, []);

  const activate = useCallback((chipEl: HTMLElement, factIds: string[]) => {
    const container = containerRef.current;
    if (!container) return;
    const containerRect = container.getBoundingClientRect();
    const chipRect = chipEl.getBoundingClientRect();
    const startX = chipRect.left - containerRect.left + container.scrollLeft;
    const startY = chipRect.top - containerRect.top + container.scrollTop + chipRect.height / 2;

    const newPaths: { d: string; factId: string }[] = [];
    for (const factId of factIds) {
      const exhibitEl = exhibitRefs.current.get(factId);
      if (!exhibitEl) continue;
      const exhibitRect = exhibitEl.getBoundingClientRect();
      const endX = exhibitRect.left - containerRect.left + container.scrollLeft + 16;
      const endY = exhibitRect.top - containerRect.top + container.scrollTop;
      const midY = (startY + endY) / 2;
      newPaths.push({ d: `M ${startX} ${startY} C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${endY}`, factId });
    }
    setSvgSize({ width: container.scrollWidth, height: container.scrollHeight });
    setPaths(newPaths);
    setActiveFactIds(factIds);
  }, []);

  const deactivate = useCallback(() => {
    setPaths([]);
    setActiveFactIds([]);
  }, []);

  return (
    <CitationThreadContext.Provider value={{ registerExhibit, activate, deactivate, activeFactIds }}>
      <div ref={containerRef} className="relative">
        {children}
        <svg
          className="pointer-events-none absolute top-0 left-0"
          style={{ width: svgSize.width, height: svgSize.height }}
          aria-hidden="true"
        >
          {paths.map((p) => (
            <path
              key={p.factId}
              d={p.d}
              fill="none"
              stroke="var(--color-stable)"
              strokeWidth="1.5"
              className="citation-thread-path"
            />
          ))}
        </svg>
      </div>
    </CitationThreadContext.Provider>
  );
}

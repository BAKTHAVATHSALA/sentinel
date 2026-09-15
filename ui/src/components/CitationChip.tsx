import { useRef } from "react";
import { useCitationThread } from "./CitationThread";

/** Triggers the citation thread on focus (Tab + Enter reachable, not
 * hover-only, WCAG 2.1 AA) or click/hover. A real <button>, so focus fires
 * naturally on keyboard navigation. */
export function CitationChip({ factIds, exhibitNumbers }: { factIds: string[]; exhibitNumbers: Record<string, number> }) {
  const { activate, deactivate } = useCitationThread();
  const ref = useRef<HTMLButtonElement>(null);

  return (
    <button
      ref={ref}
      type="button"
      onFocus={() => ref.current && activate(ref.current, factIds)}
      onMouseEnter={() => ref.current && activate(ref.current, factIds)}
      onBlur={deactivate}
      onMouseLeave={deactivate}
      onClick={(e) => {
        e.preventDefault();
        const targetId = `exhibit-${factIds[0]}`;
        document.getElementById(targetId)?.scrollIntoView({ block: "nearest" });
      }}
      className="inline-flex items-center gap-1 rounded-[3px] border border-[var(--color-stable)] bg-[var(--color-stable-soft)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--color-stable)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--color-text)]"
    >
      {factIds
        .map((id) => (exhibitNumbers[id] ? `Exhibit ${String(exhibitNumbers[id]).padStart(2, "0")}` : id))
        .join(", ")}
    </button>
  );
}

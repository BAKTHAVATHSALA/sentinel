/**
 * Tiny shared expand/collapse affordance -- the same control used across
 * Evidence exhibits, the Gemini narrative, Robustness detail, and Policy
 * detail, so the progressive-disclosure pattern reads consistently
 * everywhere on the case page rather than each section inventing its own.
 */
export function DisclosureToggle({ expanded, onToggle, expandLabel = "View evidence", collapseLabel = "Hide" }: {
  expanded: boolean;
  onToggle: () => void;
  expandLabel?: string;
  collapseLabel?: string;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={expanded}
      className="text-[11px] text-[var(--color-text-muted)] underline decoration-dotted hover:text-[var(--color-text)]"
    >
      {expanded ? collapseLabel : expandLabel}
    </button>
  );
}

/**
 * Hand-rolled functional glyphs -- not a generic icon pack. Each icon here
 * encodes a specific system meaning (risk tier, robustness pillar count,
 * evidence quality) so status remains legible without color (WCAG 2.1 AA,
 * design spec S9).
 */

type IconProps = { className?: string };

export function RiskGlyph({ band, className }: { band: "LOW" | "MEDIUM" | "HIGH" } & IconProps) {
  const filled = band === "LOW" ? 1 : band === "MEDIUM" ? 2 : 3;
  return (
    <svg viewBox="0 0 20 16" width="16" height="13" className={className} aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <rect
          key={i}
          x={i * 7}
          y={16 - (i + 1) * 5}
          width="5"
          height={(i + 1) * 5}
          fill={i < filled ? "currentColor" : "none"}
          stroke="currentColor"
          strokeWidth="1"
        />
      ))}
    </svg>
  );
}

export function PillarsGlyph({ count, fragile, className }: { count: number; fragile: boolean } & IconProps) {
  const pillars = Math.max(count, 1);
  return (
    <svg viewBox="0 0 20 16" width="16" height="13" className={className} aria-hidden="true">
      {Array.from({ length: pillars }).map((_, i) => (
        <g key={i}>
          <rect
            x={i * 8 + 2}
            y="2"
            width="5"
            height="12"
            fill={fragile ? "url(#hatch)" : "currentColor"}
            stroke="currentColor"
            strokeWidth="1"
          />
        </g>
      ))}
      <defs>
        <pattern id="hatch" width="3" height="3" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="3" stroke="currentColor" strokeWidth="1.4" />
        </pattern>
      </defs>
    </svg>
  );
}

export function EvidenceQualityGlyph({ complete, className }: { complete: boolean } & IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" className={className} aria-hidden="true">
      <rect x="1" y="1" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <line x1="4" y1="5" x2="12" y2="5" stroke="currentColor" strokeWidth="1.3" />
      <line x1="4" y1="8" x2="12" y2="8" stroke="currentColor" strokeWidth="1.3" opacity={complete ? 1 : 0.35} />
      <line x1="4" y1="11" x2="12" y2="11" stroke="currentColor" strokeWidth="1.3" opacity={complete ? 1 : 0.15} />
    </svg>
  );
}

export function PolicyGlyph({ className }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" className={className} aria-hidden="true">
      <rect x="1.5" y="1.5" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <path d="M4 8.2 L6.8 11 L12 4.8" fill="none" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

export function CompassGlyph({ className }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" className={className} aria-hidden="true">
      <circle cx="8" cy="8" r="6.3" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <path d="M10.3 5.7 L8.9 8.9 L5.7 10.3 L7.1 7.1 Z" fill="currentColor" />
    </svg>
  );
}

export function PenGlyph({ className }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" className={className} aria-hidden="true">
      <path
        d="M3 13 L3.6 10.3 L10.3 3.6 L12.4 5.7 L5.7 12.4 Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.3"
      />
      <line x1="9.2" y1="4.7" x2="11.3" y2="6.8" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  );
}

export function LinkGlyph({ className }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" width="13" height="13" className={className} aria-hidden="true">
      <path d="M6.5 9.5 L9.5 6.5" stroke="currentColor" strokeWidth="1.3" />
      <path
        d="M7.2 5.5 L8.4 4.3 A2 2 0 0 1 11.2 7.1 L10.4 7.9"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.3"
      />
      <path
        d="M8.8 10.5 L7.6 11.7 A2 2 0 0 1 4.8 8.9 L5.6 8.1"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.3"
      />
    </svg>
  );
}

const TOOL_ICON_PATHS: Record<string, React.ReactNode> = {
  get_device_history: (
    <>
      <rect x="4" y="2" width="8" height="12" rx="0.5" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <line x1="6" y1="12" x2="10" y2="12" stroke="currentColor" strokeWidth="1.2" />
    </>
  ),
  get_ip_geovelocity: (
    <>
      <circle cx="8" cy="6.5" r="3.2" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <path d="M8 9.5 L8 14" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="8" cy="6.5" r="1" fill="currentColor" />
    </>
  ),
  get_behavioral_baseline: (
    <>
      <line x1="2" y1="13" x2="14" y2="13" stroke="currentColor" strokeWidth="1.2" />
      <rect x="3.5" y="8" width="2.4" height="5" fill="currentColor" />
      <rect x="7" y="5" width="2.4" height="8" fill="currentColor" />
      <rect x="10.5" y="9.5" width="2.4" height="3.5" fill="currentColor" />
    </>
  ),
  get_linked_entities: (
    <>
      <circle cx="4.5" cy="5" r="2" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="11.5" cy="11" r="2" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <line x1="6" y1="6.5" x2="10" y2="9.5" stroke="currentColor" strokeWidth="1.2" />
    </>
  ),
  get_merchant_risk: (
    <>
      <path d="M2 6 L8 2 L14 6 L14 14 L2 14 Z" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <line x1="6" y1="9" x2="10" y2="9" stroke="currentColor" strokeWidth="1.2" />
    </>
  ),
  get_mock_kyc_status: (
    <>
      <rect x="2.5" y="3" width="11" height="10" rx="0.5" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="6" cy="6.6" r="1.3" fill="none" stroke="currentColor" strokeWidth="1" />
      <line x1="9" y1="6" x2="12" y2="6" stroke="currentColor" strokeWidth="1" />
      <line x1="4.3" y1="10.5" x2="11.7" y2="10.5" stroke="currentColor" strokeWidth="1" />
    </>
  ),
};

export function ToolSourceIcon({ tool, className }: { tool: string } & IconProps) {
  const path = TOOL_ICON_PATHS[tool];
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" className={className} aria-hidden="true">
      {path ?? <circle cx="8" cy="8" r="5" fill="none" stroke="currentColor" strokeWidth="1.2" />}
    </svg>
  );
}

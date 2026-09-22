# Sentinel --- Design System

## 1. Purpose

This document defines the visual language for Sentinel so that the
public console, analyst dashboard, senior analyst dashboard, case
detail, login, decision states and supporting UI all feel like one
product.

The design target is:

> **A calm, trustworthy enterprise financial-investigation console.**

Sentinel should feel technical and modern without looking like a
cyberpunk dashboard, gaming interface or generic AI template.

------------------------------------------------------------------------

## 2. Design Principles

### Clarity before decoration

Important information should be understandable immediately.

### Semantic color

Color communicates meaning, not decoration.

### Progressive disclosure

Show the conclusion first and technical detail when the user asks for
it.

### Evidence remains inspectable

Reducing visual density must never remove technical evidence, citations,
timestamps or provenance.

### Calm enterprise visual language

Avoid:

-   neon effects
-   gradients
-   excessive glow
-   excessive shadows
-   oversized illustrations
-   unnecessary animation
-   decorative AI graphics

------------------------------------------------------------------------

# 3. Color System

Use these values as the Sentinel baseline. Components should reference
shared tokens rather than hard-coding colors repeatedly.

## Foundation

  -----------------------------------------------------------------------------
  Token                         Hex                     Usage
  ----------------------------- ----------------------- -----------------------
  `--sentinel-bg`               `#0B1117`               Application background

  `--sentinel-surface`          `#121922`               Main cards and panels

  `--sentinel-surface-raised`   `#171F29`               Elevated panels /
                                                        expanded sections

  `--sentinel-border`           `#27313D`               Borders and separators

  `--sentinel-border-strong`    `#354252`               Focused/active
                                                        structural borders
  -----------------------------------------------------------------------------

## Text

  -----------------------------------------------------------------------------
  Token                         Hex                     Usage
  ----------------------------- ----------------------- -----------------------
  `--sentinel-text-primary`     `#E7EDF4`               Main text, headings,
                                                        important values

  `--sentinel-text-secondary`   `#9BAABD`               Supporting text

  `--sentinel-text-muted`       `#6F8196`               Metadata, timestamps,
                                                        technical labels

  `--sentinel-text-disabled`    `#536274`               Disabled controls
  -----------------------------------------------------------------------------

## Primary / informational

  Token                    Hex         Usage
  ------------------------ ----------- -----------------------------
  `--sentinel-teal`        `#2F9DB5`   Primary accent
  `--sentinel-teal-soft`   `#17353E`   Teal badge/panel background
  `--sentinel-teal-text`   `#62B9CC`   Teal text on dark surfaces

Use teal for:

-   completed stages
-   successful evidence collection
-   informational states
-   active links
-   LOW risk
-   ROBUST
-   AUTO-RESOLVED

## Human attention / warning

  Token                     Hex         Usage
  ------------------------- ----------- ------------------------------
  `--sentinel-amber`        `#D49A32`   Human attention
  `--sentinel-amber-soft`   `#3A2D18`   Amber badge/panel background
  `--sentinel-amber-text`   `#E5B65A`   Amber text

Use amber for:

-   HUMAN REVIEW
-   awaiting analyst action
-   ESCALATE
-   MEDIUM risk
-   pending states
-   warnings that are not technical failures

## Danger

  Token                   Hex         Usage
  ----------------------- ----------- ----------------------------
  `--sentinel-red`        `#C85A52`   High-severity state
  `--sentinel-red-soft`   `#3A2020`   Red badge/panel background
  `--sentinel-red-text`   `#E2766E`   Red text

Use red for:

-   HIGH risk
-   BLOCK & HOLD
-   actual technical failures
-   critical errors

### Critical semantic rule

**Red does not mean "not automatically resolved."**

For example:

-   `HUMAN_REVIEW` → amber
-   `ESCALATE` → amber
-   `AWAITING` → amber
-   `HIGH` → red
-   `BLOCK & HOLD` → red
-   `FAILED` → red

------------------------------------------------------------------------

# 4. Typography

## Font family

Preferred:

``` text
Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
```

Use one typography family throughout the product.

Do not switch to serif typography for AI responses.

## Scale

  Element                          Size     Weight   Line height
  -------------------------- ---------- ---------- -------------
  Page title                   28--32px        600           1.2
  Section title                18--20px        600           1.3
  Card title                   14--16px        600           1.4
  Body                             14px        400           1.5
  Secondary                        13px        400           1.5
  Metadata                         12px        400           1.4
  Large transaction amount     28--32px   500--600           1.2

Use weight to establish hierarchy rather than making everything bold.

------------------------------------------------------------------------

# 5. Spacing

Use a consistent spacing scale:

``` text
4px
8px
12px
16px
20px
24px
32px
40px
48px
```

Prefer the scale over arbitrary one-off values.

Common patterns:

-   card padding: 20--24px
-   section gap: 24--32px
-   control gap: 8--12px
-   page horizontal padding: 24--32px
-   compact metadata gap: 4--8px

------------------------------------------------------------------------

# 6. Borders and Radius

Use subtle borders rather than heavy shadows.

Default:

``` text
border: 1px solid var(--sentinel-border)
```

Suggested radius:

-   inputs/buttons: 4--6px
-   cards/panels: 6--8px
-   badges: 4px

Avoid excessive pill-shaped UI.

Badges may be compact, but large containers should remain structured
rectangles.

------------------------------------------------------------------------

# 7. Buttons

## Primary

Use teal for the primary non-dangerous action.

## Secondary

Dark surface with subtle border.

## Human attention

Amber when the action represents escalation or pending human action.

## Dangerous action

Red for `BLOCK & HOLD` where the product needs to visually communicate
the financial sensitivity.

## Disabled

Muted background and text while retaining enough contrast to understand
the disabled control.

All buttons should share:

-   consistent height
-   font size
-   padding
-   radius
-   focus state
-   hover state
-   disabled state

------------------------------------------------------------------------

# 8. Status Badges

  State           Color
  --------------- -------
  LOW             Teal
  MEDIUM          Amber
  HIGH            Red
  AUTO-RESOLVED   Teal
  HUMAN REVIEW    Amber
  ROBUST          Teal
  FRAGILE         Amber
  AWAITING        Amber
  ESCALATE        Amber
  BLOCK & HOLD    Red
  FAILED          Red

Never create a second color convention for the same state on another
page.

------------------------------------------------------------------------

# 9. Cards and Panels

A standard Sentinel panel should have:

-   `--sentinel-surface`
-   subtle border
-   6--8px radius
-   20--24px padding
-   no large shadow

Use cards to group meaningful information.

Do not put every sentence inside a card.

------------------------------------------------------------------------

# 10. Forms

Inputs/selects/checkboxes/file upload controls should share:

-   dark surface
-   subtle border
-   primary text
-   muted placeholder
-   teal focus state
-   consistent radius
-   consistent height

Focus must be visually obvious.

Disabled controls should remain readable.

------------------------------------------------------------------------

# 11. Tables and Queues

Use:

-   subtle horizontal separators
-   strong header hierarchy
-   consistent row height
-   semantic badges
-   right alignment for numeric values
-   readable case IDs

Avoid excessive vertical borders.

Hover states should be subtle.

------------------------------------------------------------------------

# 12. Evidence Cards

Evidence is technical information, so use progressive disclosure.

Collapsed:

``` text
Device history
New device confirmed                         View →
```

Expanded:

``` text
Device history

known device: false
first seen at: ...
transaction count: ...
source record IDs: [...]
...
```

The summary communicates meaning.

The expanded section preserves technical evidence.

Never fabricate an evidence summary that is not supported by the actual
evidence.

------------------------------------------------------------------------

# 13. AI Reasoning

Gemini's reasoning is advisory.

Use:

``` text
Gemini's assessment · Advisory, not a decision
```

The section should use the same sans-serif typography as the rest of the
application.

Recommended structure:

1.  concise assessment
2.  supporting factors
3.  counter-factors
4.  evidence gaps
5.  expandable full assessment

AI should not receive a special "magic" visual treatment.

------------------------------------------------------------------------

# 14. Pipeline

The investigation pipeline represents progression:

``` text
Detection
→ Evidence
→ Reasoning
→ Robustness
→ Policy
→ Human decision
```

### Completed

Teal.

### Awaiting human action

Amber.

### Actual technical failure

Red.

`Policy → Escalate` is a successful policy result and therefore uses
amber, not red.

------------------------------------------------------------------------

# 15. Scrollbars

The application remains scrollable.

The physical scrollbar should be visually hidden.

Required behavior:

-   mouse wheel works
-   trackpad works
-   keyboard scrolling works
-   Page Up / Page Down works

Do not disable scrolling to hide the scrollbar.

Avoid unnecessary nested scroll containers.

------------------------------------------------------------------------

# 16. Responsive Behavior

Desktop target:

-   approximately 1280px and above
-   full usable workspace
-   comfortable horizontal margins

The main application should not feel like a narrow document centered
inside a large screen.

Use approximately 24--32px page padding.

Avoid horizontal overflow.

Metric cards should wrap when required.

Case detail evidence should use available horizontal space without
becoming difficult to read.

------------------------------------------------------------------------

# 17. Iconography

Use one consistent icon style.

Icons should communicate:

-   evidence source
-   status
-   action
-   navigation

Avoid:

-   emoji as interface icons
-   unrelated icon families
-   decorative icons on every label

------------------------------------------------------------------------

# 18. Motion

Motion should be functional and restrained.

Allowed:

-   button hover
-   focus transitions
-   evidence expansion
-   upload hover
-   subtle loading indicators

Avoid:

-   glowing AI animations
-   floating particles
-   large page transitions
-   decorative motion

------------------------------------------------------------------------

# 19. Accessibility

Maintain:

-   readable contrast
-   visible keyboard focus
-   labels for controls
-   meaningful button text
-   semantic status text in addition to color

Never communicate a critical state by color alone.

For example, use:

``` text
HIGH
```

not only a red badge.

------------------------------------------------------------------------

# 20. Visual QA Checklist

Every major page should be checked for:

-   same font
-   same background
-   same panel treatment
-   same borders
-   same button geometry
-   same semantic colors
-   same status badges
-   readable secondary text
-   no horizontal overflow
-   hidden but functional scrollbar
-   consistent spacing
-   no accidental red escalation
-   no misleading risk/disposition wording

------------------------------------------------------------------------

# 21. Design Principle

Sentinel should look trustworthy because it is **clear and restrained**,
not because it is visually complicated.

The interface should consistently communicate:

> **Detect → Investigate → Explain → Stress-test → Decide**

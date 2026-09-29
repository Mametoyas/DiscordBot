Design Specification — API Usage/Rate-Limit Dashboard UI (Google AI Studio–style)
Reusable system, extended for a "DiscordBot Web Server" panel — status view, model switch, API key entry, and a command-prompt-style log

Source: single screenshot of a "Gemini API Rate Limit" dashboard — page header with tier badge, project/time-range filters, a "Rate limits by model" table with per-model usage bars across RPM/TPM/RPD. Sections marked [Inferred] are not directly visible in the source screenshot and have been extrapolated from the visible tokens to keep the system internally consistent and reusable. Sections marked [Observed] are read directly off the screenshot. Note: a hamburger menu icon is visible top-left, implying a collapsible sidebar that is not shown/expanded in this crop — Section 7 treats it as present-but-unseen rather than inventing its contents.

1. Overview
A clean, quiet, data-dense admin/monitoring dashboard. Almost the entire surface is neutral grayscale text on white; the only structural device carrying visual weight is the data table itself, where compact horizontal usage bars let a user scan many rows at once without needing color-coding or charts inline. This is a "developer console" register — closer to the Fluent settings-panel spec earlier in this series than to any of the consumer marketing pages, but built around one wide table rather than toggle rows.

Design principles to carry forward:

One flat, comparable table for any "many similar items, each with a few numeric limits" dataset — every row has the exact same column shape, making it a scan-friendly grid even though it's laid out as a table, not a card grid.
Progress-bar-plus-fraction (▬▬▬▬ 0 / 60) as the atomic "usage" unit — reused identically across every metric column (RPM, TPM, RPD) regardless of what the metric measures.
Controls cluster near what they affect: the "All models" toggle and "Compare tiers" dropdown sit directly above the table they filter, not in a distant global toolbar.
Status is a small pill, not a headline — "Free tier" is a compact dot+label badge inline with the page title, not a banner; status should stay this unobtrusive wherever it's reused.
2. Visual Style
Attribute	Value
Overall tone	Neutral, technical, calm — a developer-facing console, not a marketing surface
Shape language	Softly rounded rectangles (~6–8px) for buttons, dropdowns, and progress-bar tracks; fully rounded pill for the status badge
Surface style	Flat; the table has no card/border wrapper, rows are separated by a single hairline divider [Observed]
Contrast strategy	Near-monochrome — black/dark-gray text, gray secondary text, light-gray bars/borders; no accent color used decoratively anywhere in this view
Imagery	None — text, icons, and simple progress bars only
3. Color Palette
Token	Approx. Hex	Usage
--color-text-primary	#1A1A1A	Page title, model names, primary labels
--color-text-secondary	#5F6368	Category labels, column headers, helper subtext, filter labels
--color-bg	#FFFFFF	Page background
--color-border	#E0E0E0	Dropdown/button borders, table row dividers
--color-bar-track	#ECECEC	Empty/unfilled portion of every usage progress bar
--color-bar-fill	#1A1A1A [Inferred]	Filled portion of a usage bar once consumption > 0 (not directly observable — every row in the source reads 0 usage)
--color-toggle-on	#1A1A1A	"All models" toggle track, on state
--color-badge-bg	#F1F1F1	"Free tier" status-pill background
Usage rule: this system deliberately spends almost no color budget — everything is grayscale until a bar actually fills, at which point the fill color becomes the only thing that visually distinguishes "used" from "unused." Do not add extra accent colors when extending this system; let the data (bar fill, badge dot) be the only color that appears.

4. Typography
Role	Weight	Approx. Size	Notes
Page title ("Gemini API Rate Limit")	Bold	~26–28px	Text-primary
Status badge text ("Free tier")	Medium	~13px	Text-primary, paired with a small leading dot
Filter label ("Project", "Time Range")	Regular	~13px	Text-secondary, sits to the left of its dropdown
Dropdown value ("DiscordAI", "28 Days")	Medium	~14px	Text-primary
Section heading ("Rate limits by model")	Bold	~16–18px	Text-primary
Section subtext	Regular	~13–14px	Text-secondary
Table column header	Medium	~13px	Text-secondary, uppercase-adjacent but not fully capitalized in source
Model name (table cell)	Medium	~14–15px	Text-primary
Category (table cell)	Regular	~13–14px	Text-secondary
Usage fraction ("0 / 60")	Regular, tabular figures	~13px	Text-primary, right-aligned after its bar
Typeface [Inferred]: Consistent with a Google-product sans-serif, tuned for numeric/tabular legibility:

font-family: "Google Sans", Roboto, -apple-system, "Segoe UI", Arial, sans-serif;
5. Spacing System
Base unit: 8px.

Token	Value	Usage
--space-1	8px	Gap between a bar and its fraction text, icon-to-label gaps
--space-2	16px	Gap between filter label and its dropdown; internal table-cell padding
--space-3	24px	Gap between the filter row and the "Rate limits by model" section header
--space-4	32px	Row height (approx.) in the data table, giving each row breathing room despite the dense dataset
--space-5	40–48px	Gap between the page header and the filter row
6. Grid / Layout
Page header: single row — [title + status badge] (left) — [Docs button, Set up billing button] (right).
Filter row: left-aligned, horizontally adjacent label+dropdown pairs (Project, Time Range), no full-width stretching — controls stay compact and shrink-wrapped to their content.
Section header row: [section title + info icon, subtext below] (left) — [toggle + label, "Compare tiers" dropdown] (right) — same "content left, controls right" pattern as the page header.
Table: full page width, six fixed-role columns (Model, Category, RPM, TPM, RPD, Charts); the three metric columns share identical internal structure (bar + fraction), giving the table strong vertical rhythm even though it has no visible column borders.
No sidebar shown in this crop — a hamburger icon top-left implies one exists but is collapsed; treat it as present in the component hierarchy without inventing its contents.
7. Navigation
[Inferred, not visible] Global sidebar: signaled only by the hamburger icon top-left; contents unknown from this crop.
In-page filtering acts as the primary "navigation" of this view: Project and Time Range dropdowns scope the entire table; the "All models" toggle and "Compare tiers" dropdown further scope it without navigating to a new page.
Table sort: the "RPM" column header carries a small down-arrow, indicating the table is currently sorted by that column — clicking other headers would presumably re-sort, a lightweight in-place navigation of the data itself rather than page navigation.
8. Buttons
Variant	Fill	Text	Border	Use for
Outlined/secondary	White	Text-primary, medium	1px --color-border, ~6–8px radius	The dominant button style on this page — "Set up billing", "Docs" (icon+text)
Dropdown-trigger	White	Text-primary	1px --color-border	"Project", "Time Range", "Compare tiers" — visually identical to the outlined button, distinguished only by a trailing chevron
Toggle switch	Track fills --color-toggle-on when on	n/a	none	Binary scope control ("All models")
Icon-only button	Transparent	Text-secondary icon	none, circular hover hit-area	Hamburger menu, per-row "Charts" icon
Notably absent, as in the earlier Fluent-settings spec: no filled/solid-color primary button appears anywhere. Every action is outlined and neutral — consistent with a console where no single action should visually dominate a data-review screen.

9. Cards
No card container exists in this source — content is either a plain header row or the table itself. If a card is needed for an extension, extrapolate from the button/dropdown treatment already established:

Property	Value [Inferred]
Background	White
Border	1px --color-border
Corner radius	~8px (matches buttons/dropdowns)
Padding	16–24px
10. Forms
Element	Style
Dropdown/select (Project, Time Range)	Bordered box, label sits to its left (not above, unlike some earlier specs in this series), value + trailing chevron
Toggle switch	Small pill track, black fill + white knob when on, paired with a text label to its right
"Compare tiers" control	Same bordered-button shape as a dropdown, trailing chevron, but functions as a menu trigger rather than a simple value select
Text input [Inferred — not present in source]	Likely matches the dropdown's bordered-box treatment for consistency: white fill, 1px border, ~6–8px radius
11. Icons
Style: simple single-weight line icons — hamburger menu, info-circle (help/tooltip trigger next to "Rate limits by model"), document icon (Docs), small bar-chart icon (per-row "Charts" link), dropdown chevrons.
Icons are functional only — no illustrated/multi-color icon style anywhere in this system, reinforcing its console/developer-tool register.
New icons for extensions [Inferred]: a key/lock glyph for an "API key" action, a play/pause or power glyph for bot online/offline status, a terminal/prompt glyph (>_) for the log panel header.
12. Responsive Behavior [Inferred — single desktop breakpoint visible]
Breakpoint	Behavior
≥1200px (desktop)	As observed: wide table with all six columns visible, filter/control rows stay horizontal
900–1199px (tablet)	The "Charts" column may collapse into an overflow menu per row; filter dropdowns may wrap to a second line
<768px (mobile)	The table likely restructures into a stacked card-per-model layout (model name + category as a header, RPM/TPM/RPD as three labeled bar rows beneath) since six columns cannot fit a narrow viewport — this is the standard responsive-table pattern for this data shape
13. Hover / Active States [Inferred — static image, limited direct evidence]
Element	Rest	Hover	Active/Focus
Table row	White bg	Very light gray full-row highlight	n/a — rows aren't persistently selected
Dropdown/outlined button	White bg, gray border	Border darkens or light gray fill appears	Focus ring in a neutral dark tone, dropdown opens
Toggle	—	Slight track darkening on hover	Knob slides, track fills black, ~150ms
Charts icon (per row)	Gray icon	Circular light-gray hover background	Opens a chart/detail view
Column header (sortable)	Gray text + arrow (if active)	Text darkens slightly	Arrow appears/flips direction, table re-sorts
14. Animation & Motion [Inferred — none visible in a static screenshot]
Usage bar fill: when a value updates, the filled portion should animate its width change, ~200–300ms ease-out — appropriate for a monitoring dashboard where values may refresh live.
Toggle: knob slide + track color cross-fade, ~150ms, matching the Fluent-style toggle motion documented earlier in this series.
Dropdown open/close: simple fade + slight vertical offset, ~150ms.
Table re-sort: rows may cross-fade or reflow smoothly rather than snapping instantly, ~200ms, to help the eye track a row that moves position.
15. Component Hierarchy
Page
├── Header Row
│   ├── Page Title + Status Badge ("Gemini API Rate Limit" • "Free tier")
│   └── Actions (Button — Outlined "Docs", Button — Outlined "Set up billing")
│
├── Filter Row
│   ├── Dropdown — "Project" (DiscordAI)
│   └── Dropdown — "Time Range" (28 Days)
│
├── Section Header Row
│   ├── Section Title + info icon + subtext ("Rate limits by model")
│   └── Controls (Toggle "All models", Dropdown "Compare tiers")
│
└── Data Table
    ├── Header Row (Model, Category, RPM↓, TPM, RPD, Charts)
    └── Row × N
        ├── Model name
        ├── Category
        ├── Metric Cell — RPM (bar + "used / limit")
        ├── Metric Cell — TPM (bar + "used / limit")
        ├── Metric Cell — RPD (bar + "used / limit")
        └── Icon button — Charts

    ── [Extension] DiscordBot Web Server Panel ──
    ├── Header Row
    │   ├── Page Title + Status Badge (e.g. "DiscordBot Server" • "● Online" / "● Offline", reusing the exact "Free tier" pill shape with the dot recolored to reflect live status)
    │   └── Actions (Dropdown — "Switch model", reusing the "Compare tiers" trigger shape; Button — Outlined "Add / Update API key", reusing "Set up billing"'s exact treatment)
    │
    ├── Status Summary Row (reuses the Metric Cell shape from the table: bar + "used / limit" style stats, e.g. "Servers connected: 12", "Messages today: 0 / —", "Uptime: 3d 4h")
    │
    └── [New component] Terminal Log Panel
        ├── Panel Header ("Server Log" + `>_` icon + small live-status dot)
        └── Scrolling Log Body (dark background, monospace text, timestamped lines, auto-scrolls to newest, blinking cursor at the bottom)
16. Extending the System — DiscordBot Web Server Notes
The request is intentionally minimal — a status view, a model-switch control, an API-key action, and a command-prompt-style log — so this extension reuses almost every component already documented above, with exactly one deliberate new addition:

Status: reuse the "Free tier" pill exactly, recoloring its leading dot to reflect bot state (e.g. green for online, gray/red for offline) — keep it inline next to the page title, small and unobtrusive, matching this system's existing "status is a pill, not a banner" rule (Section 1).
Model switch: reuse the "Compare tiers" dropdown-button shape (bordered, trailing chevron) as a "Switch model" control listing the available models — visually and behaviorally identical to an existing control, just relabeled.
Add/update API key: reuse the "Set up billing" outlined button exactly — same shape, same weight, same "one quiet action, not a filled CTA" treatment already established for account/billing-adjacent actions. Clicking it should open a simple bordered text-input field (Section 10's inferred text-input style) for the key, not a new visual pattern.
Status metrics (optional): if more than a status dot is wanted (uptime, connected servers, messages processed), reuse the table's Metric Cell exactly — a bar + "value / limit-or-dash" fraction — so it reads as one family with the rate-limit table this system was built around, even in a different product.
Terminal-style log (the one new component): this is a deliberate, explicitly-requested style break from the rest of the (light, neutral) system, and should be treated as such rather than smoothed over — give it a dark background (#1E1E1E–#0D0D0D) and a monospace font stack ("SF Mono", "Fira Code", Consolas, monospace) distinct from the rest of the UI's Google Sans/Roboto, with light-gray or green log text and a subtle blinking cursor at the newest line, auto-scrolling as entries arrive. To keep it feeling like part of this system rather than a bolted-on widget: give it the same ~8px corner radius and the same "header row with a title, left; a small live-status dot, right" shape used everywhere else in this spec, and contain it in a bordered panel rather than letting it float full-bleed. This is the one place in the whole system where color/contrast is allowed to spike — intentionally, because a command-prompt reference should look different from the calm admin chrome around it.
Preserve the system's core discipline everywhere else: no filled/solid-color primary buttons, one hairline-divided list or table per data type, and status expressed as a small pill rather than a hero banner.
End of specification. This document defines reusable tokens and patterns; no implementation code included per request.
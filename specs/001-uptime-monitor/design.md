# Design Brief: Uptime Watch Dashboard

Single file `uptimewatch/dashboard.html`, inline CSS and JS, no frameworks, no external requests (no CDN, web fonts, remote images, icon fonts). Icons are inline SVG or text glyphs.

## 1. Purpose and audience
A glanceable status page for one self-hosting operator who checks it on a phone or a desktop tab to learn "is everything up?" in under two seconds. Secondary job: the same operator adds, edits, pauses and deletes UI targets with an admin token.

Direction: calm "instrument panel", not a SaaS card kit. The one memorable element is the **status banner**: a full-width band with a large serif sentence ("All 7 targets are up") whose left edge carries a thick status-coloured rail. Target rows reuse that rail motif at small scale. Everything else stays quiet: flat surfaces, 1px borders, no shadows, no gradients, no entrance animations.

## 2. Layout
Max content width 960px, centred; page padding 16px (phone) / 32px (desktop). Left-aligned text throughout.

**Phone (390px)** - single column, no horizontal scroll (usable to 360px):
1. Banner band (rail + sentence + small "Updated 12:04:31" line).
2. Optional "cannot reach monitor" notice directly under the banner (sticky-free, in flow).
3. Target list as stacked **row-cards**: line 1 = name (bold, wraps) and badge right-aligned; line 2 = type/source text, latency, 24h uptime; line 3 = last-check time. Error text from the last failure shown below in muted small text (wraps, `overflow-wrap:anywhere`). Management buttons (Edit, Pause/Resume, Delete) in a row at the bottom of UI rows, each at least 44px tall, wrapping if needed.
4. "Add target" is a button at the top of the list that expands the form inline (full-width fields, stacked). Only when management is enabled.

**Desktop (1280px)** - content column 960px:
1. Banner band, with the "Updated" line right-aligned on the same row.
2. Targets as a real `<table>` with columns: Status (badge), Name, Type, Source, Latency, 24h uptime, Last check, Actions. Numeric columns right-aligned with `font-variant-numeric: tabular-nums`. Row left border 4px in status colour.
3. Add form opens as a panel above the table with fields in a 2-column grid (name, type / url or host+port / interval, expected status / buttons).
The same markup may serve both: table on >=720px, rows collapse to the card layout below it (CSS only, `display:block` on rows with `data-label` via `::before` is acceptable).

## 3. Colour palette
Dark mode: **supported** via `prefers-color-scheme: dark` only (no manual toggle), using CSS custom properties. Set `<meta name="color-scheme" content="light dark">`.

| Token | Light | Dark |
|---|---|---|
| background | #F2F5F1 | #0E1411 |
| surface | #FFFFFF | #17211B |
| border | #CBD5CE | #2C3A32 |
| text | #16211A | #E7EEE9 |
| muted text | #4D5E54 | #A3B3AA |
| accent (links, primary button bg) | #0B5C6B | #6CCBDD |
| text on accent | #FFFFFF | #0E1411 |
| success | #1B6B38 | #62D08C |
| warning | #865400 | #E5B04A |
| danger | #B3261E | #FF8F86 |
| unknown/paused (grey) | #5A6660 | #94A39A |

All text colours listed meet >= 4.5:1 on both surface and background (muted on background is the tightest, about 6:1 light / 7.5:1 dark). Status colours are used as text/icon/rail colour on surface; badge fill is the surface with a 1.5px status-coloured border, never a coloured fill with white text. The implementer must verify ratios with a quick calculation in a test or comment, and adjust darker/lighter rather than failing the 4.5:1 rule. Warning is used for the "monitor unreachable" notice and the stale-data line.

## 4. Typography (system stacks only)
- Display (banner sentence, page title): `"Iowan Old Style", "Palatino Linotype", Charter, Georgia, serif`; weight 600.
- UI/body: `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`.
- Sizes (rem, base 16px): page title 1.25rem; banner sentence 1.75rem phone / 2.25rem desktop, line-height 1.2; section heading 1.125rem; body 1rem, line-height 1.5; small (timestamps, error text, hints) 0.875rem; never below 0.8125rem.
- Numerals use `tabular-nums`. No all-caps labels, no letter-spaced eyebrows. Line length of prose/error text <= 70ch.

## 5. Spacing and components
Spacing scale (px): 4, 8, 12, 16, 24, 32, 48. Radius: 6px on controls and rows, 0 on the banner. Transitions <= 120ms on colour only; respect `prefers-reduced-motion`.

**Badge** - inline-flex, min-height 28px, text label + shape glyph: Up (filled circle), Down (triangle/cross), Unknown (hollow circle), Paused (two bars). Label text is always present ("Up", "Down", "Unknown", "Paused").
- Default: grey/green/red border + same-colour text. Loading: "Unknown" badge until first fetch. Error: n/a (state comes from data).

**Banner** - states: all up (success rail), some down (danger rail, "2 of 7 targets are down"), none monitored (grey rail, "No targets are being monitored"), loading ("Checking..." grey rail), monitor unreachable (warning rail plus notice "Cannot reach monitor. Showing last known data from 12:04:31." with `role="alert"`; data stays on screen).

**Target row/card**
- Default: surface, 1px border, 4px left status rail. Hover: border darkens to the muted text colour (rows are not links, so no pointer cursor). Focus-within: none extra; controls carry the focus ring.
- Empty (no targets): a bordered panel "No targets yet." plus, if management enabled, "Add your first target" button; otherwise hint "Add targets to the config file and restart."
- Loading (first fetch): three skeleton rows, static grey blocks (no shimmer).
- Error text for a failed check shown in danger colour prefixed by the word "Error:".

**Buttons** - min-height 44px, min-width 44px, padding 0 16px, 1px border, weight 600. Primary: accent bg. Secondary: surface with accent border and text. Danger (Delete): surface with danger border and text. Hover: bg shifts ~8% toward text colour. Focus-visible: see section 6. Disabled/busy: opacity .6, `aria-busy`, label changes to "Saving...". Delete always opens a native `confirm()` or an inline "Delete <name>? Yes / Cancel" strip.

**Forms** - labels above inputs (always visible, not placeholders), inputs min-height 44px, 16px font (prevents iOS zoom), 1px border. Fields: Name, Type (select http/tcp), URL (http), Host and Port (tcp), Interval seconds (min 5), Expected status (http, default 200). Fields irrelevant to the chosen type are hidden. Hover: border darkens. Error: 2px danger border, message below the field in danger text with a leading "Error:" word, `aria-describedby` link, plus a summary `role="alert"` above the buttons when the server rejects input (show the server's field message). Loading: submit button busy and fields disabled.

**Token prompt** - modal-less inline panel (or `prompt()`): password input labelled "Admin token", Save/Cancel. A wrong token (401) clears sessionStorage and shows "Token rejected. Enter it again."

**Management visibility** - when `management_enabled` is false, no Add form or row controls render at all. Config rows show the text "config (read-only)" in the Source column and no buttons.

## 6. Accessibility
- Visible focus: `:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }` on every interactive element; never `outline:none` without a replacement. Outline colour must be >= 3:1 on both backgrounds.
- Tap targets >= 44x44px for buttons, inputs, selects; >= 8px gap between adjacent targets.
- Status is never colour-only: every state has a text label and a distinct glyph; rows also expose it in text for screen readers. Banner states are written in words.
- Semantics: `<main>`, one `<h1>`, real `<table>` with `<th scope>` on desktop, `<button>` elements (not clickable divs), `<label for>` on all inputs, `lang="en"`.
- Live updates: banner in `aria-live="polite"`; the unreachable notice is `role="alert"`. Refresh must not steal focus or close an open form; skip re-rendering a row being edited.
- Insert all dynamic text via `textContent` (target names, errors); never `innerHTML` with data.
- Contrast >= 4.5:1 for text, >= 3:1 for borders of inputs and focus rings, in both colour schemes. Support 200% zoom and 360px width without horizontal scroll. Honour `prefers-reduced-motion` (no animation is the default, so this is only a guard).

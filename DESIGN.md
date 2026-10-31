---
name: LG HDMI Home
description: A quiet local AV selector following the supplied review design.
colors:
  black: "#000"
  surface: "#121212"
  surface-focus: "#262626"
  ink: "#f2f2f2"
  muted: "#a6a6a6"
  focus: "#f2f2f2"
  line: "#3d3d3d"
typography:
  body:
    fontFamily: '"LG Smart UI", "Segoe UI", sans-serif'
  title:
    fontSize: "clamp(22px,2vw,38px)"
    fontWeight: 400
    letterSpacing: "-.015em"
  label:
    fontSize: "clamp(18px,1.25vw,24px)"
  utility:
    fontSize: "clamp(20px,1.35vw,26px)"
rounded:
  source: "12px"
  tool: "10px"
spacing:
  source-gap: "2.1vw"
  input-gap: "1.8vh"
components:
  source:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.source}"
  source-focus:
    backgroundColor: "{colors.surface-focus}"
    textColor: "{colors.ink}"
    rounded: "{rounded.source}"
  tool:
    textColor: "{colors.muted}"
    rounded: "{rounded.tool}"
  tool-focus:
    backgroundColor: "{colors.surface-focus}"
    textColor: "{colors.ink}"
    rounded: "{rounded.tool}"
---

# Design System: LG HDMI Home

## Overview

**Creative North Star: "The Local AV Console"**

A black OLED canvas, grayscale source controls and white focus follow the owner's supplied review design. The Xbox tile alone carries a forest tint and the supplied console photograph; quiet local date and time replace a visible page title.

This record describes the implemented v1.0.9 dashboard in `dashboard/index.html`, `dashboard/style.css`, `dashboard/app.js` and `dashboard/ports.js`. Browser evidence is `dashboard/artifacts/tv.png` and `mobile.png`. It records implementation, not confirmation of this version's installation or native behavior on the physical TV.

**Key Characteristics:**

- Black canvas, neutral controls and one green Xbox tile.
- Large source targets with a single white focus outline.
- Local console imagery, date and time.
- Configurable ports and explicit activated-control feedback.

## Colors

Neutral grayscale defines controls. Frontmatter preserves shared custom-property values.

### Primary

- **White Focus** (`focus`): border of the single focused control.

### Neutral

- **OLED Black** (`black`): canvas and sleep cover.
- **Quiet Charcoal** (`surface`): resting alternate sources.
- **Awake Charcoal** (`surface-focus`): focused alternate sources and utilities.
- **Soft White** (`ink`): source names and focused utility text.
- **Neutral Gray** (`muted`): supporting copy, date, utilities and symbols.
- **Quiet Line** (`line`): footer keycap outline.

Xbox scopes its resting forest surface (#101411), focused surface (#1c2e22) and focused action tint (#c4e6cb). Blue (#4a90e2) and yellow (#f2c94c) dots identify physical remote shortcuts. These component-specific colors do not recolor neutral controls.

**The Single Focus Rule.** Only the focused control receives focus styling. Pointer entry moves focus; hover must not light a second control.

## Typography

**Body Font:** The installed TV UI stack in frontmatter, with platform fallbacks.

Sentence-case text supports reading at distance. Alternate names use the title role, port numbers the label role, and utilities their responsive size. Xbox emphasis scales from (30px) to (58px), with weight (500), tracking (-.035em) and line height (1.12). Its action scales from (18px) to (28px). Clock digits use tabular numerals. The semantic Inputs heading remains visually hidden.

**The Action Line Rule.** Keep “Switch to HDMI 2” beneath the Xbox name; named alternate ports retain the HDMI number underneath.

## Layout

The landscape shell centers within a maximum width (1920px), with padding (5vh 7.5vw 4.5vh). Date and time align at upper right. The source grid uses columns (1.62fr / 1fr), the frontmatter gap, and maximum height (51vh). Xbox dominates the left; alternate controls occupy three fixed tracks at right. Hiding unused ports preserves remaining tile sizes. With no alternate ports, Xbox spans the source area. Below the inputs, a three-column app row uses the same horizontal grid gap and a 2.6vh top gap; app tiles are 13vh high with a 96px minimum. In portrait, apps become stacked 84px rows.

The masthead places LG Home, Game Optimizer and TV Settings at the left, in that order, with date/time at the right. Buttons and clock share font size, line height and a height of `calc(1.2em + 24px)`; icons scale with that type. Tool focus does not scale, preserving alignment. At widths below 1200px the header wraps; in portrait the tools wrap above the right-aligned clock at a shared 18px size. Footer guidance rests at the shell bottom. In portrait, the page scrolls, sources stack with an (18px) gap, Xbox has minimum height (310px), and alternate rows measure (92px).

## Elevation & Depth

There are no shadows. Tonal focus changes, a white outline and small scale changes communicate selection. Xbox carries a faint diagonal white gradient within its forest surface. Unactivated controls dim to opacity (.45) during launch while the activated control stays bright; idle shell opacity is (.22).

The focused Xbox state uses a dark green base (#0d1b12) with a softer lighter-green radial wash originating at the top-right corner and fading to transparent at 65%. The resting gradient is retained.

**The Flat Console Rule.** Use surface tone, outlines and restrained focus scaling for hierarchy; keep controls shadow-free.

## Shapes

Sources use the source radius; utilities use the tool radius. Both reserve a transparent border (3px) for focus. Xbox focus scales to (1.02), alternate focus to (1.035), while utility focus retains its size. Outline symbols use rounded caps and joins with stroke (1.7). Back uses a compact outlined keycap with radius (5px). Shortcut dots are circular.

## Components

### Source controls

Xbox contains the supplied local transparent photograph (`dashboard/xsx.png`), device name and HDMI 2 action. Alternate ports default to a plain HDMI number with no icon or secondary line. A configured name becomes the main label, its HDMI number moves underneath, and a configured port, PC, controller or media icon may appear. Unused ports are hidden and skipped by navigation. Configuration lives in `dashboard/ports.js`; HDMI 2 remains Xbox.

Focus changes fill, border, text and icon colors immediately. Source scale alone animates over 80ms with `cubic-bezier(.16,1,.3,1)` for a quicker initial response. Pointer entry moves actual focus. Activation replaces status text with “Switching…” or “Opening…”; Xbox states its destination. Activated status pulses over (1.1s), then restores when launch ends. Focus does not claim activation or connection.

### Utility navigation

The left tool group compensates for its button padding, border and home-icon inset, aligning the visible home mark with the source grid. The right clock aligns with the grid's opposite edge.

Tool icons share a 1.15em frame. The gear's wider drawing uses a padded SVG viewBox and compensating stroke width so its visible footprint matches the home/controller marks.

LG Home, Game Optimizer and TV Settings use text-and-icon buttons in the upper-left masthead with no resting fill. Focus reveals charcoal fill, white border and white text. Blue and yellow dots link Settings and Game Optimizer to remote shortcuts. Up from Xbox reaches LG Home; left/right navigates the tools, and Down returns to sources. Native launch and stock-Home recovery paths remain application behavior; this document does not assert their physical-TV verification.

### App launch tiles

Apple TV, YouTube and Browser use neutral surfaces, authored outline symbols and explicit names. White focus borders and charcoal fills match the HDMI controls; no extra focus scaling is added. Busy state and error handling use the shared launch mechanism. Labels use `clamp(22px,1.65vw,32px)`. Down from Xbox enters Apple TV, Left/Right moves across apps, and Up returns to the corresponding source. App IDs are from the saved TV inventory, not a live discovery service.

Apple TV and YouTube use actual brand path geometry rendered without fill, with optical stroke/viewport adjustments. Browser retains the authored globe. These remain monochrome at rest and white on focus; see `dashboard/BRAND-ASSETS.md` for provenance.

### Clock and remote guidance

Local date and 24-hour time occupy the masthead. Updates align to each minute and pause while hidden. Muted footer guidance reads “Back returns to Xbox,” with Back in an outlined keycap. Initial and resumed focus goes to Xbox; D-pad navigation follows visible ports. Back requests Xbox.

### Status notice

A centered bottom notice carries preview and failure messages. Its local inverse treatment uses background (#e6eee8), dark text (#142119), radius (8px) and padding (18px 28px). Preview mode visibly labels simulated controls.

### Idle and motion states

Shell opacity transitions over (200ms ease-out). Timers dim at (45 seconds) and cover at (120 seconds); first wake interaction is consumed. Reduced motion disables transitions, animation and focus scaling. Idle timers pause while hidden. Native launch timeouts and recovery remain intact.

## Do's and Don'ts

### Do:

- **Do** preserve grayscale controls, white focus and the green Xbox exception.
- **Do** use the supplied local Xbox photograph and real local date and time.
- **Do** preserve visible focus, busy labels and reduced-motion behavior.
- **Do** keep named and unused ports configurable without changing destinations.

### Don't:

- **Don't** imply live HDMI connection or signal status.
- **Don't** use hover styling that creates a second highlighted control.
- **Don't** confuse browser preview or package build with verified physical TV deployment.
- **Don't** turn shortcut dots or transient notice colors into a broader accent palette.

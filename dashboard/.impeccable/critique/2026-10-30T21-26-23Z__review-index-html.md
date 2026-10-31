---
target: review TV dashboard
total_score: 28
p0_count: 0
p1_count: 2
timestamp: 2026-10-30T21-26-23Z
slug: review-index-html
---
# Critique: review/index.html (HDMI Home review build)

## Design Health Score: 28/40 (Good, low end)
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Busy state good; no current-input or connected-port indication |
| 2 | Match system / real world | 3 | ↗ is a web external-link glyph; port icon reads as inbox tray |
| 3 | User control and freedom | 3 | Back launches HDMI2 rather than dismissing; repeat OK during 8 s busy lock silently ignored |
| 4 | Consistency and standards | 2 | Two focus vocabularies (mint/green vs white/grey), 3px vs 2px rings |
| 5 | Error prevention | 3 | Good guards; first OK in dimmed idle launches with faint focus |
| 6 | Recognition rather than recall | 3 | Colour dots explained only via title= (invisible on TV) |
| 7 | Flexibility and efficiency | 3 | No number-key (1-4) direct input shortcuts |
| 8 | Aesthetic and minimalist design | 3 | Top band holds no choices; green tint against brief |
| 9 | Error recovery | 3 | Clear copy, but near-white toast is loudest element |
| 10 | Help and documentation | 2 | No legend for colour dots; port naming only via ports.js |

## Anti-patterns
LLM: mostly passes; second-order category reflex (Xbox → tinted green), identical HDMI card trio in default config, decorative sheen + ↗ arrows. Detector: `impeccable detect` clean (0 findings). Overlay not run (live config missing; page CSP blocks external script).

## Priority issues
- [P1] Green accent system against brief + two focus styles → one neutral OKLCH token set, single 3px ring (quieter, polish)
- [P1] :hover styled as :focus can show two focused elements with Magic Remote → focus-only styling (harden)
- [P2] Port tiles stretch (1fr rows), no device/current info → fixed row height, Xbox spans when no ports (layout)
- [P2] Top band (h1 + 50px clock) not a choice, competes with Xbox title → hide h1, smaller muted clock (distill)
- [P2] Remote-key dots cryptic, may not exist on MR22GA remote → key glyph legend or remove (clarify)

## Persona red flags
- Couch owner (project persona): from 3 m, two lit tiles possible after pointer use; colour dots read as status LEDs.
- Jordan (first-timer / guest): unnamed HDMI 1/3/4 give no hint which device; ↗ suggests leaving to a web page.
- Alex (power user): no number-key direct input; repeat presses during switching do nothing with no feedback.

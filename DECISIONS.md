# Decisions

The settled decisions of this project, one entry each: what the operator decided, and every
deviation from a CommonShared rule. Append; never rewrite an entry. A change of mind is a new
entry that replaces the old one (set the old one's status to `replaced` and add `Replaced by`).
Elsewhere, cite the id (`/* design: D-001 */`, an `acceptRules` reason of `"D-001"`, "(D-001)"
after a line in DESIGN.md or AGENTS.md) instead of restating the decision.
Format and checks: CommonShared docs/09 §8, `templates/scripts/decisions.mjs`.

## D-001 Captured TV data stays byte for byte — active
- Date: 2026-11-26
- By: operator
- Rule: core:lf-everywhere-via-gitattributes-text-auto — deviates (captured files are `-text`)
- Intent: inventories, memory reports, the stock Home layout and run reports remain exact evidence of what the TV and launcher produced, so a later diff or hash never reflects our own rewriting
- Decision: these files are marked `-text` in `.gitattributes` and never edited, normalised or re-encoded (their BOM and line endings stay); new runs write UTF-8 through `tv-report.ps1`
- Revisit when: a capture is replaced by a fresh run from the TV

## D-002 Viewport-relative spacing for the 10-foot dashboard — active
- Date: 2026-11-26
- By: operator
- Rule: ui:spacing-on-4px-steps-2-4 — deviates
- Intent: the dashboard fills a 1920×1080 TV seen from the sofa and scales with the panel, not with a reader's root font size
- Decision: spacing, gaps and type sizes use `vw`/`vh` and `clamp()` as recorded in DESIGN.md; radii are the DESIGN.md `rounded` values (12px sources, 10px tools)
- Revisit when: the dashboard targets a non-TV screen as its main surface

## D-003 Forest gradient on the Xbox tile — active
- Date: 2026-11-26
- By: operator
- Rule: design:no-decorative-gradients-gradient-text-glows — deviates
- Intent: the primary source reads as the one distinct, lit tile on a black OLED canvas
- Decision: the faint resting diagonal gradient and the focused top-right radial wash described in DESIGN.md "Elevation & Depth"
- Revisit when: the Xbox tile stops being the primary tile

## D-004 D-pad focus is a 3px border on :focus — active
- Date: 2026-11-26
- By: operator
- Rule: ui:one-global-focus-visible-2px-solid — deviates
- Intent: exactly one control is visibly focused at all times on a remote-driven TV, where every focus change is keyboard (D-pad) focus
- Decision: each control reserves a transparent 3px border that turns white on `:focus` (DESIGN.md "The Single Focus Rule"); `outline:none` is set only where that border replaces it
- Revisit when: the dashboard gets a pointer-first surface

## D-005 No text selection on the dashboard — active
- Date: 2026-11-26
- By: operator
- Rule: interaction:user-select-none-on-the-canvas — deviates
- Intent: the Magic Remote pointer never starts a text selection on a full-screen kiosk page
- Decision: `user-select: none` on `body`; the page has no input fields to opt back in
- Revisit when: a text field is added to the dashboard

## D-006 Function size held by a ratchet, not a refactor — active
- Date: 2026-11-26
- By: operator
- Rule: code:keep-functions-80-lines-and-cyclomatic — deviates
- Intent: the TV-side scripts keep their reviewed, TV-verified behaviour; size does not grow from here
- Decision: `scripts/check-code-size.mjs` against the committed `code-size-baseline.json`; existing long functions stay until a change touches them and can be re-verified on the TV
- Revisit when: a script is next changed and re-run on the TV

## D-007 Agent notes are tracked in AGENTS.md — active
- Date: 2026-11-26
- By: operator
- Rule: core:agents-md-is-canonical-a-tool — follows
- Intent: the agent notes travel with the public repo and stay one canonical file
- Decision: `AGENTS.md` is tracked and canonical; the local, gitignored `CLAUDE.md` only imports it
- Revisit when: the notes need something that must not be public

## D-008 axe-core as a dev-only dependency — active
- Date: 2026-11-26
- By: operator
- Intent: the dashboard gets an automated accessibility and layout scan while the shipped app stays dependency-free
- Decision: `axe-core` in `dashboard/package.json` `devDependencies` only, used by the rendered checks against `preview.mjs`; nothing from `node_modules/` enters the IPK
- Revisit when: the checks no longer need it

## D-009 Focus lifts the HDMI tiles, also when a press focuses them — active
- Date: 2026-11-26
- By: operator
- Rule: interaction:press-feedback-only-paints-colour-opacity — deviates
- Intent: the focused source tile reads as lifted from across the room, whichever way it got focus (D-pad, Magic Remote pointer or a press)
- Decision: the DESIGN.md focus scale (Xbox 1.02, alternate ports 1.035) on `:focus`; a press only adds focus, it has no press style of its own
- Revisit when: a press needs its own feedback, or the operator drops the focus scale

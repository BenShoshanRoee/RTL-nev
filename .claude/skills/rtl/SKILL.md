---
name: rtl
description: Use when touching bidi, text direction, layout mirroring, numerals, money formatting, dates, typography, fonts, Arabic shaping, or any Hebrew/Arabic rendering or string resource. Covers packages/rtl-primitives, packages/pathology, sim/apps/*, res/strings.*.json, and any CSS. Logical properties only, no hardcoded script, golden files, pathology parity.
---

# rtl — rendering discipline

## Rules
- **CSS logical properties only.** `margin-inline-start`, `padding-inline-end`,
  `inset-inline-start`, `text-align: start`, `border-start-start-radius`. Never `left`/`right`
  variants. Check: `rg -n "margin-left|margin-right|padding-left|padding-right|text-align: *(left|right)|\bleft:|\bright:" packages/ sim/` must return only waived files.
- **No hardcoded Hebrew or Arabic in components.** All UI strings from `res/strings.he.json`
  / `res/strings.ar.json`. Check: `rg -n "[\p{Hebrew}\p{Arabic}]" --glob '*.tsx' --glob '*.ts' packages/ sim/` must return nothing outside test/golden files.
  This is what makes Arabic a content swap, not a rewrite.
- **Direction is a parameter.** Read `dir` from context, never assume RTL. LTR must still render.
- **Icons that imply direction** (back, forward, send, chevrons) go through the mirror
  registry. Icons that do not (search, clock, logo) must not mirror.
- **Numbers and money.** Integer minor units in, string out. Numeral system is a parameter
  (Western `0123` / Eastern Arabic-Indic `٠١٢٣`). Isolate numbers and Latin codes with bidi
  isolates (FSI/PDI or `<bdi>`), never with embedding overrides.
- **Mixed-script input** (Latin coupon code inside an RTL field) must round-trip
  unchanged through storage.

## Golden-file tests (required)
- Every bidi / shaping / numeral change ships a golden file in `packages/rtl-primitives/golden/`.
- Hebrew corpus (≥100 strings) is authored by the operator 🔧. Arabic corpus by a native
  speaker 🔧. Never invent golden expectations from documentation.
- Golden test compares resolved visual order / shaped forms, not screenshots.
- Same input, same output, both scripts, both directions.

## Pathology parity
- Every pathology injector must have a **non-pathological baseline** rendering the same
  content correctly, so a task can be run with and without the defect.
- Injectors are deterministic under seed (also apply `determinism`).
- An injector must produce a plausible, production-like defect, not garbage.
- Judges must be able to tell "looked right, stored wrong" from "right" (see `judge`).

## Hebrew vs Arabic
| Aspect | Hebrew | Arabic |
|---|---|---|
| Letter shaping | None; letters are isolated | Contextual: isolated / initial / medial / final |
| Final forms | 5 final letters are distinct code points (ך ם ן ף ץ) | Final form is shaping, same code point |
| Ligatures | None mandatory | Lam-alef mandatory; others font-dependent |
| Numerals | Western only | Western or Eastern Arabic-Indic, varies by country |
| Vowel marks | Niqqud, rare in UI | Harakat, rare in UI |
| Justification | Word spacing | Kashida/tatweel stretching possible |
| Currency minor units | ILS agorot, 1/100 | Varies: 1/100 (SAR, AED, EGP), 1/1000 (KWD, BHD) |
| Address / payment conventions | Israeli survey | Gulf / Levant survey; do not reuse Hebrew distribution |
| Truncation pathology | Cuts characters | Cuts characters AND breaks joining / ligatures |
| Reuses cleanly across both | Bidi resolution, mirroring, logical properties, icon registry, direction-aware components, most injectors | |

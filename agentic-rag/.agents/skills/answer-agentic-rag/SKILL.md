---
name: answer-agentic-rag
description: Answer agentic-rag English product-manual questions from agentic-rag/question.csv using the Markdown manuals and images under agentic-rag/en-manual. Use when Codex needs to search the agentic-rag English manuals, answer one or many manual QA questions, produce v2-compatible answer payloads or submission ret values, align PIC placeholders with image IDs, or maintain long-running manual-question answering work with evidence-grounded internal chain-of-thought.
---

# Answer Agentic Rag

## Overview

Use this skill to answer the 187 English manual questions in `agentic-rag/question.csv` against the 20 cleaned English Markdown manuals in `agentic-rag/en-manual/`. The answer target is the v2 format: a grounded plain-text `content` plus an `images` array whose entries align one-to-one with `<PIC>` placeholders.

## Project Files

- Questions: `agentic-rag/question.csv` with columns `id`, `raw`, `clean`, `lang`; answer the `clean` field.
- Manuals: `agentic-rag/en-manual/*.md`; exclude `手册内容总览.md` from evidence except for routing.
- Overview: `agentic-rag/en-manual/手册内容总览.md`; use it to identify the likely product/manual.
- Images: `agentic-rag/en-manual/插图/*`; answer image IDs are stems only, without path or extension.

## Required Reasoning

Use internal chain-of-thought for every answer. In the private work, explicitly reason through:

1. Which product/manual the question is about.
2. Which sections and search terms can answer it.
3. Whether the question needs multi-hop reasoning across distant sections, such as a control description plus a warning, a component location plus an operation step, or a symptom plus a troubleshooting action.
4. Whether retrieved text is actual answer evidence or only table-of-contents/index noise.
5. Which warnings, limits, quantities, steps, exceptions, and image anchors must be preserved.
6. Whether each selected image truly helps, what visible item or relationship it supports, and which exact adjacent sentence should describe it.

Do not reveal the chain-of-thought, search diary, or scratch notes in the final answer. Output only the requested v2 payload/ret or a concise status summary when the user asks for workflow progress.

## Workflow

1. Load the question by ID or from the user's text. Prefer `clean`; use `raw` only to recover lost punctuation.
2. Route to a likely manual using `手册内容总览.md`, product aliases, and direct corpus search.
3. Search the likely manual first with `rg -n -i`, using nouns, button names, symptoms, quoted phrases, and likely OCR variants. If uncertain, search all `agentic-rag/en-manual/*.md`.
4. Read enough surrounding context with `sed -n` or `nl -ba`; include nearby headings, notes, warnings, and image anchors. Do not answer from the table of contents alone.
5. For multi-hop questions, gather all needed evidence before drafting. Cross-check section relationships instead of merging unrelated snippets.
6. If the answer depends on a figure, control layout, indicator, part label, or step illustration, inspect the referenced image file when possible. Otherwise use the image only if nearby text clearly identifies it.
7. Draft the answer from evidence only. If evidence is insufficient, say the available material does not clearly state the answer; do not invent.
8. Format the final result with the v2 requirements. Read `references/v2-format.md` when writing answers or CSV rows.
9. Self-check before finalizing: answer the exact question, preserve important numbers/units/conditions, avoid unrelated expansion, and ensure `<PIC>` count equals image count in order.

## Routing Hints

Use these aliases to speed up routing, but verify with evidence:

- Yamaha 210FSH 2021: boat, sailing, ship, on board, bimini, livewell, aerator, battery switch, anchor light.
- Yamaha WaveRunner 2005: WaveRunner, jet ski, jetski, personal watercraft, hull ID, engine serial, cruising.
- Canon EOS 20D: camera, Canon, EOS, lens, shutter, AF, metering, flash, DPOF, battery.
- Philips Airfryer: airfryer, air fryer, NutriU, keep warm, preset, fries, first use.
- Hydrabuds ANC: earphones, earbuds, ANC, Bluetooth, multipoint, reset, pairing.
- Instant Pot Duo Crisp: Instant Pot, pressure cooker, air fryer lid, steam release, anti-block shield.
- Motherboard: motherboard, BIOS, CPU, memory, jumper, onboard connector, boot.
- Roomba i5: Roomba, robot vacuum, Home Base, dirt detect, side brush, filter.
- Philips XL490 XL495: phone, handset, base station, landline, answering machine, call log.
- Yamaha Snowmobile: snowmobile, brake lever, V-belt, track, ski alignment, uphill/downhill.
- Bosch Microwave: microwave, over-the-range, auto defrost, grease filter, charcoal filter.
- Color Television: TV, television, antenna, channel, captions, game, key lock.
- Outdoor Grill: grill, LP tank, burner, regulator, leak test, indirect cooking.
- Nespresso CitiZ D111: Nespresso, CitiZ, coffee, espresso, Lungo, descaling, water volume.
- Philips Sonicare Prestige: toothbrush, Sonicare, BrushSync, SenseIQ, intensity, travel case.
- Color E-Reader: e-reader, ebook, Micro SD, firmware, music, video, photo.
- Twin-Tub Washing Machine: washing machine, twin-tub, wash timer, spin dry, drain hose.
- Brother Safety Guide: Brother, fax, product safety, warning label, power cord, Canada statement.
- MV Camera: Meraki, MV camera, Dashboard, firewall, T-rail, LED.
- Toro Z Master 4000: Toro, mower, Z Master, roll bar, brake, blade, deck, belt, hydraulic.

## Evidence Standards

- Prefer exact procedure sections, troubleshooting tables, warning blocks, specifications, and labeled figures.
- For long manuals, pinpoint the exact section before answering. Use headings, repeated searches, nearby captions, and cross-references to avoid broad or approximate answers.
- Handle multi-hop questions by connecting evidence explicitly in the private reasoning: identify the relevant part, then its operation, condition, warning, or consequence.
- Include critical safety warnings only when directly relevant to the question.
- Preserve model-specific names, button labels, switch positions, wait times, capacities, temperatures, units, and direction words.
- Resolve ambiguous product words carefully. For example, "boat" normally means Yamaha 210FSH, while "jetski" means Yamaha WaveRunner.
- Treat malformed user wording as a retrieval clue, not as a reason to answer vaguely.
- Avoid using images as decoration. Each image must explain a nearby sentence, state, part, or step.
- Keep image and text tightly coupled. If an image shows labels, controls, parts, positions, arrows, or a sequence, the nearby text must name and explain the relevant visible item instead of adding a disconnected "see image" style placeholder.
- Write concise, high-density answers. Prefer short direct sentences, but keep key evidence, conditions, and warnings.
- Organize answers logically: conclusion first, then ordered steps or grouped points, then only directly relevant cautions or exceptions.

## Long-Running Work

For batches, keep a progress artifact outside the source manuals, such as `agentic-rag/tmp/answers/`, with completed IDs, evidence notes, and the generated `ret`. Do not edit the manuals or question CSV while answering unless the user explicitly asks.

When resuming, first inspect the progress artifact and skip completed IDs. Re-open the source evidence for any answer that needs revision instead of trusting old notes blindly.

## References

- `references/v2-format.md`: exact v2 answer payload, CSV `ret`, style, image, and validation requirements. Read it before producing final answer rows.

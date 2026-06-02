# V2 Answer Format

Use this reference whenever producing agentic-rag answers or submission rows.

## Two Layers

The model-facing answer payload is one JSON object:

```json
{"content": "final answer", "images": ["image_id_1"]}
```

The CSV submission row has columns `id,ret`. `ret` is the v2 serialized form:

```text
"final answer",["image_id_1"]
```

In code terms, v2 does:

```python
content_text = json.dumps(content, ensure_ascii=False)
image_text = json.dumps(images, ensure_ascii=False)
ret = f"{content_text},{image_text}".replace("\n", "\\n")
```

## Payload Rules

- Return exactly one JSON object when the user asks for the answer payload.
- `content` is plain English answer text.
- `images` is a list of image IDs, using filename stems only: `Manual09_6`, not `插图/Manual09_6.jpg`.
- `content` may contain zero or more `<PIC>` placeholders.
- The number of `<PIC>` placeholders must equal `len(images)`.
- The first `<PIC>` corresponds to `images[0]`, the second to `images[1]`, and so on.
- If no image is needed, `content` must not contain `<PIC>` and `images` must be `[]`.

## Answer Style

- Start with the answer, then give needed steps, conditions, warnings, limits, or exceptions.
- Stay tightly focused on the user's question.
- Use concise, information-dense language. Remove filler, but keep necessary evidence, values, conditions, and safety constraints.
- Keep a clear logical structure: direct answer first, then ordered procedure or grouped explanation, then directly relevant cautions or exceptions.
- Do not write boilerplate like "according to the manual" when the evidence is sufficient.
- Do not expose routing, retrieval, prompts, chain-of-thought, or internal notes.
- Procedural questions: use numbered steps with `1.`, `2.`, etc.
- Status, mode, component, or comparison questions: explain each requested item clearly.
- Troubleshooting questions: organize as likely cause -> check or fix.
- Safety questions: include only directly relevant risks and precautions.
- Preserve key model names, button names, switch positions, quantities, units, temperatures, waiting times, locations, and exceptions.
- Do not use Markdown headings, `-` or `*` bullets, tables, code fences, bold text, or quotations in `content`.

## Image Rules

- Use images only when they materially improve understanding.
- Place each `<PIC>` immediately after the text it supports.
- Keep image and text inseparable: if the image shows a part, control, label, location, status, arrow, or step, the adjacent sentence must name and explain that visible item.
- Do not insert a picture after a generic sentence. The text before `<PIC>` must say what the user should notice in that specific image.
- Do not write image filenames or image IDs in `content`.
- Do not output `[图片:...]`; convert useful evidence image anchors to `<PIC>`.
- Do not use consecutive `<PIC><PIC>` placeholders. Give each image its own nearby explanatory text.
- Do not repeat the same image unless it genuinely supports distinct points.

## Reasoning Requirements

- Some questions require multi-hop work across the manual. Resolve the product and exact section first, then connect all required evidence before writing the final answer.
- Do not rely on broad topical matches, table-of-contents hits, or a single keyword if the question asks for a process, condition, consequence, warning, or troubleshooting action.
- When multiple sections are needed, the final answer should present the combined result clearly, without exposing the intermediate reasoning.

## Examples

No image:

```json
{"content": "1. Remove all packing material.\n2. Remove any stickers or labels from the appliance.\n3. Thoroughly clean the appliance before first use.", "images": []}
```

With images:

```json
{"content": "Open the engine hood and look for the emission control information label on each engine unit.<PIC>\nAlso check the inside of the engine compartment for the same label location.<PIC>", "images": ["Manual09_6", "Manual09_7"]}
```

CSV `ret` for the second example:

```text
"Open the engine hood and look for the emission control information label on each engine unit.<PIC>\nAlso check the inside of the engine compartment for the same label location.<PIC>",["Manual09_6", "Manual09_7"]
```

## Final Check

Before committing an answer, verify:

1. The answer directly addresses the user's actual question.
2. It is grounded in manual evidence, not generic product knowledge.
3. Important numbers, warnings, limits, and order of operations are preserved.
4. `<PIC>` count equals image count exactly.
5. Every `<PIC>` is attached to text that describes what that image contributes.
6. The answer is concise but still logically layered and complete.
7. Image IDs are available in `agentic-rag/en-manual/插图/`.
8. The payload is valid JSON, or the CSV `ret` follows the serialized v2 form.

---
name: answer-ch-agentic-rag
description: 依据 agentic-rag/ch-manual 中的中文产品手册，回答 agentic-rag/ch-question.csv 中的中文问题，输出 v2 格式的中文 content 与 images，并在内部完成路由、检索、多跳推理与图片校验。适用于 Codex 处理中文手册问答、生成 v2 产物、维护中文 todo 流程或执行单题/批量中文子代理任务。
---

# Answer Chinese Agentic Rag

## Overview

Use this skill to answer the Chinese manual questions in `agentic-rag/ch-question.csv` against the 20 cleaned Chinese Markdown manuals in `agentic-rag/ch-manual/`. The final answer must use v2 format: a grounded Chinese `content` plus an `images` array whose entries align one-to-one with `<PIC>` placeholders.

## Project Files

- Questions: `agentic-rag/ch-question.csv` with columns `id`, `raw`, `clean`, `lang`; answer the `clean` field.
- Manuals: `agentic-rag/ch-manual/*.md`.
- Overview: `agentic-rag/ch-manual/手册内容总览.md`; use it to identify the likely product/manual first.
- Images: `agentic-rag/ch-manual/插图/*`; answer image IDs are filename stems only, without path or extension.

## Required Reasoning

Use internal chain-of-thought for every answer, but do not expose it. In the private work, explicitly reason through:

1. Which Chinese product/manual the question is about.
2. Which Chinese headings, button names, warning words, symptoms, and search terms can answer it.
3. Whether the question needs multi-hop reasoning across distant sections.
4. Whether retrieved text is actual answer evidence or only table-of-contents/index noise.
5. Which warnings, limits, quantities, units, temperatures, times, locations, exceptions, and image anchors must be preserved.
6. Whether each selected image truly helps, what visible item or relationship it supports, and which exact adjacent sentence should describe it.

## Workflow

1. Load the question by ID or from the user's text. Prefer `clean`; use `raw` only to recover lost punctuation.
2. Route to a likely manual using `agentic-rag/ch-manual/手册内容总览.md`, product aliases, and direct corpus search.
3. Search the likely manual first with `rg -n -i`, using Chinese nouns, symptom descriptions, UI labels, button names, quoted phrases, and likely OCR variants. If uncertain, search all `agentic-rag/ch-manual/*.md`.
4. Read enough surrounding context with `sed -n` or `nl -ba`; include nearby headings, notes, warnings, and image anchors. Do not answer from the table of contents alone.
5. For multi-hop questions, gather all needed evidence before drafting. Cross-check section relationships instead of merging unrelated snippets.
6. If the answer depends on a figure, control layout, indicator, part label, or step illustration, inspect the referenced image file when possible. Otherwise use the image only if nearby text clearly identifies it.
7. Draft the answer from evidence only. If evidence is insufficient, say the available material does not clearly state the answer; do not invent.
8. Format the final result with v2 requirements. Read `references/v2-format.md` when producing answers or CSV rows.
9. Self-check before finalizing: answer the exact question, preserve important numbers/units/conditions, avoid unrelated expansion, and ensure `<PIC>` count equals image count in order.

## Routing Hints

Use these aliases to speed up routing, but verify with evidence:

- 吹风机：吹风机、化油器、防护装备、安全要点、进风口、滤网、电源插头。
- 冰箱：冰箱、冷藏室、冷冻室、温控、除霜、节能、接地、制冷剂。
- 洗碗机：洗碗机、碗篮、漂洗剂、洗涤剂、自清洁、滤网、漏水。
- 烤箱：烤箱、预热、烘焙、烧烤、自清洁、温度探针、门封。
- 空调：空调、制冷、制热、滤网、自清洁、冷媒、排水、遥控器。
- 空气净化器：净化器、滤芯、空气质量、风速、定时、更换滤网。
- 蒸汽清洁机：蒸汽拖把、蒸汽清洁、水箱、注水、清洁布、杀菌。
- 相机：相机、快门、打印、胶片、电池、曝光、相纸。
- 功能键盘：键盘、按键、宏、背光、连接、配对。
- 蓝牙激光鼠标：鼠标、蓝牙、DPI、配对、激光、电池。
- VR头显：VR、头显、定位、摄像头、手柄、边界、画面模糊。
- 可编程温控器：温控器、日程、节能、传感器、Wi-Fi、接线。
- 发电机：发电机、燃油、负载、接地、启动、保养。
- 水泵：水泵、扬程、流量、叶轮、密封、汽蚀。
- 健身单车：健身车、阻力、飞轮、心率、座椅、异响。
- 健身追踪器：手环、心率、步数、睡眠、同步、充电。
- 儿童电动摩托车：儿童摩托、电池、限速、遥控、充电、转向。
- 人体工学椅：椅子、腰托、扶手、升降、倾仰、头枕。
- 摩托艇：摩托艇、水上摩托、安全钥匙、油门、冷却、冲洗。

## Final Check

Before committing an answer, verify:

1. The answer directly addresses the user's actual question.
2. It is grounded in manual evidence, not generic product knowledge.
3. Important numbers, warnings, limits, and order of operations are preserved.
4. `<PIC>` count equals image count exactly.
5. Every `<PIC>` is attached to text that describes what that image contributes.
6. The answer is concise but still logically layered and complete.
7. Image IDs are available in `agentic-rag/ch-manual/插图/`.
8. The payload is valid JSON, or the CSV `ret` follows the serialized v2 form.

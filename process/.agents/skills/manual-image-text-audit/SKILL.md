---
name: manual-image-text-audit
description: Generic workflow for auditing and cleaning instruction-manual or product-handbook Markdown files. Use when the user asks to clean, organize, audit, or fix a manual Markdown file for image/text mismatch, unclear Markdown structure, OCR artifacts, misplaced captions, repeated page headers, or unsafe edits. This skill requires actually inspecting every referenced image against its nearby text and preserving all images/text unless the user explicitly approves removal.
---

# Manual Image/Text Audit

## Core Rule

Inspect the images, not just filenames. "Image/text mismatch" means a referenced image does not match the title, paragraph, list item, procedure step, table label, or note around it. Do not treat "belongs to the same manual" as sufficient.

Do not delete images or text unless the user explicitly approves. Prefer moving misplaced text, moving a misplaced image, converting repeated page headers to comments, or adding a short blockquote explanation when a crop is incomplete.

## Workflow

1. Scope only the requested Markdown file (or the set the user specifies) unless the user asks for comparison.
2. Read the whole file and extract all headings and image references.
3. Run `scripts/extract_image_context.py <markdown>` to get each image with nearby heading, previous text, and next text.
4. Run `scripts/make_contact_sheet.py <markdown> --output /tmp/<name>.jpg`, then inspect the contact sheet with the image viewer. For dense tables or small UI screenshots, generate subset sheets or view individual images at original detail.
5. Audit every image:
   - Identify what the image actually shows.
   - Compare it with the closest heading and the text immediately before and after the image.
   - Check whether a note/recommended amount/caption below the image belongs to the previous image or the next section.
   - Check whether multi-image procedures are attached to the correct numbered steps.
   - Check whether repeated page headers were converted into misleading Markdown headings.
6. Make only safe, non-destructive edits:
   - Fix Markdown heading levels and split run-on sections.
   - Move misplaced text or images to the correct local section.
   - Repair high-confidence OCR artifacts that do not alter meaning.
   - Convert repeated source page headers into HTML comments when they would confuse structure.
   - Add a blockquote under an incomplete/cropped image to explain what the image actually contains.
7. Stop and ask the user before deleting content, replacing an image, dropping a page fragment, or rewriting legal/warranty/safety text where the intended wording is uncertain.
8. Validate:
   - All original image references are still present unless the user approved a removal.
   - All image links resolve.
   - The heading outline is coherent.
   - Known OCR search patterns do not reveal obvious remaining high-confidence issues.
9. Summarize concrete fixes and unresolved issues. Mention any areas intentionally left untouched because they need user confirmation.

## Image Audit Heuristics

Common mismatch patterns to watch for:

- A procedure image is under the right feature title, but the note below it belongs to the previous feature.
- A "recommended amounts" table is separated from the feature it describes.
- A maintenance illustration is placed after the wrong numbered step.
- A repeated page header (e.g. a product name or section title that appears on every printed page) appears mid-section and is mistaken for a new Markdown heading.
- A cropped table/image lacks enough visible text; add a blockquote explanation rather than guessing silently.
- A symbol/icon list may be text-before-image or image-before-text. Infer the pattern from the whole list before moving descriptions.

## OCR Cleanup Boundaries

Safe to fix when obvious: missing spaces between words, split words (e.g. `EX CESSIVE` -> `EXCESSIVE`), malformed headings, broken list nesting, units stuck to numbers (e.g. `20cm` -> `20 cm`), and punctuation that restores sentence boundaries. See `references/ocr-patterns.md` for discovery patterns.

Ask first or leave noted when uncertain: warranty/legal paragraphs, model-specific claims, safety warnings whose exact wording cannot be inferred, or any text where the OCR could have multiple valid readings.

## Scripts

- `scripts/extract_image_context.py`: print every image reference with nearest heading and surrounding non-empty lines.
- `scripts/make_contact_sheet.py`: create a labeled contact sheet for all or selected images in a Markdown file.

Use scripts as aids only; the final judgment must come from visually inspecting the images and reading the surrounding text.

# Manual Image/Text Audit TODO

Use project skill: `.codex/skills/manual-image-text-audit/SKILL.md`.

Core constraints:
- Scope only `v2/data/en-manual/*.md` unless the user explicitly expands scope.
- Inspect every referenced image visually against its nearby title, paragraph, list item, step, table label, caption, and notes.
- Do not delete images or text without explicit user approval.
- Prefer moving misplaced text/images, fixing heading levels, converting repeated page headers to HTML comments, adding concise blockquote explanations for incomplete crops, and repairing high-confidence OCR artifacts.
- Ask the user before replacing images, dropping fragments, or rewriting uncertain safety/legal/warranty text.

Per-manual checklist:
- [ ] Read full Markdown and heading outline.
- [ ] Run `extract_image_context.py` and review every image's neighboring text.
- [ ] Generate contact sheet(s) with `make_contact_sheet.py`.
- [ ] Visually inspect every image, including dense tables at larger size when needed.
- [ ] Identify image/text mismatches, misplaced notes/captions, wrong procedure-step placement, repeated page headers, unclear heading hierarchy, and high-confidence OCR artifacts.
- [ ] Apply only non-destructive fixes.
- [ ] Validate all image links still resolve and image count is unchanged unless approved.
- [ ] Update this TODO status and note unresolved issues.

Completed in this session:
- [x] `Brother Safety Guide.md`
  - Added explanatory blockquote for cropped font-style reference image.
  - Cleaned structure/OCR issues and validated image links.
- [x] `Bosch Microwave.md`
  - Cleaned structure/OCR issues.
  - Re-audited image/text alignment per image.
  - Fixed confirmed mismatches around Potato/Vegetable sensor notes and Cooktop Light image placement.
  - Left warranty long paragraph OCR residue as unresolved because legal wording is uncertain.
- [x] `Canon EOS 20D.md`
  - Visually checked all 324 image references against nearby text using contact sheets and image contexts.
  - Found no confirmed local image/text mismatches requiring image or text movement.
  - Cleaned the Markdown outline by demoting OCR-promoted procedure steps and Custom Function option values.
  - Fixed high-confidence OCR spacing/label issues such as AF-assist wording, center AF point spacing, and C.Fn option spacing.
  - Validated that all image references are still present in the same order and all links resolve.
- [x] `Color E-Reader.md`
  - Visually checked all 22 image references against nearby text.
  - Found no confirmed local image/text mismatches requiring image or text movement.
  - Split dense OCR paragraphs into readable lists/sections, including front-view numbered parts, eBook controls, music/video/photo controls, settings, specifications, and troubleshooting.
  - Restored `NAVIGATION BUTTON VIEW` as the heading for the navigation button image instead of leaving it glued to the front-view description.
  - Left an OCR note for an incomplete charging sentence rather than guessing missing content.
  - Validated that all image references are still present and all links resolve.
- [x] `Color Television.md`
  - Visually checked all 52 image references against nearby text.
  - Cleaned remote-control/front-panel descriptions and grouped battery/front-panel notes under clear headings.
  - Fixed one confirmed local context issue by moving the `Connecting Component DVD Inputs` heading before the component-DVD notes, so they no longer read as part of the preceding VCR-recording image.
  - Cleaned high-confidence OCR spacing/labels throughout channel setup, timers, picture/sound settings, closed captions, antenna, and external-equipment sections.
  - Validated that all image references are still present and all links resolve.
- [x] `Hydrabuds ANC.md`
  - Visually checked all 21 image references against nearby text, including small gesture/reset diagrams at original size.
  - Found no confirmed local image/text mismatches and no structure cleanup needed.
  - Validated that all image references are present and all links resolve.
- [x] `Instant Pot Duo Crisp.md`
  - Visually checked all 46 image references against nearby text.
  - Found no confirmed local image/text mismatches requiring deletion or image replacement.
  - Added concise blockquote explanations under the clustered air-frying overview/reference images so they do not read as step images.
  - Added concise blockquote explanations under the two troubleshooting table screenshots, noting the second image overlaps with the first at the top.
  - Validated that all image references are still present and all links resolve.
- [x] `MV Camera.md`
  - Visually checked all 17 image references against nearby text.
  - Added concise blockquote explanations for the two package-hardware images so they do not read as unlabeled decorative images.
  - Cleaned wall-mounting and T-rail OCR around procedure steps, including misplaced wall-template text, unit spacing, punctuation, and Dashboard path formatting.
  - Validated that all image references are still present and all links resolve.
- [x] `Motherboard.md`
  - Visually checked all 99 image references against nearby text using full and segmented contact sheets.
  - Fixed confirmed local context issues around specifications-summary tables, thermal/front-panel audio connector headings, ROG/USB 3.0 connector headings, and the Advanced Mode screenshot/note icon ordering.
  - Added concise blockquote explanations for icon-only caution/note images so they do not read as procedure diagrams or screenshots.
  - Cleaned high-confidence OCR around DIMM/MHz/PCIe wording, BIOS paths, connector descriptions, and BIOS setup text.
  - Validated that all image references are still present and all links resolve.
  - Left a few OCR residues in FCC/compliance text untouched because legal/compliance wording should not be rewritten without confirmation.
- [x] `Nespresso CitiZ D111.md`
  - Visually checked all 50 image references against nearby text using a contact sheet and image-context extraction.
  - Confirmed that the duplicated `Manual07_19.jpg` reference is intentional reuse for blinking/steady button status in two procedures.
  - Cleaned the Markdown structure around Energy Saving Mode, Programming the Water Volume, Emptying the System, Descaling, Cleaning, Troubleshooting, and Contact sections.
  - Added a concise blockquote explanation for the cropped safety-label key image.
  - Cleaned high-confidence OCR such as coffee/fill/first/off/LEDs/electrical/Troubleshooting and related heading casing.
  - Validated that all image references are still present and all links resolve.
  - Left incomplete brand-name fragments untouched where the missing words could not be reliably inferred from local context.
- [x] `Outdoor Grill.md`
  - Re-audited all 81 image references from scratch after the interrupted prior run, using contact sheets, image-context extraction, and larger original-image checks for parts tables, troubleshooting tables, and assembly diagrams.
  - Confirmed the local image/text alignment, including the previously suspicious main-burner match-lighting image placement and side-burner assembly step 10 image order.
  - Cleaned the Markdown structure around the cover material, Product Record, Warranty, light-operation section, Parts List, Parts Diagram, Assembly steps, Emergencies, and Troubleshooting tables.
  - Added or kept concise blockquote explanations only where the source image is a cropped warning/caution label or an image-only assembly step reference.
  - Repaired high-confidence OCR and punctuation issues across LP tank safety, leak testing, lighting, burner-cleaning, food-safety, halogen-light, and assembly text, and restored a few clearly visible instructions from the assembly figures.
  - Validated that all 81 image references remain present and all links resolve.
- [x] `Philips Airfryer.md`
  - Visually checked all 36 image references against nearby text using image-context extraction, a contact sheet, and larger original-image checks for the Wi-Fi status table and troubleshooting/cleaning tables.
  - Confirmed that the local image placement is correct, including moving the Wi-Fi indicator table under `The NutriU App` rather than leaving it in `General description`.
  - Cleaned the Markdown structure around the app setup, voice control, food table, airfrying steps, keep-warm mode, presets, NutriU recipe start, storage, software updates, and troubleshooting sections.
  - Repaired high-confidence OCR issues such as broken headings, app naming, and dense run-on procedure text.
  - Validated that all 36 image references remain present and all links resolve.
- [x] `Philips Sonicare Prestige.md`
  - Visually checked all 35 image references against nearby text using a contact sheet plus larger original-image checks for the battery-status tables and handle-control indicator figures.
  - Confirmed that the local image placement is correct; the main problems were OCR run-on text and repeated page headers, not image/text mismatches.
  - Converted misleading page headers into HTML comments and rebuilt the Markdown structure for safeguards, intended use, box contents, app setup, brushing instructions, feature descriptions, handle-based feature toggles, charging, battery status, cleaning, storage, and disposal.
  - Repaired high-confidence OCR issues such as broken numbering, missing spaces, app/feature naming, `0°C` temperature text, and `MHz`/`dBm`/`GHz` regulatory unit spacing while keeping the regulatory/compliance content substantively intact.
  - Validated that all 35 image references remain present and all links resolve.
- [x] `Roomba i5.md`
  - Visually checked all 23 image references against nearby text using image-context extraction, a contact sheet, and larger original-image checks for the labeled top-view, button/indicator, and virtual-wall figures.
  - Found no confirmed image/text misplacement; the manual was already structurally clean.
  - Added the image-labeled parts that were missing from nearby lists, including `iAdapt Localization Camera`, `Handle`, and the button-panel status indicators shown in the buttons/indicators figure.
  - Validated that all 23 image references remain present and all links resolve.
- [x] `Twin-Tub Washing Machine.md`
  - Visually checked all 38 image references against nearby text using image-context extraction, a contact sheet, and larger original-image checks for the combined additional-rinse panel, parts diagram, washing-time table, and troubleshooting table.
  - Confirmed the image order is locally correct; the main issues were OCR structure problems and one meaningful text omission where the `ADDITIONAL RINSE` section had been reduced to a title plus image only.
  - Reconstructed the six `ADDITIONAL RINSE` steps from the source figure, cleaned high-confidence OCR in overflow-rinse and filter-cleaning instructions, normalized heading levels, and added concise blockquote notes where a combined panel or labeled catch needed clarification.
  - Validated that all 38 image references remain present and all links resolve.
- [x] `Philips XL490 XL495.md`
  - Visually checked all 62 image references against nearby text using image-context extraction, a contact sheet, and larger original-image checks for the handset/base overview diagrams, note/tip icon panels, LED status tables, remote-access command table, and battery-removal figure.
  - Found no confirmed local image/text misplacement; the dominant issue was severe OCR structure corruption, especially table-of-contents debris, numbered callout circles promoted to headings, and note/tip icon panels treated as section titles.
  - Rebuilt the front half of the manual into a coherent outline, including table of contents, safety sections, phone/base overview, setup, charging, calls, intercom, phonebook, call log, redial list, phone settings, answering machine, services, technical data, notice, appendix, and FAQ headings.
  - Repaired high-confidence OCR such as `Declaration of conformity`, temperature ranges, `ECO+`/`PIN` wording, split section titles, broken step numbering, and several clearly corrupted words, while leaving some low-value index-page OCR residue untouched because it does not affect image/text alignment or core usability.
  - Validated that all 62 image references remain present and all links resolve.
- [x] `Yamaha WaveRunner 2005.md`
  - Visually checked all 101 image references against nearby text using image-context extraction, a contact sheet, and larger original-image checks for the component-location diagrams, controls, warning labels, storage compartments, adjustable sponson adjustment, and boarding/starting procedure figures.
  - Found no confirmed local image/text misplacement; the primary problems were OCR-split headings, compressed numbered callout descriptions, and note/warning formatting rather than image ordering.
  - Rebuilt the main-component overview and multiple operation sections into readable Markdown, including QSTS controls, multifunction meter features, storage compartments, fire-extinguisher note, adjustable sponson adjustment, jet-intake cleaning, and boarding/starting sections.
  - Repaired high-confidence OCR such as split headings, `ON/OFF/RES` structure, torque line breaks, `one-piece`, `position of`, `combination of`, and similar obvious corruption, while leaving many low-value source code markers (`EJU...`) and some brand-name OCR residue untouched because they do not create image/text mismatch risk.
  - Validated that all 101 image references remain present and all links resolve.

Pending manuals:

Not a target manual unless requested:
- [ ] `手册内容总览.md`

- [x] `Toro Z Master 4000.md`
  - Visually checked all 142 image references against nearby text using image-context extraction, a full contact sheet, and targeted larger-image checks for decal blocks, parking-brake/height-of-cut figures, Kohler air-cleaner figures, troubleshooting tables, and blade-maintenance diagrams.
  - Confirmed the overall image order is correct; the main issues were OCR structure corruption and a few local text/figure attachments, including the safety decal block, parking-brake figure numbering, fuel-shutoff figure labels, Kawasaki/Kohler maintenance figure captions, battery/fuse figure text, and a confirmed blade-maintenance mismatch where sharpening figures had been left under `Installing the Blades`.
  - Rebuilt those sections into coherent Markdown without removing images, restored missing `Troubleshooting` and `Schematics` headings before the final table/schematic images, and repaired high-confidence OCR such as `TRANSPORT`, `bottom cushion of the seat`, and multiple broken warning/step/title lines.
  - Validated that all 142 image references remain present and all links resolve.
- [x] `Yamaha 210FSH 2021.md`
  - Visually checked all 294 image references against nearby text using image-context extraction, a full contact sheet, and targeted larger-image checks for label blocks, main-component overviews, helm/control diagrams, Bimini procedures, maintenance tables, troubleshooting tables, and emergency/fuse figures.
  - Confirmed the overall image order is correct; the dominant issue was OCR structure corruption rather than misplaced images, including run-on contents pages, merged section titles, compressed numbered callouts, and multi-step procedures collapsed into single paragraphs.
  - Rebuilt the highest-impact sections into coherent Markdown, including the opening glossary/contents area, safety-capacity and operation requirements text, component overviews, control-function descriptions, Bimini setup/storage sections, pre-operation checks, lubrication headings, and trouble-recovery emergency/fuse procedures.
  - Repaired high-confidence OCR such as `Thank you`, `vision of others`, `National Association of State Boating Law Administrators`, `CO2`, `Accessory fuse`, and multiple broken warning/list/heading lines, while preserving all image references.
  - Validated that all 294 image references remain present and all links resolve.
- [x] `Yamaha Snowmobile.md`
  - Visually checked all 256 image references against nearby text using image-context extraction, segmented contact sheets, and targeted original-image checks for label blocks, control-switch figures, emergency-starting figures, brake/track adjustment diagrams, headlight/battery/fuse figures, troubleshooting diagrams, and final wiring diagrams.
  - Confirmed the overall image order is correct; the dominant issue was OCR structure corruption rather than large-scale image misplacement, including damaged contents pages, merged section titles, compressed procedures, and model-specific subsections collapsed together.
  - Rebuilt the highest-impact sections into coherent Markdown, including identification/intro/contents, important-label blocks, safety information, model descriptions, control functions, pre-operation checks, starting/driving sections, high-altitude and V-belt maintenance, brake/suspension/track adjustment sections, headlight/battery/fuse sections, troubleshooting, storage, and the wiring-diagram tail.
  - Fixed one local context issue in the control-switch area by restoring the trip-odometer-reset figure under its own heading instead of leaving it attached to the grip/thumb-warmer section.
  - Validated that all 256 image references remain present and all links resolve.

Current next target:
- [x] All target manuals in `v2/data/en-manual/*.md` are complete for this audit pass.

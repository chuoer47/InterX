# OCR Patterns

Use these searches as a starting point, not as an automatic rewrite list.

## How to discover patterns for a new manual

1. Skim the first few pages of the Markdown for obvious corruptions (missing spaces, split words, merged headings).
2. Pick 3–5 representative corrupted tokens and build a `rg` alternation pattern from them.
3. Run it against the full file; review each hit before fixing.
4. Add domain-specific terms (product names, feature labels, safety keywords) as you encounter them.

## Generic pattern starters

These catch the most common OCR artifacts across manuals:

```bash
# Missing spaces between common English words
rg -n '[a-z](the|for|and|with|from|that|this|not|are|was|has|can|will|all|one|use|see|set|get|but|how|any)[A-Z]' <manual.md>

# Split uppercase words (e.g. "EX CESSIVE", "OP ERA TING")
rg -n '[A-Z]{2,} [A-Z]{2,}' <manual.md>

# Merged heading/paragraph runs (lowercase immediately followed by uppercase mid-line)
rg -n '[a-z]{3,}[A-Z][a-z]{2,}' <manual.md>

# Units stuck to numbers (e.g. "20cm", "10kg")
rg -n '[0-9](cm|mm|kg|lb|oz|ml|L|W|V|A|Hz|dB|°C|°F)' <manual.md>
```

## Domain-specific examples (from previous manual audits)

```bash
# Microwave / kitchen appliance manuals
rg -n 'theoven|Theoven|theboiling|heatingit|OPERATINGINSTRUCTIONS|METALRACK|HOLDWARM' <manual.md>

# Outdoor power equipment manuals
rg -n 'TRANSPORT|bottomcushion|parkingbrake|heightofcut' <manual.md>

# Camera / electronics manuals
rg -n 'AFassist|CustomFunction|shutterspeed|aperturevalue' <manual.md>
```

Add patterns as you encounter them; keep the list lean and high-confidence.

## Fix guidelines

- **Safe to fix**: missing spaces, split words, malformed headings, broken list nesting, stuck units, punctuation that restores sentence boundaries.
- **Ask first**: warranty/legal paragraphs, model-specific claims, safety warnings whose exact wording cannot be inferred, or any text where OCR could have multiple valid readings.

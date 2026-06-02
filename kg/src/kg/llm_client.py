"""LLM client for knowledge graph cold-start relationship extraction."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAI

from .config import LLMConfig
from .types import SemanticPoint, SemanticRelation

log = logging.getLogger(__name__)

# Build prompt with str.format() — {{ }} become literal { } in output.
_EXTRACT_TEMPLATE = (
    "<role>Analyze two chunks from the same product manual.\n"
    "Extract semantic points and any meaningful multi-hop relation.</role>\n\n"
    "<rules>\n"
    "- Only extract genuine semantic links: REQUIRES, CAUSES, RESOLVED_BY, AFFECTS, NEXT_STEP.\n"
    "- Do NOT link chunks just because they are in the same section.\n"
    "- If no meaningful link exists, return empty arrays.\n"
    "</rules>\n\n"
    "<output_format>\n"
    "Return ONLY this JSON (no markdown, no explanation):\n"
    '{{"semantic_points": [{{"sp_id": "sp_001", "chunk_side": "A", "point_type": "task", "label": "short desc", "description": "1 sentence"}}], '
    '"relations": [{{"src_sp_id": "sp_001", "dst_sp_id": "sp_002", "rel_type": "CAUSES", "confidence": 0.8, "evidence": "reason"}}]}}\n\n'
    "point_type values: task, condition, symptom, cause, resolution, parameter, effect, concept, warning, requirement\n"
    "rel_type values: REQUIRES, CAUSES, RESOLVED_BY, AFFECTS, NEXT_STEP, RELATED_TO\n"
    "</output_format>\n\n"
    "<chunk_a section=\"{section_a}\">\n{chunk_a}\n</chunk_a>\n\n"
    "<chunk_b section=\"{section_b}\">\n{chunk_b}\n</chunk_b>\n"
)


class LLMClient:
    """Thin wrapper around OpenAI-compatible API for graph extraction."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout,
        )
        self.call_count = 0

    def extract_relations(
        self,
        chunk_a: dict[str, Any],
        chunk_b: dict[str, Any],
    ) -> tuple[list[SemanticPoint], list[SemanticRelation]]:
        """Send a chunk pair to LLM and extract semantic points + relations."""
        prompt = _EXTRACT_TEMPLATE.format(
            section_a=chunk_a.get("section_title", ""),
            chunk_a=chunk_a.get("text", "")[:1500],
            section_b=chunk_b.get("section_title", ""),
            chunk_b=chunk_b.get("text", "")[:1500],
        )

        for attempt in range(self._config.max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=self._config.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=8192,
                )
                self.call_count += 1
                raw = resp.choices[0].message.content or ""
                if not raw.strip():
                    log.warning("Empty LLM response on attempt %d", attempt + 1)
                    continue
                return self._parse_response(raw, chunk_a, chunk_b)
            except Exception as exc:
                log.warning("LLM extract attempt %d failed: %s", attempt + 1, exc)
                if attempt == self._config.max_retries - 1:
                    log.error("LLM extract failed after %d retries", self._config.max_retries)
        return [], []

    def _parse_response(
        self,
        raw: str,
        chunk_a: dict[str, Any],
        chunk_b: dict[str, Any],
    ) -> tuple[list[SemanticPoint], list[SemanticRelation]]:
        """Parse LLM JSON output into typed objects."""
        # Strip markdown fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            log.warning("Failed to parse LLM response as JSON: %s", raw[:300])
            return [], []

        manual_id = chunk_a.get("doc_id", "")
        sp_map: dict[str, str] = {}
        points: list[SemanticPoint] = []
        for item in data.get("semantic_points", []):
            local_id = item.get("sp_id", "")
            side = str(item.get("chunk_side", "A")).strip().upper()
            base_chunk = chunk_a if side == "A" else chunk_b
            global_id = f"{manual_id}_sp_{local_id}_{base_chunk.get('chunk_id', '')}"
            sp_map[local_id] = global_id
            points.append(SemanticPoint(
                sp_id=global_id,
                point_type=item.get("point_type", "concept"),
                label=item.get("label", ""),
                description=item.get("description", ""),
                source_chunk_ids=[base_chunk.get("chunk_id", "")],
                manual_id=manual_id,
            ))

        relations: list[SemanticRelation] = []
        for item in data.get("relations", []):
            src_id = sp_map.get(item.get("src_sp_id", ""), "")
            dst_id = sp_map.get(item.get("dst_sp_id", ""), "")
            if src_id and dst_id:
                relations.append(SemanticRelation(
                    src_sp_id=src_id,
                    dst_sp_id=dst_id,
                    rel_type=item.get("rel_type", "RELATED_TO"),
                    confidence=float(item.get("confidence", 0.5)),
                    evidence=item.get("evidence", ""),
                ))

        return points, relations

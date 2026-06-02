"""Shared data types for the KG layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SemanticPoint:
    """A semantic concept extracted from one or more chunks."""
    sp_id: str
    point_type: str       # task / condition / symptom / cause / resolution / parameter / effect / concept / warning / requirement
    label: str            # human-readable short description
    description: str
    source_chunk_ids: list[str] = field(default_factory=list)
    manual_id: str = ""


@dataclass(slots=True)
class SemanticRelation:
    """A typed directed edge between two semantic points."""
    src_sp_id: str
    dst_sp_id: str
    rel_type: str         # REQUIRES / CAUSES / RESOLVED_BY / AFFECTS / NEXT_STEP / RELATED_TO
    confidence: float = 1.0
    evidence: str = ""


@dataclass(slots=True)
class GraphExpansion:
    """Result returned by graph retrieval for one query."""
    expanded_chunk_ids: list[str] = field(default_factory=list)
    paths: list[dict[str, Any]] = field(default_factory=list)
    graph_scores: dict[str, float] = field(default_factory=dict)
    manual_id: str = ""


@dataclass(slots=True)
class BuildReport:
    """Summary produced after building one manual's graph."""
    manual_id: str
    total_small_chunks: int = 0
    total_semantic_points: int = 0
    total_relations: int = 0
    llm_calls: int = 0
    errors: list[str] = field(default_factory=list)

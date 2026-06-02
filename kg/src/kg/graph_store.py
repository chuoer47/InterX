"""Graph storage backend using Kùzu (embedded, no server needed).

NOTE: Kùzu's MERGE ... SET only supports one property per SET clause when
updating an existing node.  We work around this by issuing one MERGE per
property column.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import kuzu

from .types import SemanticPoint, SemanticRelation


def _exec(conn: kuzu.Connection, query: str, params: dict[str, Any] | None = None) -> None:
    """Execute a query, silently ignoring 'already exists' errors."""
    try:
        conn.execute(query, parameters=params or {})
    except RuntimeError as exc:
        if "already exists" in str(exc).lower() or "exist" in str(exc).lower():
            return
        raise


class GraphStore:
    """Manages per-manual knowledge graphs in Kùzu.

    Each manual gets its own database file at ``<root>/<manual_id>.kuzu``.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._dbs: dict[str, kuzu.Database] = {}
        self._conns: dict[str, kuzu.Connection] = {}

    def _db_path(self, manual_id: str) -> Path:
        return self._root / f"{manual_id}.kuzu"

    def _get_conn(self, manual_id: str) -> kuzu.Connection:
        if manual_id in self._conns:
            return self._conns[manual_id]
        db = kuzu.Database(self._db_path(manual_id))
        conn = kuzu.Connection(db)
        self._init_schema(conn)
        self._dbs[manual_id] = db
        self._conns[manual_id] = conn
        return conn

    def _init_schema(self, conn: kuzu.Connection) -> None:
        stmts = [
            "CREATE NODE TABLE IF NOT EXISTS Manual(id STRING, name STRING, PRIMARY KEY(id))",
            "CREATE NODE TABLE IF NOT EXISTS Section(id STRING, manual_id STRING, title STRING, PRIMARY KEY(id))",
            "CREATE NODE TABLE IF NOT EXISTS BigChunk(id STRING, manual_id STRING, section_id STRING, PRIMARY KEY(id))",
            "CREATE NODE TABLE IF NOT EXISTS MidChunk(id STRING, manual_id STRING, big_chunk_id STRING, PRIMARY KEY(id))",
            "CREATE NODE TABLE IF NOT EXISTS SmallChunk(id STRING, manual_id STRING, mid_chunk_id STRING, txt STRING, section_title STRING, PRIMARY KEY(id))",
            "CREATE NODE TABLE IF NOT EXISTS SemanticPoint(id STRING, manual_id STRING, ptype STRING, lbl STRING, descr STRING, PRIMARY KEY(id))",
            "CREATE REL TABLE IF NOT EXISTS HAS_SECTION(FROM Manual TO Section)",
            "CREATE REL TABLE IF NOT EXISTS HAS_BIG(FROM Section TO BigChunk)",
            "CREATE REL TABLE IF NOT EXISTS HAS_MID(FROM BigChunk TO MidChunk)",
            "CREATE REL TABLE IF NOT EXISTS HAS_SMALL(FROM MidChunk TO SmallChunk)",
            "CREATE REL TABLE IF NOT EXISTS MENTIONS(FROM SmallChunk TO SemanticPoint)",
            "CREATE REL TABLE IF NOT EXISTS GROUNDED_IN(FROM SemanticPoint TO SmallChunk)",
            "CREATE REL TABLE IF NOT EXISTS SEMANTIC_REL(FROM SemanticPoint TO SemanticPoint, rel_type STRING, confidence DOUBLE, evidence STRING)",
        ]
        for s in stmts:
            _exec(conn, s)

    # ── helpers ───────────────────────────────────────────────────────

    def _merge_node(self, conn: kuzu.Connection, label: str, node_id: str, props: dict[str, Any]) -> None:
        """Upsert a node by issuing one MERGE per property (Kùzu workaround)."""
        for key, val in props.items():
            pname = f"p_{key}"
            conn.execute(
                f"MERGE (n:{label} {{id: $id}}) SET n.{key}=${pname}",
                parameters={"id": node_id, pname: val},
            )

    # ── write helpers ─────────────────────────────────────────────────

    def upsert_manual(self, manual_id: str, name: str) -> None:
        conn = self._get_conn(manual_id)
        self._merge_node(conn, "Manual", manual_id, {"name": name})

    def upsert_small_chunk(self, manual_id: str, chunk_id: str, mid_chunk_id: str, text: str, section_title: str) -> None:
        conn = self._get_conn(manual_id)
        self._merge_node(conn, "SmallChunk", chunk_id, {
            "manual_id": manual_id,
            "mid_chunk_id": mid_chunk_id,
            "txt": text[:2000],
            "section_title": section_title,
        })

    def upsert_mid_chunk(self, manual_id: str, chunk_id: str, big_chunk_id: str) -> None:
        conn = self._get_conn(manual_id)
        self._merge_node(conn, "MidChunk", chunk_id, {"manual_id": manual_id, "big_chunk_id": big_chunk_id})

    def upsert_big_chunk(self, manual_id: str, chunk_id: str, section_id: str) -> None:
        conn = self._get_conn(manual_id)
        self._merge_node(conn, "BigChunk", chunk_id, {"manual_id": manual_id, "section_id": section_id})

    def upsert_semantic_point(self, manual_id: str, sp: SemanticPoint) -> None:
        conn = self._get_conn(manual_id)
        self._merge_node(conn, "SemanticPoint", sp.sp_id, {
            "manual_id": manual_id,
            "ptype": sp.point_type,
            "lbl": sp.label,
            "descr": sp.description[:1000],
        })

    def upsert_relation(self, manual_id: str, rel: SemanticRelation) -> None:
        conn = self._get_conn(manual_id)
        _exec(conn, """
            MATCH (a:SemanticPoint {id: $src}), (b:SemanticPoint {id: $dst})
            CREATE (a)-[:SEMANTIC_REL {rel_type: $rt, confidence: $conf, evidence: $ev}]->(b)
        """, {"src": rel.src_sp_id, "dst": rel.dst_sp_id,
              "rt": rel.rel_type, "conf": rel.confidence, "ev": rel.evidence[:500]})

    def link_chunk_to_sp(self, manual_id: str, chunk_id: str, sp_id: str) -> None:
        conn = self._get_conn(manual_id)
        _exec(conn,
              "MATCH (s:SmallChunk {id: $cid}), (sp:SemanticPoint {id: $sid}) CREATE (s)-[:MENTIONS]->(sp)",
              {"cid": chunk_id, "sid": sp_id})
        _exec(conn,
              "MATCH (sp:SemanticPoint {id: $sid}), (s:SmallChunk {id: $cid}) CREATE (sp)-[:GROUNDED_IN]->(s)",
              {"sid": sp_id, "cid": chunk_id})

    def link_chunk_hierarchy(self, manual_id: str, small_id: str, mid_id: str, big_id: str) -> None:
        conn = self._get_conn(manual_id)
        _exec(conn,
              "MATCH (m:MidChunk {id: $mid}), (s:SmallChunk {id: $sm}) CREATE (m)-[:HAS_SMALL]->(s)",
              {"mid": mid_id, "sm": small_id})
        _exec(conn,
              "MATCH (b:BigChunk {id: $big}), (m:MidChunk {id: $mid}) CREATE (b)-[:HAS_MID]->(m)",
              {"big": big_id, "mid": mid_id})

    # ── read helpers ──────────────────────────────────────────────────

    def get_chunk_semantic_points(self, manual_id: str, chunk_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn(manual_id)
        result = conn.execute(
            "MATCH (s:SmallChunk {id: $cid})-[:MENTIONS]->(sp:SemanticPoint) "
            "RETURN sp.id, sp.ptype, sp.lbl, sp.descr",
            parameters={"cid": chunk_id},
        )
        out: list[dict[str, Any]] = []
        while result.has_next():
            row = result.get_next()
            out.append({"sp_id": row[0], "point_type": row[1], "label": row[2], "description": row[3]})
        return out

    def traverse_from_sp(self, manual_id: str, sp_ids: list[str], max_hops: int = 2) -> list[dict[str, Any]]:
        if not sp_ids:
            return []
        conn = self._get_conn(manual_id)
        return self._bfs(conn, sp_ids, max_hops)

    def _bfs(self, conn: kuzu.Connection, seed_ids: list[str], max_hops: int) -> list[dict[str, Any]]:
        visited = set(seed_ids)
        frontier = set(seed_ids)
        all_paths: list[dict[str, Any]] = []
        for hop in range(1, max_hops + 1):
            next_frontier: set[str] = set()
            for sp_id in frontier:
                result = conn.execute(
                    "MATCH (a:SemanticPoint {id: $sid})-[r:SEMANTIC_REL]->(b:SemanticPoint) "
                    "RETURN b.id, r.rel_type",
                    parameters={"sid": sp_id},
                )
                while result.has_next():
                    row = result.get_next()
                    dst, rel_type = row[0], row[1]
                    all_paths.append({"src_sp": sp_id, "dst_sp": dst, "hops": hop, "rel_chain": [rel_type]})
                    if dst not in visited:
                        visited.add(dst)
                        next_frontier.add(dst)
            frontier = next_frontier
            if not frontier:
                break
        return all_paths

    def sp_to_chunks(self, manual_id: str, sp_ids: list[str]) -> list[dict[str, Any]]:
        if not sp_ids:
            return []
        conn = self._get_conn(manual_id)
        out: list[dict[str, Any]] = []
        for sp_id in sp_ids:
            result = conn.execute(
                "MATCH (sp:SemanticPoint {id: $sid})-[:GROUNDED_IN]->(s:SmallChunk) "
                "RETURN DISTINCT s.id, s.txt, s.section_title",
                parameters={"sid": sp_id},
            )
            while result.has_next():
                row = result.get_next()
                out.append({"chunk_id": row[0], "text": row[1], "section_title": row[2]})
        return out

    def count_nodes(self, manual_id: str) -> dict[str, int]:
        conn = self._get_conn(manual_id)
        counts: dict[str, int] = {}
        for label in ("SmallChunk", "SemanticPoint", "MidChunk", "BigChunk", "Manual"):
            r = conn.execute(f"MATCH (n:{label}) RETURN count(*)")
            counts[label] = r.get_next()[0] if r.has_next() else 0
        for rel in ("SEMANTIC_REL", "MENTIONS", "GROUNDED_IN", "HAS_SMALL", "HAS_MID"):
            r = conn.execute(f"MATCH ()-[r:{rel}]->() RETURN count(*)")
            counts[rel] = r.get_next()[0] if r.has_next() else 0
        return counts

    def drop_manual(self, manual_id: str) -> None:
        """Delete an entire manual's graph database files."""
        db_path = self._db_path(manual_id)
        self._conns.pop(manual_id, None)
        self._dbs.pop(manual_id, None)
        # Remove db file and any associated WAL/checkpoint files
        for p in [db_path] + list(db_path.parent.glob(f'{manual_id}.kuzu.*')):
            if p.exists():
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()

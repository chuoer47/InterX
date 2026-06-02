from __future__ import annotations
"""Milvus Lite ingestion for small-chunk embeddings."""

from pathlib import Path
from typing import Any

from pymilvus import DataType, MilvusClient

from .config import VectorStoreConfig
from .utils import read_jsonl


def _create_collection(
    client: MilvusClient,
    *,
    collection_name: str,
    dim: int,
    config: VectorStoreConfig,
) -> None:
    """
    Create the Milvus schema used by retrieval.

    Only the search-critical metadata is indexed into Milvus. Heavier payloads stay
    in JSON artifacts so the vector store remains compact and fast to load.
    """
    schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("chunk_id", DataType.VARCHAR, is_primary=True, max_length=160)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field("big_chunk_id", DataType.VARCHAR, max_length=160)
    schema.add_field("mid_chunk_id", DataType.VARCHAR, max_length=160)
    schema.add_field("doc_id", DataType.VARCHAR, max_length=128)
    schema.add_field("doc_name", DataType.VARCHAR, max_length=256)
    schema.add_field("product_name", DataType.VARCHAR, max_length=128)
    schema.add_field("source_path", DataType.VARCHAR, max_length=1024)
    schema.add_field("section_title", DataType.VARCHAR, max_length=512)
    schema.add_field("image_count", DataType.INT64)
    schema.add_field("token_count", DataType.INT64)

    index_params = client.prepare_index_params()
    index_params.add_index(
        "vector",
        index_type=config.index_type,
        metric_type=config.metric_type,
    )
    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
    )


def build_vector_store(
    *,
    manuals_dir: Path,
    db_path: Path,
    config: VectorStoreConfig,
    rebuild: bool = True,
) -> int:
    """
    Ingest all manual-level embedding outputs into one shared Milvus Lite database.

    The retrieval layer uses small chunks as its primary recall unit, so only the
    small chunk embeddings are inserted here.
    """
    collection_name = config.collection_name
    db_path.parent.mkdir(parents=True, exist_ok=True)
    client = MilvusClient(uri=str(db_path))

    if rebuild and client.has_collection(collection_name):
        client.drop_collection(collection_name)

    total = 0
    created = False
    batch_size = max(1, config.batch_size)

    for manual_dir in sorted(manuals_dir.iterdir()):
        if not manual_dir.is_dir():
            continue
        chunks_path = manual_dir / "small_chunks.jsonl"
        embeddings_path = manual_dir / "embeddings.jsonl"
        if not chunks_path.exists() or not embeddings_path.exists():
            continue

        chunks = read_jsonl(chunks_path)
        embeddings = read_jsonl(embeddings_path)
        vector_by_id = {row["chunk_id"]: row["vector"] for row in embeddings}

        if not created and vector_by_id:
            sample_vector = next(iter(vector_by_id.values()))
            _create_collection(
                client,
                collection_name=collection_name,
                dim=len(sample_vector),
                config=config,
            )
            created = True

        rows: list[dict[str, Any]] = []
        for chunk in chunks:
            cid = chunk["chunk_id"]
            vec = vector_by_id.get(cid)
            if vec is None:
                continue
            rows.append(
                {
                    "chunk_id": cid,
                    "vector": vec,
                    "big_chunk_id": chunk.get("big_chunk_id", ""),
                    "mid_chunk_id": chunk.get("mid_chunk_id", ""),
                    "doc_id": chunk.get("doc_id", ""),
                    "doc_name": chunk.get("doc_name", ""),
                    "product_name": chunk.get("product_name", ""),
                    "source_path": chunk.get("source_path", ""),
                    "section_title": chunk.get("section_title", ""),
                    "image_count": int(chunk.get("image_count", 0)),
                    "token_count": int(chunk.get("token_count", 0)),
                }
            )

        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            if not batch:
                continue
            client.insert(collection_name=collection_name, data=batch)
            total += len(batch)

    if created:
        client.flush(collection_name=collection_name)
    return total

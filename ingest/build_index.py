"""CLI: python -m ingest.build_index. See SPEC.md section 3, 5, 6."""
from __future__ import annotations

from app.config import Settings, get_settings
from app.retriever import get_collection
from ingest.chunk import chunk_document
from ingest.embed import get_embedder
from ingest.load import load_documents

MANIFEST_PATH = "data/manifest.csv"
RAW_DIR = "data/raw"


def build_index(settings: Settings) -> dict:
    documents = load_documents(MANIFEST_PATH, RAW_DIR)
    embedder = get_embedder(settings, for_query=False)
    collection = get_collection(settings.chroma_dir, settings.collection)

    for document in documents:
        chunks = chunk_document(document, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            continue
        ids = [c.chunk_id for c in chunks]
        texts = [c.text for c in chunks]
        embeddings = embedder.embed(texts)
        metadatas = [
            {
                "doc_id": c.doc_id,
                "title": c.title,
                "publisher": c.publisher,
                "url": c.url,
                "page": c.page,
                "section": c.section,
            }
            for c in chunks
        ]
        # Upsert by chunk_id: re-running ingestion never creates duplicates.
        collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

    return {"documents": len(documents), "chunks": collection.count()}


if __name__ == "__main__":
    result = build_index(get_settings())
    print(f"documents={result['documents']} chunks={result['chunks']}")

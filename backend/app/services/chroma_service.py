import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
CHROMA_DATA_DIR = BACKEND_DIR / "data" / "chroma"
COLLECTION_NAME = "citizen_complaints"


class ChromaService:

    def __init__(self):
        self._client: Optional[chromadb.ClientAPI] = None
        self._collection = None

    @property
    def client(self) -> chromadb.ClientAPI:
        if self._client is None:
            CHROMA_DATA_DIR.mkdir(parents=True, exist_ok=True)
            logger.info("Initializing persistent ChromaDB client at: %s", CHROMA_DATA_DIR)
            self._client = chromadb.PersistentClient(
                path=str(CHROMA_DATA_DIR),
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB collection '%s' ready.", COLLECTION_NAME)
        return self._collection

    def add_complaint(
        self,
        complaint_id: str,
        document: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> None:
        # ChromaDB metadata values must be primitives (str, int, float, bool)
        sanitized_metadata = {}
        for k, v in metadata.items():
            if v is None:
                sanitized_metadata[k] = ""
            elif isinstance(v, (str, int, float, bool)):
                sanitized_metadata[k] = v
            else:
                sanitized_metadata[k] = str(v)

        self.collection.add(
            ids=[complaint_id],
            documents=[document],
            embeddings=[embedding],
            metadatas=[sanitized_metadata],
        )
        logger.info("Added complaint '%s' to ChromaDB collection.", complaint_id)

    def query_similar(
        self,
        embedding: List[float],
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        total_items = self.collection.count()
        if total_items == 0:
            return []

        limit = min(n_results, total_items)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )

        matches = []
        if results and results.get("ids") and results["ids"][0]:
            ids = results["ids"][0]
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            for i in range(len(ids)):
                dist = float(distances[i]) if i < len(distances) else 1.0
                # ChromaDB cosine space returns Cosine Distance = (1 - similarity)
                similarity = max(0.0, min(1.0, round(1.0 - dist, 4)))
                matches.append(
                    {
                        "id": ids[i],
                        "document": documents[i] if i < len(documents) else "",
                        "metadata": metadatas[i] if i < len(metadatas) else {},
                        "distance": round(dist, 4),
                        "similarity": similarity,
                    }
                )

        # Sort matches by highest similarity first
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches

    def count_complaints(self) -> int:
        return self.collection.count()

    def clear_collection(self) -> None:
        try:
            self.client.delete_collection(name=COLLECTION_NAME)
        except Exception:
            pass
        self._collection = None
        logger.info("Cleared ChromaDB collection '%s'.", COLLECTION_NAME)


chroma_service = ChromaService()

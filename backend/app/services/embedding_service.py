import logging
import os
from typing import List

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingService:

    def __init__(self):
        self._model = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            model_name = os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL_NAME).strip()
            logger.info("Loading multilingual SentenceTransformer model '%s'...", model_name)
            try:
                self._model = SentenceTransformer(model_name)
                logger.info("SentenceTransformer model loaded successfully.")
            except Exception as e:
                logger.exception("Failed to load SentenceTransformer model '%s': %s", model_name, str(e))
                if model_name != DEFAULT_MODEL_NAME:
                    logger.info("Falling back to default model '%s'...", DEFAULT_MODEL_NAME)
                    self._model = SentenceTransformer(DEFAULT_MODEL_NAME)
                else:
                    raise
        return self._model

    def get_embedding(self, text: str) -> List[float]:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty for embedding generation.")

        embedding_vector = self.model.encode(text, convert_to_numpy=True)
        return embedding_vector.tolist()


embedding_service = EmbeddingService()

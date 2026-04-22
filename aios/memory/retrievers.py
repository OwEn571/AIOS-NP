from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import List, Dict, Any

import chromadb
import numpy as np
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from sklearn.metrics.pairwise import cosine_similarity


def simple_tokenize(text: str) -> list[str]:
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())

class SimpleEmbeddingRetriever:
    """Simple retriever using sentence embeddings"""
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.documents = []
        self.embeddings = None
        
    def add_document(self, document: str):
        """Add a document to the retriever.
        
        Args:
            document: Text content to add
        """
        self.documents.append(document)
        # Update embeddings
        if len(self.documents) == 1:
            self.embeddings = self.model.encode([document])
        else:
            new_embedding = self.model.encode([document])
            self.embeddings = np.vstack([self.embeddings, new_embedding])
            
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of dictionaries containing document content and similarity score
        """
        if not self.documents:
            return []
            
        # Get query embedding
        query_embedding = self.model.encode([query])
        
        # Calculate cosine similarities
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        
        # Get top k results
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            results.append({
                'content': self.documents[idx],
                'score': float(similarities[idx])
            })
            
        return results

class ChromaRetriever:
    """Vector database retrieval using ChromaDB"""
    def __init__(self, collection_name: str | None = None):
        """Initialize ChromaDB retriever.
        
        Args:
            collection_name: Name of the ChromaDB collection
        """
        chroma_dir = Path(
            os.getenv(
                "AIOS_MEMORY_CHROMA_DIR",
                str(Path(__file__).resolve().parents[3] / "data" / "aios-np-memory-chroma"),
            )
        )
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(chroma_dir))
        self.collection = self.client.get_or_create_collection(
            name=collection_name or os.getenv("AIOS_MEMORY_COLLECTION_NAME", "memories_localhash_v1"),
            embedding_function=LocalHashEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"},
        )
        
    def add_document(self, document: str, metadata: Dict, doc_id: str):
        """Add a document to ChromaDB.
        
        Args:
            document: Text content to add
            metadata: Dictionary of metadata
            doc_id: Unique identifier for the document
        """
        # Convert lists to strings in metadata to comply with ChromaDB requirements
        processed_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, list):
                processed_metadata[key] = ", ".join(value)
            else:
                processed_metadata[key] = value
                
        self.collection.add(
            documents=[document],
            metadatas=[processed_metadata],
            ids=[doc_id]
        )
        
    def delete_document(self, doc_id: str):
        """Delete a document from ChromaDB.
        
        Args:
            doc_id: ID of document to delete
        """
        self.collection.delete(ids=[doc_id])
        
    def search(self, query: str, k: int = 5):
        """Search for similar documents.
        
        Args:
            query: Query text
            k: Number of results to return
            
        Returns:
            List of dicts with document text and metadata
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=k
        )
        
        # Convert string metadata back to lists where appropriate
        if 'metadatas' in results and results['metadatas']:
            for metadata in results['metadatas']:
                for key in ['keywords', 'tags']:
                    if key in metadata and isinstance(metadata[key], str):
                        metadata[key] = [item.strip() for item in metadata[key].split(',')]
                        
        return results


class LocalHashEmbeddingFunction(EmbeddingFunction[Documents]):
    """Offline embedding function used by AIOS memory on constrained hosts.

    It avoids Chroma's default ONNX model download path so the memory subsystem
    remains usable on servers without stable outbound network access.
    """

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed_document(document) for document in input]

    @staticmethod
    def name() -> str:
        return "local_hash_embedding"

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "LocalHashEmbeddingFunction":
        return LocalHashEmbeddingFunction(dimensions=int(config.get("dimensions", 256)))

    def get_config(self) -> Dict[str, Any]:
        return {"dimensions": self.dimensions}

    def _embed_document(self, document: str) -> list[float]:
        vector = np.zeros(self.dimensions, dtype=np.float32)
        for feature in self._extract_features(document):
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = -1.0 if digest[4] % 2 else 1.0
            vector[bucket] += sign

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector /= norm
        return vector.tolist()

    def _extract_features(self, document: str) -> list[str]:
        lowered = (document or "").lower()
        features = simple_tokenize(lowered)
        compact = re.sub(r"\s+", "", lowered)
        if compact:
            features.extend(compact[index : index + 2] for index in range(max(len(compact) - 1, 0)))
            features.extend(compact[index : index + 3] for index in range(max(len(compact) - 2, 0)))
        return [feature for feature in features if feature]

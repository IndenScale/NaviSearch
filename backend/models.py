from pydantic import BaseModel
from typing import List, Dict, Any, Optional
# Pydantic models
class SearchQuery(BaseModel):
    query: str = ""
    like_tags: List[str] = []
    must_tags: List[str] = []
    must_not_tags: List[str] = []

class SearchResult(BaseModel):
    id: str
    content: str
    source: str
    original_file: Optional[str] = None
    tags: List[str]
    similarity: float
    like_score: int = 0
    chunk_info: Optional[Dict[str, Any]] = None

class TagUpdate(BaseModel):
    tags: List[str]

class IngestResponse(BaseModel):
    success: bool
    processed_files: int
    total_chunks: int
    failed_files: List[str]
    message: str

class DocumentChunk(BaseModel):
    chunk_id: str
    content: str
    source: str
    original_file: str
    chunk_index: int
    total_chunks: int
    tags: List[str]
    embedding: List[float]
    metadata: Dict[str, Any] = {}
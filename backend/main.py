import os
import json
import uuid
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
import aiofiles
from datetime import datetime
import shutil

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
import openai
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
import uvicorn
from dotenv import load_dotenv

from document_processors import DocumentProcessorFactory

# Pydantic models
from models import SearchQuery, SearchResult, TagUpdate, IngestResponse, DocumentChunk
from utils import calculate_tag_eig, generate_tags, get_embedding

# Load environment variables
load_dotenv()

# Configuration
class Config:
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-v3")
    OPENAI_LLM_MODEL = os.getenv("OPENAI_LLM_MODEL", "deepseek-v3")
    OPENAI_VLM_MODEL = os.getenv("OPENAI_VLM_MODEL", "qwen-vl-max")

    MILVUS_COLLECTION_NAME = os.getenv("MILVUS_COLLECTION_NAME", "navisearch_docs")
    MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
    MILVUS_TOKEN = os.getenv("MILVUS_TOKEN", "")

    TAG_DIRECTORY = os.getenv("TAG_DIRECTORY", "data/tag_directory.json")
    VLM_PROMPT_TEMPLATE = os.getenv("VLM_PROMPT_TEMPLATE", "prompts/vlm_image_description.txt")
    
    RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "10"))
    RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "5"))
    TAGS_TOP_K = int(os.getenv("TAGS_TOP_K", "15"))
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "52428800"))  # 50MB
    
    # Text chunking configuration
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
    CHUNK_SEPARATORS = json.loads(os.getenv("CHUNK_SEPARATORS", '["\\n\\n", "\\n", "。", ".", " "]'))

    ADMIN_WEBUI_URL = os.getenv("ADMIN_WEBUI_URL", "http://localhost:3001")
    USER_WEBUI_URL = os.getenv("USER_WEBUI_URL", "http://localhost:3000")
    FAST_API_URL = os.getenv("FAST_API_URL", "http://localhost:8000")

    # Directory structure
    BASE_DATA_DIR = Path("data")
    UPLOAD_DIR = BASE_DATA_DIR / "upload"
    INGESTED_DIR = BASE_DATA_DIR / "ingested"
    SEPARATED_DIR = BASE_DATA_DIR / "separated"
    CHUNKED_DIR = BASE_DATA_DIR / "chunked"
    DOCUMENTS_FILE = BASE_DATA_DIR / "documents.jsonl"

    # Supported file types
    SUPPORTED_EXTENSIONS = {
        '.txt', '.md', '.pdf', '.docx', '.pptx', '.xlsx', 
        '.html', '.htm', '.rtf', '.odt', '.odp', '.ods'
    }

    # Simple auth tokens (in production, use proper JWT)
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin_secret_token")
    USER_TOKEN = os.getenv("USER_TOKEN", "user_secret_token")

config = Config()

# Initialize OpenAI client
openai_client = openai.AsyncOpenAI(
    api_key=config.OPENAI_API_KEY,
    base_url=config.OPENAI_BASE_URL
)



# FastAPI app
app = FastAPI(title="NaviSearch API", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security), admin_required: bool = False):
    token = credentials.credentials
    if admin_required:
        if token != config.ADMIN_TOKEN:
            raise HTTPException(status_code=403, detail="Admin access required")
        return "admin"
    else:
        if token not in [config.ADMIN_TOKEN, config.USER_TOKEN]:
            raise HTTPException(status_code=401, detail="Invalid token")
        return "admin" if token == config.ADMIN_TOKEN else "user"

# Milvus connection
async def get_milvus_collection():
    try:
        if not connections.has_connection("default"):
            connections.connect(
                "default",
                host=config.MILVUS_HOST,
                port=config.MILVUS_PORT,
                token=config.MILVUS_TOKEN if config.MILVUS_TOKEN else None
            )
        # if utility.has_collection(config.MILVUS_COLLECTION_NAME):
        #     print(f"检测到旧的 Milvus 集合 '{config.MILVUS_COLLECTION_NAME}'，正在删除以更新 Schema...")
        #     utility.drop_collection(config.MILVUS_COLLECTION_NAME)
        #     print(f"旧集合 '{config.MILVUS_COLLECTION_NAME}' 已删除。")
        if not utility.has_collection(config.MILVUS_COLLECTION_NAME):
            # Create collection if it doesn't exist
            fields = [
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=36, is_primary=True),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=255),
                FieldSchema(name="original_file", dtype=DataType.VARCHAR, max_length=255),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
                FieldSchema(name="total_chunks", dtype=DataType.INT64),
                FieldSchema(name="tags", dtype=DataType.VARCHAR, max_length=2048),
                FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=4096),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024)
            ]

            schema = CollectionSchema(fields, "NaviSearch document chunks collection")
            collection = Collection(config.MILVUS_COLLECTION_NAME, schema)

            # Create index
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            collection.create_index("embedding", index_params)

        return Collection(config.MILVUS_COLLECTION_NAME)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Milvus connection error: {str(e)}")

def load_tag_dictionary() -> List[str]:
    """Load tag dictionary from file"""
    try:
        if Path(config.TAG_DIRECTORY).exists():
            with open(config.TAG_DIRECTORY, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Default tags
            default_tags = [
                "前端", "后端", "JavaScript", "Python", "React", "Vue", "Node.js",
                "机器学习", "人工智能", "数据科学", "Web开发", "移动开发",
                "架构", "微服务", "容器化", "Docker", "DevOps",
                "算法", "数据结构", "数据库", "API", "GraphQL",
                "框架", "库", "工具", "平台", "生态系统"
            ]
            save_tag_dictionary(default_tags)
            return default_tags
    except Exception:
        return []

def save_tag_dictionary(tags: List[str]):
    """Save tag dictionary to file"""
    os.makedirs(os.path.dirname(config.TAG_DIRECTORY), exist_ok=True)
    with open(config.TAG_DIRECTORY, 'w', encoding='utf-8') as f:
        json.dump(tags, f, ensure_ascii=False, indent=2)

# Initialize directories
def init_directories():
    """Initialize required directories"""
    for directory in [
        config.UPLOAD_DIR, 
        config.INGESTED_DIR, 
        config.SEPARATED_DIR, 
        config.CHUNKED_DIR,
        config.BASE_DATA_DIR / "prompts"
    ]:
        directory.mkdir(parents=True, exist_ok=True)

# API Endpoints

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_type: str = Depends(verify_token)
):
    """Upload file endpoint with relaxed restrictions"""
    if file.size > config.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size: {config.MAX_FILE_SIZE/1024/1024:.1f}MB")

    # Check file extension
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in config.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Supported: {', '.join(config.SUPPORTED_EXTENSIONS)}"
        )

    # Save file
    init_directories()
    file_id = uuid.uuid4().hex
    file_path = config.UPLOAD_DIR / f"{file_id}_{file.filename}"

    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)

    return {
        "message": "File uploaded successfully", 
        "filename": file.filename,
        "file_id": file_id,
        "file_type": file_extension
    }

@app.post("/api/ingest", response_model=IngestResponse)
async def ingest_documents(user_type: str = Depends(verify_token)):
    """Enhanced ingest documents with modular processing pipeline"""
    collection = await get_milvus_collection()
    tag_dictionary = load_tag_dictionary()
    
    init_directories()
    
    upload_files = list(config.UPLOAD_DIR.glob("*"))
    if not upload_files:
        return IngestResponse(
            success=True, 
            processed_files=0, 
            total_chunks=0,
            failed_files=[],
            message="No files to process"
        )

    processed_count = 0
    total_chunks = 0
    failed_files = []
    all_chunks = []

    processor_factory = DocumentProcessorFactory(config, openai_client)

    for file_path in upload_files:
        try:
            print(f"Processing file: {file_path.name}")
            
            # Move to ingested directory first
            ingested_path = config.INGESTED_DIR / file_path.name
            shutil.move(str(file_path), str(ingested_path))
            
            # Get processor based on file extension
            file_extension = file_path.suffix.lower()
            processor = processor_factory.get_processor(file_extension)
            
            if not processor:
                failed_files.append(f"{file_path.name}: Unsupported file type")
                continue
            
            # Process document through pipeline
            chunks = await processor.process_document(
                ingested_path, 
                tag_dictionary
            )
            
            if chunks:
                all_chunks.extend(chunks)
                total_chunks += len(chunks)
                processed_count += 1
                print(f"Successfully processed {file_path.name}: {len(chunks)} chunks")
            else:
                failed_files.append(f"{file_path.name}: Processing returned no chunks")
                
        except Exception as e:
            error_msg = f"{file_path.name}: {str(e)}"
            failed_files.append(error_msg)
            print(f"Error processing {file_path}: {e}")
            continue

    # Insert chunks into Milvus
    if all_chunks:
        try:
            data = [
                [chunk.chunk_id for chunk in all_chunks],
                [chunk.content for chunk in all_chunks],
                [chunk.source for chunk in all_chunks],
                [chunk.original_file for chunk in all_chunks],
                [chunk.chunk_index for chunk in all_chunks],
                [chunk.total_chunks for chunk in all_chunks],
                [json.dumps(chunk.tags) for chunk in all_chunks],
                [json.dumps(chunk.metadata) for chunk in all_chunks],
                [chunk.embedding for chunk in all_chunks]
            ]

            collection.insert(data)
            collection.load()
            print(f"Inserted {len(all_chunks)} chunks into Milvus")

            # Save to JSONL
            async with aiofiles.open(config.DOCUMENTS_FILE, 'a', encoding='utf-8') as f:
                for chunk in all_chunks:
                    chunk_dict = {
                        "chunk_id": chunk.chunk_id,
                        "content": chunk.content,
                        "source": chunk.source,
                        "original_file": chunk.original_file,
                        "chunk_index": chunk.chunk_index,
                        "total_chunks": chunk.total_chunks,
                        "tags": chunk.tags,
                        "metadata": chunk.metadata,
                        "timestamp": datetime.now().isoformat()
                    }
                    await f.write(json.dumps(chunk_dict, ensure_ascii=False) + '\n')

        except Exception as e:
            print(f"Error inserting into Milvus: {e}")
            failed_files.append(f"Database insertion error: {str(e)}")

    return IngestResponse(
        success=len(failed_files) == 0,
        processed_files=processed_count,
        total_chunks=total_chunks,
        failed_files=failed_files,
        message=f"Processed {processed_count} files into {total_chunks} chunks. {len(failed_files)} failures."
    )

@app.post("/api/search")
async def search_documents(
    query: SearchQuery,
    user_type: str = Depends(verify_token)
):
    """Enhanced search with chunk support"""
    collection = await get_milvus_collection()

    # Get query embedding
    if query.query:
        query_embedding = await get_embedding(query.query)
    else:
        # Use zero vector for empty query
        query_embedding = [0.0] * 1024

    # Search in Milvus
    search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
    results = collection.search(
        [query_embedding],
        "embedding",
        search_params,
        limit=config.RETRIEVAL_TOP_K,
        output_fields=["chunk_id", "content", "source", "original_file", 
                      "chunk_index", "total_chunks", "tags", "metadata"]
    )

    # Convert to SearchResult objects
    search_results = []
    for hit in results[0]:
        tags = json.loads(hit.entity.get("tags", "[]"))
        metadata = json.loads(hit.entity.get("metadata", "{}"))

        result = SearchResult(
            id=hit.entity.get("chunk_id"),
            content=hit.entity.get("content"),
            source=hit.entity.get("source"),
            original_file=hit.entity.get("original_file"),
            tags=tags,
            similarity=float(hit.score),
            chunk_info={
                "chunk_index": hit.entity.get("chunk_index"),
                "total_chunks": hit.entity.get("total_chunks"),
                "metadata": metadata
            }
        )
        search_results.append(result)

    # Apply tag filters
    filtered_results = []
    for result in search_results:
        # Check must tags
        if query.must_tags:
            if not all(any(tag.lower() in doc_tag.lower() for doc_tag in result.tags)
                      for tag in query.must_tags):
                continue

        # Check must not tags
        if query.must_not_tags:
            if any(any(tag.lower() in doc_tag.lower() for doc_tag in result.tags)
                  for tag in query.must_not_tags):
                continue

        # Calculate like score
        like_score = 0
        for tag in query.like_tags:
            if any(tag.lower() in doc_tag.lower() for doc_tag in result.tags):
                like_score += 1

        result.like_score = like_score
        filtered_results.append(result)

    # Sort by like score then similarity
    filtered_results.sort(key=lambda x: (x.like_score, x.similarity), reverse=True)

    # Limit results
    final_results = filtered_results[:config.RERANK_TOP_K]

    # Calculate recommended tags
    recommended_tags = calculate_tag_eig(final_results)
    print(final_results)
    print(recommended_tags)
    return {
        "results": final_results,
        "recommended_tags": recommended_tags,
        "total_found": len(final_results)
    }

@app.get("/api/document/{file_id}")
async def get_original_document(
    file_id: str,
    user_type: str = Depends(verify_token)
):
    """Get original document file"""
    # Look for file in ingested directory
    for file_path in config.INGESTED_DIR.glob(f"{file_id}_*"):
        if file_path.is_file():
            return {
                "file_id": file_id,
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            }
    
    raise HTTPException(status_code=404, detail="Original document not found")

@app.get("/api/tags")
async def get_tags(user_type: str = Depends(verify_token)):
    """Get tag dictionary"""
    return {"tags": load_tag_dictionary()}

@app.put("/api/tags")
async def update_tags(
    tag_update: TagUpdate,
    user_type: str = Depends(lambda creds=Depends(security): verify_token(creds, admin_required=True))
):
    """Update tag dictionary (admin only)"""
    save_tag_dictionary(tag_update.tags)
    return {"message": "Tag dictionary updated successfully"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/stats")
async def get_stats(user_type: str = Depends(verify_token)):
    """Get system statistics"""
    try:
        collection = await get_milvus_collection()
        collection.load()
        total_chunks = collection.num_entities
        
        # Count files in each directory
        upload_count = len(list(config.UPLOAD_DIR.glob("*")))
        ingested_count = len(list(config.INGESTED_DIR.glob("*")))
        
        return {
            "total_chunks": total_chunks,
            "files_pending": upload_count,
            "files_ingested": ingested_count,
            "supported_formats": list(config.SUPPORTED_EXTENSIONS)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")

if __name__ == "__main__":
    init_directories()
    uvicorn.run(app, host="0.0.0.0", port=8000)
import openai
import json
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from models import SearchResult
from pathlib import Path
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
async def get_embedding(text: str) -> List[float]:
    """Get embedding from OpenAI API"""
    try:
        response = await openai_client.embeddings.create(
            model=config.OPENAI_EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding error: {str(e)}")

async def generate_tags(content: str, tag_dictionary: List[str]) -> List[str]:
    """Generate tags using LLM based on tag dictionary"""
    try:
        prompt = f"""
Based on the following content, select the most relevant tags from the provided tag dictionary.
Return only the selected tags as a JSON array, maximum 8 tags.

Content: {content[:1000]}...

Tag Dictionary: {json.dumps(tag_dictionary)}

Response format: ["tag1", "tag2", "tag3"]
IMPORTANT: Only return the JSON array. Do not include any other text, explanation, or markdown code block fences (```json).
"""

        response = await openai_client.chat.completions.create(
            model=config.OPENAI_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )

        tags_text = response.choices[0].message.content.strip()
        print(f"原始LLM响应: {tags_text}") # 调试输出原始响应

        json_str = ""
        # 尝试查找 '[' 和 ']' 的位置
        start_index = tags_text.find("[")
        end_index = tags_text.rfind("]")

        if start_index != -1 and end_index != -1 and end_index > start_index:
            # 提取 '[' 到 ']' 之间的内容，包括方括号
            json_str = tags_text[start_index : end_index + 1]
            print(f"提取的可能JSON字符串: {json_str}") # 调试输出提取到的字符串
        else:
            print(f"未能在LLM响应中找到有效的JSON数组结构 (方括号不匹配或顺序错误): {tags_text}")
            return [] # 如果没有找到有效的方括号，直接返回空列表

        try:
            tags = json.loads(json_str)

            # 进一步验证 tags 是一个列表，并且其中的元素都是字符串
            if not isinstance(tags, list):
                raise ValueError("LLM响应的JSON不是一个列表")
            if not all(isinstance(tag, str) for tag in tags):
                raise ValueError("LLM响应的JSON列表包含非字符串元素")

        except json.JSONDecodeError as e:
            print(f"JSON解析错误 (提取后): {e} - 尝试解析的字符串: {json_str}")
            return []
        except ValueError as e:
            print(f"JSON内容验证失败: {e}")
            return []

        # Validate tags are in dictionary
        valid_tags = [tag for tag in tags if tag in tag_dictionary]
        return valid_tags[:8]

    except Exception as e:
        print(f"Tag generation error: {e}")
        return []

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

def calculate_tag_eig(results: List[SearchResult]) -> List[Dict[str, Any]]:
    """Calculate Expected Information Gain for tags"""
    total_results = len(results)
    if total_results == 0:
        return []

    tag_frequency = {}
    for doc in results:
        for tag in doc.tags:
            tag_frequency[tag] = tag_frequency.get(tag, 0) + 1

    tags_with_eig = []
    for tag, freq in tag_frequency.items():
        eig = abs(freq - total_results / 2)
        tags_with_eig.append({
            "tag": tag,
            "frequency": freq,
            "eig": eig
        })

    return sorted(tags_with_eig, key=lambda x: x["eig"], reverse=True)[:config.TAGS_TOP_K]
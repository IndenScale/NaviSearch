import os
import json
import uuid
import base64
from typing import List, Dict, Any, Optional
from pathlib import Path
from abc import ABC, abstractmethod
import asyncio
import tempfile
import shutil

import aiofiles
from langchain.text_splitter import RecursiveCharacterTextSplitter

import pypandoc # Import pypandoc

import openai
from datetime import datetime
from utils import load_tag_dictionary, get_embedding, generate_tags # Assuming these are in your utils.py

# Configuration (assuming config object is passed or accessed globally)
# from enhanced_main import config # Or however you manage config access here

tag_dictionary = load_tag_dictionary()
class DocumentChunk:
    """Represents a document chunk with metadata"""
    def __init__(self, chunk_id: str, content: str, source: str, original_file: str,
                 chunk_index: int, total_chunks: int, tags: List[str],
                 embedding: List[float], metadata: Dict[str, Any] = None):
        self.chunk_id = chunk_id
        self.content = content
        self.source = source
        self.original_file = original_file
        self.chunk_index = chunk_index
        self.total_chunks = total_chunks
        self.tags = tags
        self.embedding = embedding
        self.metadata = metadata or {}


class BaseDocumentProcessor(ABC):
    """Base class for document processors"""

    def __init__(self, config, openai_client):
        self.config = config
        self.openai_client = openai_client
        self.text_splitter = RecursiveCharacterTextSplitter(
            separators=config.CHUNK_SEPARATORS,
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            length_function=len,
        )

    @abstractmethod
    async def extract_content(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract content from document.
        Should return a dictionary:
        {
            'text': str,  # Extracted text content
            'images': List[Dict[str, Any]]  # List of images, each dict containing 'data' (bytes) and 'name' (str)
                                             # e.g., [{'data': b'...', 'name': 'image1.png'}, ...]
        }
        """
        pass

    async def process_images(self, images: List[Dict[str, Any]]) -> List[str]:
        """Process images and return descriptions"""
        descriptions = []

        if not images:
            return descriptions

        prompt_template = await self.load_vlm_prompt_template()

        for i, image_info in enumerate(images):
            try:
                if 'data' in image_info and isinstance(image_info['data'], bytes):
                    base64_image = base64.b64encode(image_info['data']).decode('utf-8')
                    description = await self.describe_image_with_vlm(base64_image, image_info.get('name', f'image_{i+1}'), prompt_template)
                    if description:
                        descriptions.append(f"[图像 {image_info.get('name', i+1)}]: {description}")
                else:
                    print(f"Skipping image {image_info.get('name', i+1)} due to missing or invalid 'data'.")
                    descriptions.append(f"[图像 {image_info.get('name', i+1)}]: 图像数据无效")

            except Exception as e:
                print(f"Error processing image {image_info.get('name', i+1)}: {e}")
                descriptions.append(f"[图像 {image_info.get('name', i+1)}]: 图像处理失败")

        return descriptions

    async def load_vlm_prompt_template(self) -> str:
        """Load VLM prompt template"""
        try:
            template_path = Path(self.config.VLM_PROMPT_TEMPLATE)
            if template_path.exists():
                async with aiofiles.open(template_path, 'r', encoding='utf-8') as f:
                    return await f.read()
            else:
                default_template = """请详细描述这张图片的内容，包括：
1. 主要对象和场景
2. 重要的文字信息（如果有）
3. 图表或数据的关键信息（如果适用）
4. 整体的视觉特征和风格

请用中文回答，保持描述准确和详细。"""
                template_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(template_path, 'w', encoding='utf-8') as f:
                    await f.write(default_template)
                return default_template
        except Exception as e:
            print(f"Error loading VLM template: {e}")
            return "请描述这张图片的内容。"

    async def describe_image_with_vlm(self, image_base64: str, image_name: str, prompt_template: str) -> str:
        """Use VLM to describe a base64 encoded image"""
        try:
            image_media_type = "image/jpeg"
            if image_name.lower().endswith(".png"):
                image_media_type = "image/png"
            elif image_name.lower().endswith(".gif"):
                image_media_type = "image/gif"
            elif image_name.lower().endswith(".webp"):
                image_media_type = "image/webp"

            response = await self.openai_client.chat.completions.create(
                model=self.config.OPENAI_VLM_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_template},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_media_type};base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"VLM description error for {image_name}: {e}")
            return f"图像描述生成失败: {str(e)}"

    async def chunk_content(self, content: str, source: str, original_file: str,
                            tag_dictionary: List[str]) -> List[DocumentChunk]:
        chunks = []
        text_chunks = self.text_splitter.split_text(content)
        total_text_chunks = len(text_chunks)

        for i, chunk_text in enumerate(text_chunks):
            try:
                embedding = await get_embedding(chunk_text)
                tags = await generate_tags(chunk_text, tag_dictionary)

                chunk = DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    content=chunk_text,
                    source=source,
                    original_file=original_file,
                    chunk_index=i,
                    total_chunks=total_text_chunks,
                    tags=tags,
                    embedding=embedding,
                    metadata={
                        "chunk_length": len(chunk_text),
                        "processing_timestamp": datetime.now().isoformat()
                    }
                )
                chunks.append(chunk)
            except Exception as e:
                print(f"Error processing chunk {i} for {original_file}: {e}")
                continue
        return chunks

    async def save_separated_content(self, file_path: Path, content: str,
                                     images: List[Dict[str, Any]]) -> Path:
        """
        Saves the (potentially VLM-enhanced) markdown content and original images.
        'images' dicts should contain 'data' (bytes) and 'name' (str).
        """
        separated_dir = self.config.SEPARATED_DIR / file_path.stem
        separated_dir.mkdir(parents=True, exist_ok=True)

        md_file = separated_dir / "content_with_vlm.md"
        async with aiofiles.open(md_file, 'w', encoding='utf-8') as f:
            await f.write(content)

        if images:
            images_out_dir = separated_dir / "images"
            images_out_dir.mkdir(exist_ok=True)
            for i, image_info in enumerate(images):
                if 'data' in image_info and 'name' in image_info:
                    image_filename = image_info['name']
                    image_file_path = images_out_dir / image_filename
                    try:
                        async with aiofiles.open(image_file_path, 'wb') as f:
                            await f.write(image_info['data'])
                    except Exception as e:
                        print(f"Error saving image {image_filename}: {e}")
                else:
                    print(f"Skipping save for image {i+1} due to missing data or name.")
        return separated_dir

    async def process_document(self, file_path: Path, tag_dictionary: List[str]) -> List[DocumentChunk]:
        """Main processing pipeline"""
        try:
            extracted = await self.extract_content(file_path)
            text_content = extracted.get('text', '')
            original_images_data = extracted.get('images', [])

            image_descriptions = await self.process_images(original_images_data)

            combined_content = text_content
            if image_descriptions:
                combined_content += "\n\n" + "\n\n".join(image_descriptions)

            await self.save_separated_content(file_path, combined_content, original_images_data)

            chunks = await self.chunk_content(
                combined_content,
                str(file_path.name),
                str(file_path.name),
                tag_dictionary
            )
            return chunks
        except Exception as e:
            print(f"Error in document processing pipeline for {file_path.name}: {e}")
            return []


class TextDocumentProcessor(BaseDocumentProcessor):
    """Processor for plain text documents (.txt, .md)"""
    async def extract_content(self, file_path: Path) -> Dict[str, Any]:
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                text = await f.read()
            return {'text': text, 'images': []}
        except Exception as e:
            print(f"Error extracting content from text file {file_path.name}: {e}")
            return {'text': '', 'images': []}

## PyPandoc-Based DOCX Processor (根据您提供的正确调用方式进行最终修正)

class DocxProcessor(BaseDocumentProcessor):
    """
    Processor for DOCX documents using pypandoc for conversion to markdown.
    This allows for more controlled extraction of text and images.
    """
    async def extract_content(self, file_path: Path) -> Dict[str, Any]:
        extracted_text = ""
        images_data_list = []

        # 创建一个临时目录用于 pypandoc 的输出
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir_path = Path(temp_dir_str)
            output_markdown_file = temp_dir_path / (file_path.stem + ".md")
            media_output_dir = temp_dir_path / "media" # Pandoc 媒体输出目录

            try:
                # 确保 media_output_dir 存在，pypandoc 才能把图片放进去
                media_output_dir.mkdir(parents=True, exist_ok=True)

                # 异步执行 pypandoc 转换
                # 使用您提供的正确的 `outputfile` 参数和 `extra_args` 结构
                await asyncio.to_thread(pypandoc.convert_file,
                    str(file_path),                  # src_file_path
                    to='markdown',                   # to
                    outputfile=str(output_markdown_file), # outputfile
                    extra_args=[
                        '--extract-media',           # --extract-media 作为一个单独的参数
                        str(media_output_dir),       # 媒体目录路径作为 --extract-media 的值
                        '--wrap=none'                # 其他额外参数
                    ]
                )

                # 读取提取的 markdown 文本
                if output_markdown_file.exists():
                    async with aiofiles.open(output_markdown_file, 'r', encoding='utf-8') as f:
                        extracted_text = await f.read()
                else:
                    print(f"PyPandoc 未能生成预期的 markdown 文件: {output_markdown_file}")

                # 收集提取的图片
                if media_output_dir.exists() and media_output_dir.is_dir():
                    for image_file in media_output_dir.glob('*.*'):
                        if image_file.is_file() and image_file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                            try:
                                async with aiofiles.open(image_file, 'rb') as f_img:
                                    image_data = await f_img.read()
                                images_data_list.append({'data': image_data, 'name': image_file.name})
                            except Exception as e_img:
                                print(f"读取图片文件 {image_file.name} 时出错: {e_img}")
                else:
                    print(f"未找到 pypandoc 提取的媒体目录: {media_output_dir}")

            except Exception as e:
                print(f"PyPandoc 处理 {file_path.name} 时出错: {e}")
                return {'text': '', 'images': []}

        return {'text': extracted_text, 'images': images_data_list}


## 其他文件类型的占位符处理器 (保持不变)

class PdfProcessor(BaseDocumentProcessor):
    """
    PDF 处理器的占位符。
    您需要在此处实现内容和图片提取逻辑。
    可以考虑使用 PyPDF2, pdfminer.six 或 PyMuPDF 等库。
    """
    async def extract_content(self, file_path: Path) -> Dict[str, Any]:
        print(f"PDF 文件 {file_path.name} 的处理尚未实现。")
        return {'text': '', 'images': []}

class PptxProcessor(BaseDocumentProcessor):
    """
    PPTX 处理器的占位符。
    您需要在此处实现内容和图片提取逻辑。
    可以考虑使用 python-pptx 等库。
    """
    async def extract_content(self, file_path: Path) -> Dict[str, Any]:
        print(f"PPTX 文件 {file_path.name} 的处理尚未实现。")
        return {'text': '', 'images': []}

class XlsxProcessor(BaseDocumentProcessor):
    """
    XLSX 处理器的占位符。
    您需要在此处实现内容和图片提取逻辑。
    可以考虑使用 openpyxl 或 pandas 等库。
    """
    async def extract_content(self, file_path: Path) -> Dict[str, Any]:
        print(f"XLSX 文件 {file_path.name} 的处理尚未实现。")
        return {'text': '', 'images': []}

class HtmlProcessor(BaseDocumentProcessor):
    """
    HTML 处理器的占位符。
    您需要在此处实现内容和图片提取逻辑。
    可以考虑使用 BeautifulSoup 等库。
    """
    async def extract_content(self, file_path: Path) -> Dict[str, Any]:
        print(f"HTML 文件 {file_path.name} 的处理尚未实现。")
        return {'text': '', 'images': []}

# 可以根据需要添加其他 ODF 处理器占位符:
# class OdtProcessor(BaseDocumentProcessor):
#     async def extract_content(self, file_path: Path) -> Dict[str, Any]:
#         print(f"ODT processing for {file_path.name} is not yet implemented.")
#         return {'text': '', 'images': []}

# class OdpProcessor(BaseDocumentProcessor):
#     async def extract_content(self, file_path: Path) -> Dict[str, Any]:
#         print(f"ODP processing for {file_path.name} is not yet implemented.")
#         return {'text': '', 'images': []}

# class OdsProcessor(BaseDocumentProcessor):
#     async def extract_content(self, file_path: Path) -> Dict[str, Any]:
#         print(f"ODS processing for {file_path.name} is not yet implemented.")
#         return {'text': '', 'images': []}

# class RtfProcessor(BaseDocumentProcessor):
#     async def extract_content(self, file_path: Path) -> Dict[str, Any]:
#         print(f"RTF processing for {file_path.name} is not yet implemented.")
#         return {'text': '', 'images': []}


## 更新后的文档处理器工厂 (保持不变)

class DocumentProcessorFactory:
    def __init__(self, config, openai_client):
        self.config = config
        self.openai_client = openai_client
        self._processors = {
            '.pdf': PdfProcessor(config, openai_client),
            '.docx': DocxProcessor(config, openai_client), # DOCX 现在使用优化的 pypandoc 处理器
            '.pptx': PptxProcessor(config, openai_client),
            '.xlsx': XlsxProcessor(config, openai_client),
            '.txt': TextDocumentProcessor(config, openai_client),
            '.md': TextDocumentProcessor(config, openai_client),
            '.html': HtmlProcessor(config, openai_client),
            '.htm': HtmlProcessor(config, openai_client),
            # '.rtf': RtfProcessor(config, openai_client),
            # '.odt': OdtProcessor(config, openai_client),
            # '.odp': OdpProcessor(config, openai_client),
            # '.ods': OdsProcessor(config, openai_client),
        }

    def get_processor(self, file_extension: str) -> Optional[BaseDocumentProcessor]:
        return self._processors.get(file_extension.lower())
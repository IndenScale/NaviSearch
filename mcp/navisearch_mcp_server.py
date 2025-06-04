#!/usr/bin/env python3
# navisearch_mcp_server.py
import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import httpx
from urllib.parse import urljoin

# MCP imports
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio


# Configuration
class NaviSearchMCPConfig:
    def __init__(self):
        self.navisearch_base_url = os.getenv("NAVISEARCH_BASE_URL", "http://localhost:8000")
        self.admin_token = os.getenv("NAVISEARCH_ADMIN_TOKEN", "admin_secret_token")
        self.user_token = os.getenv("NAVISEARCH_USER_TOKEN", "user_secret_token")
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))
        self.max_results = int(os.getenv("MAX_RESULTS", "10"))

        # Logging configuration
        log_level = os.getenv("LOG_LEVEL", "DEBUG")  # Change to DEBUG for troubleshooting

        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Configure logging to both file and console
        log_file = log_dir / "navisearch_mcp.log"

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level))

        # Remove existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # File handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)  # Less verbose on console
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Logging initialized. Log file: {log_file}")
        self.logger.info(f"Log level: {log_level}")


config = NaviSearchMCPConfig()

# MCP Server instance
server = Server("navisearch-mcp")

# HTTP client for NaviSearch API
http_client = httpx.AsyncClient(timeout=config.request_timeout)


class NaviSearchClient:
    """Client for NaviSearch API"""

    def __init__(self, base_url: str, admin_token: str, user_token: str):
        self.base_url = base_url
        self.admin_token = admin_token
        self.user_token = user_token

    def _get_headers(self, admin_required: bool = False) -> Dict[str, str]:
        token = self.admin_token if admin_required else self.user_token
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    async def search_documents(self, query: str, must_tags: List[str] = None,
                             must_not_tags: List[str] = None,
                             like_tags: List[str] = None) -> Dict[str, Any]:
        """Search documents in NaviSearch"""
        url = urljoin(self.base_url, "/api/search")
        payload = {
            "query": query,
            "must_tags": must_tags or [],
            "must_not_tags": must_not_tags or [],
            "like_tags": like_tags or []
        }

        config.logger.debug(f"Search request URL: {url}")
        config.logger.debug(f"Search payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")

        headers = self._get_headers()
        config.logger.debug(f"Request headers: {headers}")

        try:
            response = await http_client.post(url, json=payload, headers=headers)
            config.logger.debug(f"Response status: {response.status_code}")
            config.logger.debug(f"Response headers: {dict(response.headers)}")

            response.raise_for_status()
            result = response.json()
            config.logger.debug(f"Response data keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

            return result
        except Exception as e:
            config.logger.error(f"Search request failed: {e}")
            config.logger.error(f"Response content: {getattr(response, 'text', 'No response content')}")
            raise

    async def get_tags(self) -> List[str]:
        """Get available tags"""
        url = urljoin(self.base_url, "/api/tags")
        headers = self._get_headers()
        response = await http_client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()["tags"]

    async def get_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        url = urljoin(self.base_url, "/api/stats")
        headers = self._get_headers()
        response = await http_client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def upload_file(self, file_path: str) -> Dict[str, Any]:
        """Upload a file"""
        url = urljoin(self.base_url, "/api/upload")
        headers = {"Authorization": f"Bearer {self.admin_token}"}

        with open(file_path, 'rb') as f:
            files = {"file": (Path(file_path).name, f, "application/octet-stream")}
            response = await http_client.post(url, files=files, headers=headers)
            response.raise_for_status()
            return response.json()

    async def ingest_documents(self) -> Dict[str, Any]:
        """Ingest uploaded documents"""
        url = urljoin(self.base_url, "/api/ingest")
        headers = self._get_headers(admin_required=True)
        response = await http_client.post(url, headers=headers)
        response.raise_for_status()
        return response.json()


# Initialize NaviSearch client
navisearch_client = NaviSearchClient(
    config.navisearch_base_url,
    config.admin_token,
    config.user_token
)


def _format_tags(tags) -> str:
    """Format tags safely - handle both list and dict formats"""
    if not tags:
        return ""

    try:
        if isinstance(tags, list):
            # Handle list of strings or dicts
            tag_strings = []
            for tag in tags:
                if isinstance(tag, str):
                    tag_strings.append(tag)
                elif isinstance(tag, dict):
                    # If tag is a dict, try to extract string representation
                    if 'name' in tag:
                        tag_strings.append(str(tag['name']))
                    elif 'tag' in tag:
                        tag_strings.append(str(tag['tag']))
                    else:
                        tag_strings.append(str(tag))
                else:
                    tag_strings.append(str(tag))
            return ', '.join(tag_strings)
        elif isinstance(tags, dict):
            # If tags is a dict, try to extract meaningful representation
            if 'tags' in tags:
                return _format_tags(tags['tags'])
            else:
                return str(tags)
        else:
            return str(tags)
    except Exception as e:
        config.logger.warning(f"Error formatting tags {tags}: {e}")
        return str(tags)


@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="search_documents",
            description="Search for documents in the NaviSearch knowledge base",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text"
                    },
                    "must_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags that must be present (AND logic)",
                        "default": []
                    },
                    "must_not_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags that must not be present (NOT logic)",
                        "default": []
                    },
                    "like_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Preferred tags for ranking (OR logic)",
                        "default": []
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_available_tags",
            description="Get list of available tags in the knowledge base",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="get_system_stats",
            description="Get knowledge base statistics (total chunks, files, etc.)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="upload_document",
            description="Upload a document to the knowledge base",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to upload"
                    }
                },
                "required": ["file_path"]
            }
        ),
        types.Tool(
            name="ingest_documents",
            description="Process and index uploaded documents",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> List[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls"""

    config.logger.debug(f"Tool call received: {name}")
    config.logger.debug(f"Arguments type: {type(arguments)}")
    config.logger.debug(f"Arguments content: {json.dumps(arguments, ensure_ascii=False, indent=2) if arguments else 'None'}")

    if arguments is None:
        arguments = {}

    try:
        if name == "search_documents":
            config.logger.debug("Processing search_documents request")

            # Extract and validate query parameter
            query = arguments.get("query", "")
            if not isinstance(query, str):
                query = str(query) if query is not None else ""

            config.logger.debug(f"Query: '{query}'")

            # Helper function to safely convert parameters to list
            def _ensure_list(param_value, param_name="parameter"):
                """Convert any parameter value to a list of strings"""
                config.logger.debug(f"Processing {param_name}: {param_value} (type: {type(param_value)})")

                if param_value is None:
                    return []

                if isinstance(param_value, list):
                    # Ensure all items are strings
                    return [str(item) for item in param_value]

                if isinstance(param_value, str):
                    return [param_value] if param_value.strip() else []

                if isinstance(param_value, dict):
                    # Handle empty dict
                    if not param_value:
                        return []
                    # Try common keys that might contain the actual list
                    for key in ['value', 'values', 'items', 'list']:
                        if key in param_value:
                            return _ensure_list(param_value[key], f"{param_name}.{key}")
                    # If no common keys, convert dict values to list
                    return [str(v) for v in param_value.values() if v is not None]

                # For any other type, try to convert to string and wrap in list
                try:
                    str_value = str(param_value).strip()
                    return [str_value] if str_value else []
                except Exception as e:
                    config.logger.warning(f"Could not convert {param_name} to string: {e}")
                    return []

            # Process tag parameters
            must_tags = _ensure_list(arguments.get("must_tags"), "must_tags")
            must_not_tags = _ensure_list(arguments.get("must_not_tags"), "must_not_tags")
            like_tags = _ensure_list(arguments.get("like_tags"), "like_tags")

            config.logger.info(f"Final parameters - query: '{query}', must_tags: {must_tags}, must_not_tags: {must_not_tags}, like_tags: {like_tags}")

            results = await navisearch_client.search_documents(
                query=query,
                must_tags=must_tags,
                must_not_tags=must_not_tags,
                like_tags=like_tags
            )

            config.logger.debug(f"Search results type: {type(results)}")
            config.logger.debug(f"Search results keys: {list(results.keys()) if isinstance(results, dict) else 'Not a dict'}")

            # Format results for MCP response
            response_text = f"## Search Results for: '{query}'\n\n"
            response_text += f"**Found {results.get('total_found', 0)} results**\n\n"

            for i, result in enumerate(results.get('results', []), 1):
                config.logger.debug(f"Processing result {i}: {list(result.keys()) if isinstance(result, dict) else type(result)}")

                response_text += f"### Result {i}\n"
                response_text += f"**File:** {result.get('original_file', 'N/A')}\n"
                response_text += f"**Source:** {result.get('source', 'N/A')}\n"
                response_text += f"**Similarity:** {result.get('similarity', 0):.3f}\n"

                # Handle chunk info safely
                if result.get('chunk_info'):
                    chunk_info = result['chunk_info']
                    response_text += f"**Chunk:** {chunk_info.get('chunk_index', 'N/A')}/{chunk_info.get('total_chunks', 'N/A')}\n"

                # Handle tags safely using the helper function
                tags = result.get('tags')
                config.logger.debug(f"Result tags: {tags} (type: {type(tags)})")

                if tags:
                    try:
                        formatted_tags = _format_tags(tags)
                        if formatted_tags:
                            response_text += f"**Tags:** {formatted_tags}\n"
                        config.logger.debug(f"Formatted tags: {formatted_tags}")
                    except Exception as e:
                        config.logger.error(f"Error formatting tags for result {i}: {e}")
                        config.logger.error(f"Problematic tags: {tags}")

                response_text += f"**Content:**\n{result.get('content', 'No content available')}\n\n"
                response_text += "---\n\n"

            # Handle recommended tags safely
            if results.get('recommended_tags'):
                try:
                    formatted_recommended = _format_tags(results['recommended_tags'])
                    if formatted_recommended:
                        response_text += f"**Recommended Tags:** {formatted_recommended}\n"
                except Exception as e:
                    config.logger.error(f"Error formatting recommended tags: {e}")

            config.logger.info(f"Search completed successfully, returning {len(results.get('results', []))} results")
            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_available_tags":
            config.logger.info("Getting available tags")
            tags_response = await navisearch_client.get_tags()
            tags = tags_response

            response_text = "## Available Tags\n\n"
            response_text += f"Total tags: {len(tags)}\n\n"
            response_text += "### Tags List:\n"
            for tag in sorted(tags):
                response_text += f"- {tag}\n"

            return [types.TextContent(type="text", text=response_text)]

        elif name == "get_system_stats":
            config.logger.info("Getting system statistics")
            stats = await navisearch_client.get_stats()

            response_text = "## NaviSearch System Statistics\n\n"
            response_text += f"**Total Chunks:** {stats.get('total_chunks', 0)}\n"
            response_text += f"**Files Pending:** {stats.get('files_pending', 0)}\n"
            response_text += f"**Files Ingested:** {stats.get('files_ingested', 0)}\n"
            response_text += f"**Supported Formats:** {', '.join(stats.get('supported_formats', []))}\n"

            return [types.TextContent(type="text", text=response_text)]

        elif name == "upload_document":
            file_path = arguments.get("file_path")
            if not file_path:
                raise ValueError("file_path is required")

            if not Path(file_path).exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            config.logger.info(f"Uploading file: {file_path}")
            result = await navisearch_client.upload_file(file_path)

            response_text = "## File Upload Result\n\n"
            response_text += f"**Status:** {result['message']}\n"
            response_text += f"**Filename:** {result['filename']}\n"
            response_text += f"**File ID:** {result['file_id']}\n"
            response_text += f"**File Type:** {result['file_type']}\n"
            response_text += "\n*Note: Run 'ingest_documents' to process this file.*\n"

            return [types.TextContent(type="text", text=response_text)]

        elif name == "ingest_documents":
            config.logger.info("Ingesting documents")
            result = await navisearch_client.ingest_documents()

            response_text = "## Document Ingestion Result\n\n"
            response_text += f"**Success:** {result['success']}\n"
            response_text += f"**Processed Files:** {result['processed_files']}\n"
            response_text += f"**Total Chunks:** {result['total_chunks']}\n"
            response_text += f"**Message:** {result['message']}\n"

            if result.get('failed_files'):
                response_text += f"\n**Failed Files:**\n"
                for error in result['failed_files']:
                    response_text += f"- {error}\n"

            return [types.TextContent(type="text", text=response_text)]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        config.logger.error(f"Error in tool {name}: {str(e)}")
        config.logger.error(f"Exception type: {type(e)}")
        config.logger.error(f"Traceback:", exc_info=True)
        error_msg = f"Error executing {name}: {str(e)}"
        return [types.TextContent(type="text", text=error_msg)]


async def main():
    """Main entry point"""
    config.logger.info("Starting NaviSearch MCP Server")

    # Test connection to NaviSearch
    try:
        stats = await navisearch_client.get_stats()
        config.logger.info(f"Connected to NaviSearch: {stats['total_chunks']} chunks available")
    except Exception as e:
        config.logger.error(f"Failed to connect to NaviSearch: {e}")
        config.logger.error("Please ensure NaviSearch service is running and accessible")
        # Don't exit on connection failure - let MCP server start anyway

    config.logger.info("MCP Server ready for connections...")

    # Run MCP server
    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            config.logger.info("MCP Server streams established")
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="navisearch-mcp",
                    server_version="1.0.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )
    except Exception as e:
        config.logger.error(f"MCP Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
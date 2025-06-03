# NaviSearch: Tag-Enhanced Semantic Search Engine

NaviSearch is a lightweight, tag-enhanced semantic search engine designed to streamline the process of finding relevant information within a collection of documents. It's particularly useful for small teams dealing with a corpus of unstructured or semi-structured textual evidence, such as in network security assessments, research, or knowledge management.

## The Challenge NaviSearch Solves

In many analytical tasks, especially network security assessments, users often provide a large volume of diverse, unorganized evidence (documents, logs, reports). Analysts (like security engineers) need to sift through this data to find specific pieces of information that align with predefined checklist items or areas of concern. This process is often manual, time-consuming, and prone to inconsistencies.

The core challenge lies in bridging the gap between:
1.  **User knowledge**: Users understand their systems and the content of the documents they provide.
2.  **Analyst knowledge**: Analysts understand the assessment criteria and what constitutes relevant evidence.

Manually organizing and tagging this data is a burden neither party wants to fully own. NaviSearch aims to automate and assist in this crucial "evidence discovery" phase.

## How NaviSearch Works

NaviSearch combines semantic search with a flexible tagging system to provide a powerful and intuitive search experience.

1.  **File Upload & Ingestion**:
    * Users upload their documents (UTF-8 text files) through the web interface.
    * The backend validates and temporarily stores these files.
    * During the **ingestion** process:
        * Each document's content is read.
        * A semantic **embedding** (a vector representation of the text's meaning) is generated using an OpenAI-compatible embedding model (e.g., `text-embedding-v3` via DashScope).
        * Relevant **tags** are automatically generated for the document using an LLM (e.g., `deepseek-v3` via DashScope). These tags are chosen from a predefined, centrally managed **tag dictionary**.
        * The document content, its source, generated tags, and the semantic embedding are stored in a **Milvus** vector database. Milvus is optimized for efficient similarity searches on high-dimensional vectors.
        * Metadata is also saved to a `documents.jsonl` file for backup or other uses.

2.  **Tag Dictionary**:
    * A central `tag_directory.json` file stores all valid tags that can be assigned to documents or used in queries.
    * Administrators can modify this dictionary through a dedicated interface, ensuring consistency and relevance of tags.

3.  **Search Functionality**:
    * Users enter a **search query** (natural language).
    * They can augment their query with **tags** using specific prefixes:
        * `+tag`: **Must Include** - Results *must* contain this tag.
        * `-tag`: **Must Not Include** - Results *must not* contain this tag.
        * `~tag` (or `tag` without prefix): **Like/Boost** - Results containing this tag are preferred/boosted.
    * The backend performs a hybrid search:
        * **Semantic Search**: The query string is embedded, and Milvus finds documents with the most similar embeddings (cosine similarity). This is the `RETRIEVAL_TOP_K` stage.
        * **Tag Filtering & Scoring**: The initial semantic search results are then filtered based on `must_tags` and `must_not_tags`. A `like_score` is calculated based on the presence of `like_tags`.
        * **Re-ranking**: Results are sorted first by `like_score` (descending) and then by semantic `similarity` (descending). The final `RERANK_TOP_K` results are returned.
    * **Recommended Tags (EIG)**: Based on the current search results, NaviSearch calculates the Expected Information Gain (EIG) for tags present in those results. Tags with higher EIG are those that can best help differentiate or narrow down the current result set, aiding the user in refining their search.

4.  **User Roles**:
    * **User**: Can upload documents, trigger ingestion, and perform searches.
    * **Admin**: Has all user permissions plus the ability to modify the global tag dictionary.
    * Authentication is handled via simple bearer tokens defined in environment variables.

## Advantages of NaviSearch

* **Efficient Evidence Discovery**: Quickly pinpoints relevant documents even in large, unsorted collections.
* **Bridging the Knowledge Gap**: The system assists in organizing data by automatically suggesting relevant tags based on content, using a shared vocabulary (the tag dictionary). Users provide raw data; the system helps structure it for the analyst.
* **Collaborative Tagging**: While initial tags are AI-generated, the search interface allows users to interactively use tags, implicitly validating or suggesting the importance of certain tags. The EIG feature further guides users.
* **Improved Accuracy & Consistency**: Reduces reliance on manual keyword searching and individual interpretation by leveraging semantic understanding and a standardized tag set.
* **User-Friendly Interface**: Provides a simple web UI for upload, ingestion, and search, making it accessible to team members without deep technical expertise in vector databases or LLMs.
* **Lightweight & Deployable**: Designed as a FastAPI backend and React frontend, it can be deployed relatively easily for small team usage.
* **Customizable**: Tag dictionaries and AI models can be configured to suit specific domains and requirements.

## Positioning

NaviSearch is positioned as a **team-based productivity tool** for the initial stages of information retrieval and evidence organization, particularly when dealing with textual data where semantic meaning and key themes (tags) are crucial. It is not a full-fledged document management system but rather a focused search and navigation aid.

It excels in scenarios where:
* A team needs to collaboratively make sense of a shared document pool.
* The documents are primarily text-based.
* A predefined set of concepts or categories (tags) is important for filtering and organization.
* Rapidly finding "needles in a haystack" based on both meaning and specific attributes is essential.

For your network security assessment use case, NaviSearch helps turn a pile of user-submitted "proofs" into a searchable, tagged collection, allowing your team to quickly find materials relevant to specific checklist items or security controls.

## Setup and Configuration

### Prerequisites
* Python 3.8+
* Node.js and npm/yarn (for frontend)
* Access to an OpenAI-compatible API (like DashScope) for embeddings and LLM calls.
* A running Milvus instance.

### Backend Setup
1.  Clone the repository.
2.  Create a virtual environment: `python -m venv venv` and activate it.
3.  Install Python dependencies: `pip install -r requirements.txt`.
4.  Create a `.env` file in the backend root directory based on `.env.example` (if provided) or the `Config` class in `main.py`. Populate it with your API keys, Milvus details, etc.
    ```dotenv
    OPENAI_BASE_URL="[https://dashscope.aliyuncs.com/compatible-mode/v1](https://dashscope.aliyuncs.com/compatible-mode/v1)"
    OPENAI_API_KEY="your_dashscope_api_key" # Or your OpenAI key
    OPENAI_EMBEDDING_MODEL="text-embedding-v3" # Ensure your provider supports this
    OPENAI_LLM_MODEL="deepseek-v3" # Or any compatible chat model like qwen-turbo, gpt-3.5-turbo

    MILVUS_COLLECTION_NAME="navisearch_docs_sec_assessment"
    MILVUS_HOST="localhost" # Or your Milvus instance IP/hostname
    MILVUS_PORT="19530"
    MILVUS_TOKEN="" # Optional: your Milvus token if authentication is enabled

    TAG_DIRECTORY="data/tag_directory.json"
    RETRIEVAL_TOP_K="20" # Increased for broader initial fetch
    RERANK_TOP_K="10"   # Show more results
    TAGS_TOP_K="15"
    MAX_FILE_SIZE="10485760" # 10MB

    # These tokens are for API authentication. Keep them secret.
    ADMIN_TOKEN="your_strong_admin_secret_token"
    USER_TOKEN="your_strong_user_secret_token"

    # UPLOAD_DIR and DOCUMENTS_FILE are relative to where main.py is run
    # UPLOAD_DIR="data/upload"
    # DOCUMENTS_FILE="data/documents.jsonl"
    ```
5.  Ensure the `data/upload` directory exists (or will be created by the application if `os.makedirs` is used appropriately before write).
6.  Create your initial `data/tag_directory.json` (see example above).
7.  Run the FastAPI backend: `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`

### Frontend Setup
1.  Navigate to your frontend project directory.
2.  Install Node.js dependencies: `npm install` or `yarn install`.
3.  (If not already done) Install `lucide-react`: `npm install lucide-react` or `yarn add lucide-react`.
4.  You might need to set up environment variables for the frontend if you want to configure the API base URL dynamically (e.g., using Vite, create a `.env` file in the frontend root with `VITE_API_BASE_URL=http://localhost:8000/api`).
5.  Start the React development server: `npm run dev` or `yarn dev`.
6.  Open your browser to the address provided by the React development server (usually `http://localhost:5173` or `http://localhost:3000`).

### Authentication Switch / Local Deployment
The current backend `main.py` uses simple token-based authentication via `HTTPBearer`.
* **Admin Token**: `ADMIN_TOKEN` from `.env`. Grants access to all endpoints, including tag dictionary modification.
* **User Token**: `USER_TOKEN` from `.env`. Grants access to upload, ingest, and search.

For local deployment and debugging:
1.  Set `ADMIN_TOKEN` and `USER_TOKEN` in your `.env` file to known values.
2.  In the NaviSearch frontend, there's an input field where you (or your team members) can paste the appropriate token to authenticate API requests.
This mechanism, while basic, serves the purpose of user/admin separation for a small team without requiring complex OAuth setups. **There isn't a global "off switch" for authentication in the provided backend code**, as endpoints are protected by the `Depends(verify_token)` FastAPI dependency. To use the API, a valid token must be provided in the `Authorization: Bearer <token>` header.

## Future Considerations (Optional)
* **VLM for Multimodal Data**: Integrate the `OPENAI_VLM_MODEL` for processing image-based evidence.
* **Advanced User Management**: Implement a proper database-backed user authentication system (e.g., with JWTs and password hashing).
* **Document Preprocessing**: More sophisticated chunking and text extraction for diverse file types (PDF, DOCX - currently only UTF-8 text).
* **UI/UX Enhancements**: More detailed loading/error states, pagination for results, interactive tag management visualizations.
* **Feedback Loop for Tags**: Allow users to correct or add tags to documents, potentially retraining or fine-tuning the tag generation model.
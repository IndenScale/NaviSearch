// src/NaviSearch.jsx
import './index.css';
import React, { useState, useEffect, useCallback } from 'react';
import { Search, FileText, Tag, UploadCloud, Settings, AlertTriangle, CheckCircle, Loader2, X, ChevronRight, Edit3, Info, Database, ListChecks, FileUp } from 'lucide-react'; // Added more icons

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

function NaviSearch() {
  const [searchInput, setSearchInput] = useState('');
  const [parsedQuery, setParsedQuery] = useState({
    query: '',
    likeTags: [],
    mustTags: [],
    mustNotTags: []
  });
  const [searchResults, setSearchResults] = useState([]);
  const [recommendedTags, setRecommendedTags] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Authentication
  const [authToken, setAuthToken] = useState('admin_secret_token'); // Consider storing this more securely or leaving it empty by default
  const [isAdminView, setIsAdminView] = useState(false);

  // File Upload
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  // Ingestion
  const [isIngesting, setIsIngesting] = useState(false);

  // Tag Dictionary Management (Admin)
  const [tagDictionary, setTagDictionary] = useState([]);
  const [isEditingTags, setIsEditingTags] = useState(false); // This state seems unused, consider removing or implementing its use-case
  const [editableTags, setEditableTags] = useState('');
  const [isLoadingTags, setIsLoadingTags] = useState(false);

  // New states for original document viewing
  const [viewingDocument, setViewingDocument] = useState(null); // Stores details of document being viewed
  const [currentlyFetchingFileId, setCurrentlyFetchingFileId] = useState(null); // Tracks specific file ID fetch

  // New states for system statistics (Admin)
  const [systemStats, setSystemStats] = useState(null);
  const [isLoadingStats, setIsLoadingStats] = useState(false);


  const displayMessage = (setter, message, duration = 3000) => {
    setter(message);
    setTimeout(() => setter(null), duration);
  };

  const makeApiRequest = useCallback(async (endpoint, method = 'GET', body = null, isFile = false) => {
    if (!authToken) {
      setError("认证令牌未设置。请输入一个令牌。");
      return null;
    }
    setIsLoading(true); // Global loading state
    setError(null);
    // setSuccessMessage(null); // Clear previous success messages when a new request starts

    const headers = new Headers();
    if (!isFile) {
      headers.append('Content-Type', 'application/json');
    }
    headers.append('Authorization', `Bearer ${authToken}`);

    const config = {
      method,
      headers,
      body: isFile ? body : body ? JSON.stringify(body) : null,
    };

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errData.detail || `HTTP 错误 ${response.status}`);
      }
      if (response.status === 204 || response.headers.get("content-length") === "0") {
        return null;
      }
      return await response.json();
    } catch (err) {
      console.error(`API 请求 ${endpoint} 失败:`, err);
      setError(err.message);
      return null;
    } finally {
      setIsLoading(false); // Global loading state
    }
  }, [authToken]);


  const parseSearchInput = useCallback((input) => {
    const cleanedInput = input.trim();
    if (!cleanedInput) {
        return { query: '', likeTags: [], mustTags: [], mustNotTags: [] };
    }
    const parts = cleanedInput.split(/\s+/);
    const queryTerms = [];
    const likeTags = [];
    const mustTags = [];
    const mustNotTags = [];
    let parsingQuery = true;

    for (const part of parts) {
        if (!part) continue; 

        if (part.startsWith('+') && part.length > 1) {
            parsingQuery = false;
            mustTags.push(part.substring(1));
        } else if (part.startsWith('-') && part.length > 1) {
            parsingQuery = false;
            mustNotTags.push(part.substring(1));
        } else if (part.startsWith('~') && part.length > 1) {
            parsingQuery = false;
            likeTags.push(part.substring(1));
        } else if (parsingQuery && !part.match(/^([+\-~])/)) { // ensure it's not a malformed tag like just "+"
            queryTerms.push(part);
        } else { // No prefix, and we are past the query OR it's an unprefixed term from the start but other conditions made parsingQuery false
             if (part.match(/^([+\-~])$/)) { // if it's just a prefix char, ignore or treat as part of a name if intended
                if(parsingQuery) queryTerms.push(part); else likeTags.push(part); // or decide to ignore
             } else {
                parsingQuery = false; // any unhandled part that's not a query term means query parsing is over
                likeTags.push(part);
             }
        }
    }
    return { query: queryTerms.join(' '), likeTags, mustTags, mustNotTags };
  }, []);


  // Perform search
  const performSearch = useCallback(async (parsed) => {
    if (!parsed.query && parsed.likeTags.length === 0 && parsed.mustTags.length === 0 && parsed.mustNotTags.length === 0) {
      setSearchResults([]);
      setRecommendedTags([]);
      return;
    }
    const payload = {
      query: parsed.query,
      like_tags: parsed.likeTags,
      must_tags: parsed.mustTags,
      must_not_tags: parsed.mustNotTags,
    };
    const data = await makeApiRequest('/search', 'POST', payload);
    if (data) {
      setSearchResults(data.results || []);
      setRecommendedTags(data.recommended_tags || []);
    } else {
      setSearchResults([]);
      setRecommendedTags([]);
    }
  }, [makeApiRequest]);

  useEffect(() => {
    const parsed = parseSearchInput(searchInput);
    setParsedQuery(parsed);
    const debounceSearch = setTimeout(() => {
      performSearch(parsed);
    }, 500);
    return () => clearTimeout(debounceSearch);
  }, [searchInput, parseSearchInput, performSearch]);


  // File Upload Handling
  const handleFileChange = (event) => {
    setSelectedFile(event.target.files[0]);
  };

  const handleFileUpload = async () => {
    if (!selectedFile) {
      displayMessage(setError, "请选择一个文件上传。");
      return;
    }
    setIsUploading(true); // Specific loading state for upload button
    const formData = new FormData();
    formData.append('file', selectedFile);

    const data = await makeApiRequest('/upload', 'POST', formData, true);
    setIsUploading(false);
    if (data) {
      displayMessage(setSuccessMessage, `文件 "${data.filename}" 上传成功。您现在可以对它进行提取。`);
      setSelectedFile(null);
      if (document.getElementById('fileUpload')) {
        document.getElementById('fileUpload').value = null; // Clear file input
      }
    }
  };

  // Document Ingestion Handling
  const handleIngestDocuments = async () => {
    setIsIngesting(true); // Specific loading state for ingest button
    const data = await makeApiRequest('/ingest', 'POST');
    setIsIngesting(false);
    if (data) {
      displayMessage(setSuccessMessage, data.message || "提取过程已启动。");
      performSearch(parsedQuery); // Refresh search results
      if (isAdminView && systemStats) fetchSystemStats(); 
    }
  };

  // Tag Dictionary Management (Admin)
  const fetchTagDictionary = useCallback(async () => {
    if (!authToken) return;
    setIsLoadingTags(true);
    const data = await makeApiRequest('/tags', 'GET');
    setIsLoadingTags(false);
    if (data && data.tags) {
      setTagDictionary(data.tags);
      setEditableTags(data.tags.join('\n'));
    }
  }, [makeApiRequest, authToken]);

  useEffect(() => {
    if (isAdminView) {
      fetchTagDictionary();
      // fetchSystemStats(); // Optionally fetch stats when admin view is enabled, or let admin click a button
    } else {
        setSystemStats(null); 
    }
  }, [isAdminView, fetchTagDictionary]); // Removed fetchSystemStats from here to avoid auto-call

  const handleUpdateTagDictionary = async () => {
    const tagsArray = editableTags.split('\n').map(tag => tag.trim()).filter(tag => tag);
    setIsLoadingTags(true);
    const data = await makeApiRequest('/tags', 'PUT', { tags: tagsArray });
    setIsLoadingTags(false);
    if (data) {
      displayMessage(setSuccessMessage, data.message || "标签字典更新成功。");
      setTagDictionary(tagsArray);
      // setIsEditingTags(false); // This state seems unused
      fetchTagDictionary(); // Re-fetch to confirm and get normalized tags if any
    }
  };

  // New: Fetch Original Document Details
  const handleViewOriginalDocument = async (originalFileField) => {
    if (!originalFileField) {
        displayMessage(setError, "原始文件字段为空，无法查看。");
        return;
    }
    const fileIdParts = originalFileField.match(/^([0-9a-fA-F]{32})_(.*)$/);
    if (!fileIdParts || fileIdParts.length < 3) {
      displayMessage(setError, `搜索结果中的 original_file 字段格式无效: ${originalFileField}。无法提取文件 ID。`);
      setCurrentlyFetchingFileId(null);
      return;
    }
    const fileId = fileIdParts[1];

    setCurrentlyFetchingFileId(fileId);
    setViewingDocument(null); 

    const data = await makeApiRequest(`/document/${fileId}`, 'GET');

    setCurrentlyFetchingFileId(null);
    if (data) {
      setViewingDocument(data);
    }
  };
  
  // New: Fetch System Statistics (Admin)
  const fetchSystemStats = useCallback(async () => {
    if (!authToken || !isAdminView) return;
    setIsLoadingStats(true);
    const data = await makeApiRequest('/stats', 'GET');
    setIsLoadingStats(false);
    if (data) {
      setSystemStats(data);
    }
  }, [makeApiRequest, authToken, isAdminView]);


  const getTagState = (tag) => {
    const lowerTag = tag.toLowerCase();
    const { likeTags, mustTags, mustNotTags } = parsedQuery;
    if (mustTags.some(t => t.toLowerCase() === lowerTag)) return 'must';
    if (mustNotTags.some(t => t.toLowerCase() === lowerTag)) return 'mustNot';
    if (likeTags.some(t => t.toLowerCase() === lowerTag)) return 'like';
    return 'none';
  };

  const updateSearchInputWithTags = (query, likeTags, mustTags, mustNotTags) => {
    const queryPart = query ? query + " " : "";
    const likePart = likeTags.map(t => `~${t}`).join(" ");
    const mustPart = mustTags.map(t => `+${t}`).join(" ");
    const mustNotPart = mustNotTags.map(t => `-${t}`).join(" ");
    setSearchInput(`${queryPart}${likePart} ${mustPart} ${mustNotPart}`.replace(/\s+/g, ' ').trim());
  };

  const toggleTagInSearch = (tagToToggle) => {
    let { query, likeTags, mustTags, mustNotTags } = parseSearchInput(searchInput); // get current parsed state
    const lowerTagToToggle = tagToToggle.toLowerCase();

    // Remove all instances of the tag (case-insensitive)
    likeTags = likeTags.filter(t => t.toLowerCase() !== lowerTagToToggle);
    mustTags = mustTags.filter(t => t.toLowerCase() !== lowerTagToToggle);
    mustNotTags = mustNotTags.filter(t => t.toLowerCase() !== lowerTagToToggle);

    const currentState = getTagState(tagToToggle); // Get state based on current searchInput (before modification for this specific tag)

    if (currentState === 'none') { // none -> like
      likeTags.push(tagToToggle); // Add with original casing
    } else if (currentState === 'like') { // like -> must
      mustTags.push(tagToToggle);
    } else if (currentState === 'must') { // must -> mustNot
      mustNotTags.push(tagToToggle);
    }
    // If current state is 'mustNot', it's removed, effectively cycling to 'none' for the next click

    updateSearchInputWithTags(query, likeTags, mustTags, mustNotTags);
  };

  const addTagFromRecommendation = (tag, type) => {
    let { query, likeTags, mustTags, mustNotTags } = parseSearchInput(searchInput);
    const lowerTag = tag.toLowerCase();

    likeTags = likeTags.filter(t => t.toLowerCase() !== lowerTag);
    mustTags = mustTags.filter(t => t.toLowerCase() !== lowerTag);
    mustNotTags = mustNotTags.filter(t => t.toLowerCase() !== lowerTag);

    if (type === 'like') likeTags.push(tag);
    else if (type === 'must') mustTags.push(tag);
    else if (type === 'mustNot') mustNotTags.push(tag);

    updateSearchInputWithTags(query, likeTags, mustTags, mustNotTags);
  };

  const removeTagFromPill = (tagToRemove, type) => {
    let { query, likeTags, mustTags, mustNotTags } = parseSearchInput(searchInput);
    const lowerTagToRemove = tagToRemove.toLowerCase();

    if (type === 'like') likeTags = likeTags.filter(t => t.toLowerCase() !== lowerTagToRemove);
    else if (type === 'must') mustTags = mustTags.filter(t => t.toLowerCase() !== lowerTagToRemove);
    else if (type === 'mustNot') mustNotTags = mustNotTags.filter(t => t.toLowerCase() !== lowerTagToRemove);

    updateSearchInputWithTags(query, likeTags, mustTags, mustNotTags);
  };


  return (
    <div className="max-w-7xl mx-auto p-4 md:p-6 bg-gray-50 min-h-screen">
      {/* Auth Token Input & Global Messages */}
      <div className="mb-4 p-4 bg-sky-100 rounded-lg shadow">
        <label htmlFor="authToken" className="block text-sm font-medium text-sky-700 mb-1">认证令牌 (Auth Token):</label>
        <input
          type="password"
          id="authToken"
          value={authToken}
          onChange={(e) => setAuthToken(e.target.value)}
          placeholder="输入您的API令牌"
          className="w-full px-3 py-2 border border-sky-300 rounded-md shadow-sm focus:ring-sky-500 focus:border-sky-500"
        />
        <div className="mt-2 flex justify-between items-center">
            <label className="inline-flex items-center">
                <input type="checkbox" className="form-checkbox h-5 w-5 text-sky-600" checked={isAdminView} onChange={() => setIsAdminView(!isAdminView)} />
                <span className="ml-2 text-sky-700">启用管理员功能</span>
            </label>
            {isLoading && <div className="flex items-center text-sky-600"><Loader2 className="animate-spin h-5 w-5 mr-2" />处理中...</div>}
        </div>
        {error && <div className="mt-2 p-3 bg-red-100 text-red-700 rounded-md flex items-center"><AlertTriangle className="h-5 w-5 mr-2" />错误: {error}</div>}
        {successMessage && <div className="mt-2 p-3 bg-green-100 text-green-700 rounded-md flex items-center"><CheckCircle className="h-5 w-5 mr-2" />{successMessage}</div>}
      </div>


      <div className="bg-white rounded-lg shadow-xl p-4 md:p-6">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-800 mb-1">NaviSearch</h1>
          <p className="text-gray-600">标签增强搜索引擎 - 精确导航至目标文档</p>
        </div>

        {/* File Upload and Ingestion Section */}
        <div className="mb-6 p-4 border border-gray-200 rounded-lg bg-gray-50">
          <h2 className="text-lg font-semibold text-gray-700 mb-3 flex items-center"><FileUp className="h-5 w-5 mr-2 text-blue-500"/>文档管理</h2>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="fileUpload" className="block text-sm font-medium text-gray-700 mb-1">上传文档</label>
              <div className="flex items-center">
                <input
                  type="file"
                  id="fileUpload"
                  onChange={handleFileChange}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
                <button
                  onClick={handleFileUpload}
                  disabled={!selectedFile || isUploading || !authToken || isLoading}
                  className="ml-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 flex items-center whitespace-nowrap"
                >
                  {isUploading ? <Loader2 className="animate-spin h-5 w-5 mr-2" /> : <UploadCloud className="h-5 w-5 mr-2" />} 上传
                </button>
              </div>
              {selectedFile && <p className="text-xs text-gray-500 mt-1">已选择: {selectedFile.name}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">提取已上传文档</label>
              <button
                onClick={handleIngestDocuments}
                disabled={isIngesting || !authToken || isLoading}
                className="w-full px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:bg-gray-300 flex items-center justify-center"
              >
                {isIngesting ? <Loader2 className="animate-spin h-5 w-5 mr-2" /> : <ChevronRight className="h-5 w-5 mr-2" />} 开始提取
              </button>
              <p className="text-xs text-gray-500 mt-1">处理 `data/upload/` 中的文件到搜索索引。</p>
            </div>
          </div>
        </div>


        {/* Search Input Section */}
        <div className="mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="查询词和标签 (例: React +前端 -后端 ~JS)"
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={!authToken}
            />
          </div>
          {/* Parsed Query Display */}
          <div className="mt-3 space-y-1">
            {parsedQuery.query && (
              <div className="flex items-center gap-1 text-xs">
                <span className="font-medium text-gray-600">查询:</span>
                <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">
                  {parsedQuery.query}
                </span>
              </div>
            )}
            {parsedQuery.likeTags.length > 0 && (
              <div className="flex items-center gap-1 flex-wrap text-xs">
                <span className="font-medium text-gray-600">倾向:</span>
                {parsedQuery.likeTags.map((tag, index) => (
                  <span key={`like-${index}-${tag}`} className="flex items-center gap-0.5 px-1.5 py-0.5 bg-green-100 text-green-700 rounded">
                    ~{tag}
                    <X className="h-3 w-3 cursor-pointer hover:text-green-900" onClick={() => removeTagFromPill(tag, 'like')} />
                  </span>
                ))}
              </div>
            )}
            {parsedQuery.mustTags.length > 0 && (
              <div className="flex items-center gap-1 flex-wrap text-xs">
                <span className="font-medium text-gray-600">必须:</span>
                {parsedQuery.mustTags.map((tag, index) => (
                  <span key={`must-${index}-${tag}`} className="flex items-center gap-0.5 px-1.5 py-0.5 bg-red-100 text-red-700 rounded">
                    +{tag}
                    <X className="h-3 w-3 cursor-pointer hover:text-red-900" onClick={() => removeTagFromPill(tag, 'must')} />
                  </span>
                ))}
              </div>
            )}
            {parsedQuery.mustNotTags.length > 0 && (
              <div className="flex items-center gap-1 flex-wrap text-xs">
                <span className="font-medium text-gray-600">排除:</span>
                {parsedQuery.mustNotTags.map((tag, index) => (
                  <span key={`not-${index}-${tag}`} className="flex items-center gap-0.5 px-1.5 py-0.5 bg-gray-200 text-gray-700 rounded">
                    -{tag}
                    <X className="h-3 w-3 cursor-pointer hover:text-gray-900" onClick={() => removeTagFromPill(tag, 'mustNot')} />
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Search Results */}
          <div className="lg:col-span-2">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-gray-700">
              <FileText className="h-5 w-5" />
              搜索结果 ({searchResults.length})
            </h2>
            <div className="space-y-4">
              {isLoading && searchResults.length === 0 && <div className="text-center py-8 text-gray-500"><Loader2 className="animate-spin h-10 w-10 mx-auto"/></div>}
              {!isLoading && searchResults.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  <FileText className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>没有找到匹配的文档。请尝试不同查询或检查标签。</p>
                </div>
              )}
              {searchResults.map((doc) => {
                const fileIdMatch = doc.original_file?.match(/^([0-9a-fA-F]{32})_(.*)$/);
                const currentFileIdForButton = fileIdMatch ? fileIdMatch[1] : null;
                return (
                  <div key={doc.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                    <div className="flex justify-between items-start mb-2">
                      <h3 className="font-semibold text-gray-800 break-all">{doc.source}</h3> {/* User-friendly filename */}
                      <div className="flex-shrink-0 ml-2 text-xs text-gray-500 text-right">
                        <div>相似度: {(doc.similarity * 100).toFixed(0)}%</div>
                        {doc.like_score > 0 && <div>倾向分: {doc.like_score}</div>}
                      </div>
                    </div>
                    <p className="text-gray-700 mb-3 text-sm leading-relaxed whitespace-pre-wrap">
                      {doc.content.substring(0, 300)}{doc.content.length > 300 && '...'}
                    </p>
                    
                    {/* Original File and Chunk Info */}
                    <div className="mb-3 text-xs text-gray-600 bg-gray-50 p-2 rounded">
                      {doc.original_file && <p><strong>存储为:</strong> <span className="break-all">{doc.original_file}</span></p>}
                      {doc.chunk_info && (
                        <>
                          <p>
                            <strong>区块:</strong> {doc.chunk_info.chunk_index + 1} / {doc.chunk_info.total_chunks}
                          </p>
                          {doc.chunk_info.metadata && Object.keys(doc.chunk_info.metadata).length > 0 && (
                             <details className="mt-1 text-xs">
                               <summary className="cursor-pointer hover:underline">查看元数据</summary>
                               <pre className="bg-gray-100 p-1 rounded text-xs whitespace-pre-wrap break-all mt-1">
                                 {JSON.stringify(doc.chunk_info.metadata, null, 2)}
                               </pre>
                             </details>
                          )}
                        </>
                      )}
                      {doc.original_file && currentFileIdForButton && (
                        <button
                          onClick={() => handleViewOriginalDocument(doc.original_file)}
                          disabled={isLoading && currentlyFetchingFileId === currentFileIdForButton} // Disable only if this specific doc is loading
                          className="mt-1 text-blue-600 hover:text-blue-800 hover:underline disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                        >
                          {(isLoading && currentlyFetchingFileId === currentFileIdForButton) ? (
                              <Loader2 className="animate-spin h-3 w-3 mr-1 inline-block"/>
                          ) : <Info className="h-3 w-3 mr-1 inline-block"/> }
                          查看原始文件信息
                        </button>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-1">
                      {doc.tags.map((tag, index) => {
                        const tagState = getTagState(tag);
                        const getTagStyle = () => {
                          switch(tagState) {
                            case 'like': return 'bg-green-100 text-green-800 border-green-300 hover:bg-green-200';
                            case 'must': return 'bg-red-100 text-red-800 border-red-300 hover:bg-red-200';
                            case 'mustNot': return 'bg-gray-200 text-gray-700 border-gray-400 hover:bg-gray-300 line-through';
                            default: return 'bg-gray-100 hover:bg-gray-200 text-gray-700 border-gray-300';
                          }
                        };
                        return (
                          <button
                            key={`${tag}-${index}`}
                            onClick={() => toggleTagInSearch(tag)}
                            className={`px-2 py-1 rounded text-xs transition-colors border ${getTagStyle()}`}
                            title={`点击循环: 无 -> 倾向 (~) -> 必须 (+) -> 排除 (-) -> 无. 当前: ${tagState}`}
                          >
                            {tagState === 'like' && <span className="mr-0.5">~</span>}
                            {tagState === 'must' && <span className="mr-0.5">+</span>}
                            {tagState === 'mustNot' && <span className="mr-0.5">-</span>}
                            {tag}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Recommended Tags */}
          <div>
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-gray-700">
              <Tag className="h-5 w-5" />
              推荐标签
            </h2>
            <div className="space-y-2">
              {isLoading && recommendedTags.length === 0 && <div className="text-sm text-gray-500">加载推荐中...</div>}
              {!isLoading && recommendedTags.length === 0 && (
                <div className="text-center py-4 text-gray-500 text-sm">
                  <Tag className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>无推荐标签。</p>
                </div>
              )}
              {recommendedTags.map(({ tag, frequency, eig }) => (
                <div key={tag} className="border border-gray-200 rounded-lg p-3 bg-white">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-medium text-gray-800">{tag}</span>
                    <span className="text-xs text-gray-500">EIG: {eig.toFixed(1)}</span>
                  </div>
                  <div className="text-xs text-gray-500 mb-2">Freq: {frequency}</div>
                  <div className="flex gap-1">
                    <button onClick={() => addTagFromRecommendation(tag, 'like')} className="flex-1 px-1.5 py-0.5 bg-green-100 hover:bg-green-200 text-green-700 rounded text-xs">~倾向</button>
                    <button onClick={() => addTagFromRecommendation(tag, 'must')} className="flex-1 px-1.5 py-0.5 bg-red-100 hover:bg-red-200 text-red-700 rounded text-xs">+必须</button>
                    <button onClick={() => addTagFromRecommendation(tag, 'mustNot')} className="flex-1 px-1.5 py-0.5 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded text-xs">-排除</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Admin Section */}
        {isAdminView && (
          <div className="mt-8 p-4 border border-amber-300 rounded-lg bg-amber-50">
            <h2 className="text-lg font-semibold text-amber-800 mb-3 flex items-center">
              <Settings className="h-5 w-5 mr-2"/> 管理员功能
            </h2>
            
            {/* Tag Dictionary Management */}
            <div className="mb-6">
                <h3 className="text-md font-semibold text-amber-800 mb-2 flex items-center"><Edit3 className="h-4 w-4 mr-1"/> 管理标签字典</h3>
                {isLoadingTags && <div className="text-amber-700"><Loader2 className="animate-spin h-5 w-5 mr-2 inline"/>加载标签中...</div>}
                {!isLoadingTags && (
                <>
                    <div className="mb-2">
                    <label htmlFor="tagDictionaryEdit" className="block text-sm font-medium text-amber-700">编辑标签 (每行一个):</label>
                    <textarea
                        id="tagDictionaryEdit"
                        rows="10"
                        value={editableTags}
                        onChange={(e) => setEditableTags(e.target.value)}
                        className="mt-1 block w-full px-3 py-2 bg-white border border-amber-300 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm"
                        placeholder="输入标签，每行一个..."
                        disabled={!authToken || isLoading} // Also consider global isLoading
                    />
                    </div>
                    <button
                    onClick={handleUpdateTagDictionary}
                    disabled={isLoadingTags || !authToken || isLoading}
                    className="px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:bg-gray-300 flex items-center"
                    >
                    <Edit3 className="h-5 w-5 mr-2"/> 更新标签字典
                    </button>
                </>
                )}
            </div>

            {/* System Statistics */}
            <div className="mt-6">
              <h3 className="text-md font-semibold text-amber-800 mb-2 flex items-center"><Database className="h-4 w-4 mr-1"/> 系统统计</h3>
              <button
                onClick={fetchSystemStats}
                disabled={isLoadingStats || !authToken || isLoading }
                className="px-3 py-1.5 bg-amber-400 text-amber-900 rounded-md hover:bg-amber-500 disabled:bg-gray-300 text-sm mb-2 flex items-center"
              >
                {isLoadingStats ? <Loader2 className="animate-spin h-4 w-4 mr-1 inline"/> : <ListChecks className="h-4 w-4 mr-1 inline"/>} 刷新统计
              </button>
              {systemStats && !isLoadingStats && (
                <div className="text-sm text-amber-700 space-y-1 p-3 bg-amber-100 rounded">
                  <p><strong>总索引区块:</strong> {systemStats.total_chunks}</p>
                  <p><strong>待提取文件 (upload/):</strong> {systemStats.files_pending}</p>
                  <p><strong>已提取文件 (ingested/):</strong> {systemStats.files_ingested}</p>
                  <p><strong>支持格式:</strong> {systemStats.supported_formats.join(', ')}</p>
                </div>
              )}
               {isLoadingStats && <div className="text-amber-700 mt-2"><Loader2 className="animate-spin h-4 w-4 mr-1 inline"/>加载统计中...</div>}
            </div>
          </div>
        )}

        {/* Usage Instructions */}
        <div className="mt-8 p-4 bg-blue-50 rounded-lg">
          <h3 className="font-semibold text-blue-800 mb-2">使用说明:</h3>
          <ul className="text-sm text-blue-700 space-y-1 list-disc list-inside">
            <li>请先在顶部输入有效的API令牌以启用功能。</li>
            <li><strong>文档管理</strong>: 上传支持的文件 (如 .txt, .pdf, .docx等), 然后点击 "开始提取" 处理它们。</li>
            <li><strong>搜索</strong>: 输入查询词。使用前缀添加标签: <code>+</code> (必须), <code>-</code> (排除), <code>~</code> (倾向)。无前缀标签默认为倾向。例: <code>myquery +importantTag ~optionalTag -excludedTag</code></li>
            <li><strong>文档标签点击</strong>: 点击搜索结果中的标签可循环切换其在当前搜索中的状态: 未选 → 倾向(~) → 必须(+) → 排除(-) → 从查询中移除。</li>
            <li><strong>推荐标签</strong>: 点击倾向/必须/排除按钮可将其添加到当前搜索查询中。</li>
            <li>管理员可通过 "启用管理员功能" 复选框访问标签字典管理和系统统计功能。</li>
            <li>搜索结果会显示原始文件名、存储文件名、区块信息及元数据（如果存在）。可点击“查看原始文件信息”获取更多文件详情。</li>
          </ul>
        </div>
      </div>

      {/* Modal for Viewing Original Document Details */}
      {viewingDocument && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-75 overflow-y-auto h-full w-full z-50 flex justify-center items-center p-4">
          <div className="relative p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4 text-center">原始文档信息</h3>
              <div className="px-4 py-3 text-left space-y-2 text-sm text-gray-700">
                <p><strong>文件 ID:</strong> <span className="break-all">{viewingDocument.file_id}</span></p>
                <p><strong>文件名 (存储):</strong> <span className="break-all">{viewingDocument.filename}</span></p>
                <p><strong>大小:</strong> {(viewingDocument.size / 1024).toFixed(2)} KB</p>
                <p><strong>最后修改时间:</strong> {new Date(viewingDocument.modified).toLocaleString()}</p>
              </div>
              <div className="items-center px-4 py-3 mt-2">
                <button
                  id="ok-btn"
                  onClick={() => setViewingDocument(null)}
                  className="w-full px-4 py-2 bg-blue-500 text-white text-base font-medium rounded-md shadow-sm hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default NaviSearch;
import React, { useState, useEffect, useMemo } from 'react';
import { Search, FileText, Tag, Filter, X, Plus } from 'lucide-react';

// 模拟文档数据
const mockDocuments = [
  {
    id: 1,
    content: "React是一个用于构建用户界面的JavaScript库。它采用组件化架构，支持虚拟DOM技术，提供了声明式编程范式。React由Facebook开发，广泛应用于现代Web开发中。",
    source: "react-guide.md",
    tags: ["前端", "JavaScript", "React", "组件化", "虚拟DOM", "声明式", "Facebook", "Web开发"]
  },
  {
    id: 2,
    content: "Vue.js是一个渐进式JavaScript框架，用于构建用户界面。Vue的核心库只关注视图层，易于上手，同时便于与第三方库或既有项目整合。",
    source: "vue-tutorial.md",
    tags: ["前端", "JavaScript", "Vue", "渐进式", "框架", "视图层", "易上手", "Web开发"]
  },
  {
    id: 3,
    content: "Python是一种高级编程语言，具有简洁的语法和强大的功能。Python广泛应用于数据科学、机器学习、Web开发等领域。其丰富的第三方库生态系统是其主要优势之一。",
    source: "python-intro.md",
    tags: ["后端", "Python", "高级语言", "数据科学", "机器学习", "Web开发", "第三方库", "生态系统"]
  },
  {
    id: 4,
    content: "机器学习是人工智能的一个重要分支，通过算法让计算机从数据中学习模式。常见的机器学习算法包括线性回归、决策树、神经网络等。",
    source: "ml-basics.md",
    tags: ["机器学习", "人工智能", "算法", "数据", "线性回归", "决策树", "神经网络", "模式识别"]
  },
  {
    id: 5,
    content: "Docker是一个开源的容器化平台，允许开发者将应用程序和其依赖项打包到轻量级、可移植的容器中。Docker简化了应用部署和环境管理。",
    source: "docker-guide.md",
    tags: ["DevOps", "Docker", "容器化", "开源", "部署", "环境管理", "轻量级", "可移植"]
  },
  {
    id: 6,
    content: "Node.js是一个基于Chrome V8引擎的JavaScript运行时环境。它使JavaScript能够在服务器端运行，具有事件驱动、非阻塞I/O等特性。",
    source: "nodejs-overview.md",
    tags: ["后端", "Node.js", "JavaScript", "V8引擎", "服务器", "事件驱动", "非阻塞", "运行时"]
  },
  {
    id: 7,
    content: "微服务架构是一种将单一应用程序开发为一套小服务的方法。每个服务运行在自己的进程中，并使用轻量级机制通信。",
    source: "microservices.md",
    tags: ["架构", "微服务", "分布式", "服务化", "进程", "轻量级", "通信", "解耦"]
  },
  {
    id: 8,
    content: "GraphQL是一种用于API的查询语言和运行时。它提供了一种更高效、强大和灵活的数据获取方式，允许客户端精确指定需要的数据。",
    source: "graphql-intro.md",
    tags: ["API", "GraphQL", "查询语言", "运行时", "数据获取", "灵活", "客户端", "精确查询"]
  }
];

// 预定义标签字典
const tagDictionary = [
  "前端", "后端", "JavaScript", "Python", "React", "Vue", "Node.js",
  "机器学习", "人工智能", "数据科学", "Web开发", "移动开发",
  "架构", "微服务", "容器化", "Docker", "DevOps",
  "算法", "数据结构", "数据库", "API", "GraphQL",
  "框架", "库", "工具", "平台", "生态系统"
];

function NaviSearch() {
  const [searchInput, setSearchInput] = useState('');
  const [parsedQuery, setParsedQuery] = useState({
    query: '',
    likeTags: [],
    mustTags: [],
    mustNotTags: []
  });
  const [searchResults, setSearchResults] = useState([]);
  const [availableTags, setAvailableTags] = useState([]);

  // 解析搜索输入
  const parseSearchInput = (input) => {
    const parts = input.trim().split(/\s+/);
    const query = parts[0] || '';
    const tags = parts.slice(1);

    const likeTags = [];
    const mustTags = [];
    const mustNotTags = [];

    tags.forEach(tag => {
      if (tag.startsWith('+')) {
        mustTags.push(tag.substring(1));
      } else if (tag.startsWith('-')) {
        mustNotTags.push(tag.substring(1));
      } else if (tag.startsWith('~')) {
        likeTags.push(tag.substring(1));
      } else {
        likeTags.push(tag);
      }
    });

    return { query, likeTags, mustTags, mustNotTags };
  };

  // 计算语义相似度（改进版本，模拟向量相似度）
  const calculateSimilarity = (query, content) => {
    if (!query) return 0.3; // 无查询时给个基础分

    const queryLower = query.toLowerCase();
    const contentLower = content.toLowerCase();

    // 1. 精确匹配得分
    let exactMatch = 0;
    if (contentLower.includes(queryLower)) {
      exactMatch = 0.8; // 精确匹配高分
    }

    // 2. 关键词匹配得分
    const queryWords = queryLower.split(/\s+/).filter(w => w.length > 0);
    const contentWords = contentLower.split(/\s+/);

    let keywordMatch = 0;
    if (queryWords.length > 0) {
      const matchedWords = queryWords.filter(qWord =>
        contentWords.some(cWord =>
          cWord.includes(qWord) || qWord.includes(cWord)
        )
      );
      keywordMatch = matchedWords.length / queryWords.length * 0.6;
    }

    // 3. 部分匹配得分（模拟语义相似度）
    let partialMatch = 0;
    const queryChars = queryLower.replace(/\s/g, '');
    let charMatches = 0;
    for (let char of queryChars) {
      if (contentLower.includes(char)) {
        charMatches++;
      }
    }
    if (queryChars.length > 0) {
      partialMatch = Math.sqrt(charMatches / queryChars.length) * 0.3;
    }

    // 4. 长度惩罚（越短的查询匹配度稍微降低）
    const lengthPenalty = Math.min(queryLower.length / 10, 1);

    // 综合得分
    const totalScore = Math.max(exactMatch, keywordMatch + partialMatch) * lengthPenalty;

    // 添加一些随机性模拟真实向量相似度的差异
    const randomFactor = 0.85 + Math.random() * 0.15;

    return Math.min(totalScore * randomFactor, 0.95); // 最高不超过95%
  };

  // 执行搜索
  const performSearch = (parsed) => {
    const { query, likeTags, mustTags, mustNotTags } = parsed;

    // 1. 语义相似度召回
    let candidates = mockDocuments.map(doc => ({
      ...doc,
      similarity: calculateSimilarity(query, doc.content)
    })).sort((a, b) => b.similarity - a.similarity);

    // 保留前K个（这里设为8个）
    candidates = candidates.slice(0, 8);

    // 2. 应用过滤标签
    candidates = candidates.filter(doc => {
      // Must tags检查
      const hasMustTags = mustTags.every(tag =>
        doc.tags.some(docTag => docTag.toLowerCase().includes(tag.toLowerCase()))
      );
      // Must not tags检查
      const hasNoMustNotTags = mustNotTags.every(tag =>
        !doc.tags.some(docTag => docTag.toLowerCase().includes(tag.toLowerCase()))
      );
      return hasMustTags && hasNoMustNotTags;
    });

    // 3. 根据like tags重排序
    candidates = candidates.map(doc => {
      let likeScore = 0;
      likeTags.forEach(tag => {
        if (doc.tags.some(docTag => docTag.toLowerCase().includes(tag.toLowerCase()))) {
          likeScore += 1;
        }
      });
      return { ...doc, likeScore };
    }).sort((a, b) => {
      if (b.likeScore !== a.likeScore) {
        return b.likeScore - a.likeScore;
      }
      return b.similarity - a.similarity;
    });

    // 保留前K个结果（这里设为5个）
    return candidates.slice(0, 5);
  };

  // 计算标签的期望信息增益（EIG）
  const calculateTagEIG = (results) => {
    const totalResults = results.length;
    if (totalResults === 0) return [];

    const tagFrequency = {};
    results.forEach(doc => {
      doc.tags.forEach(tag => {
        tagFrequency[tag] = (tagFrequency[tag] || 0) + 1;
      });
    });

    const tagsWithEIG = Object.entries(tagFrequency).map(([tag, freq]) => ({
      tag,
      frequency: freq,
      eig: Math.abs(freq - totalResults / 2)
    })).sort((a, b) => b.eig - a.eig);

    return tagsWithEIG.slice(0, 15); // 显示前15个标签
  };

  // 处理搜索输入变化
  useEffect(() => {
    const parsed = parseSearchInput(searchInput);
    setParsedQuery(parsed);

    const results = performSearch(parsed);
    setSearchResults(results);

    const tags = calculateTagEIG(results);
    setAvailableTags(tags);
  }, [searchInput]);

  // 获取标签当前状态
  const getTagState = (tag) => {
    const parts = searchInput.trim().split(/\s+/);
    const existingTags = parts.slice(1);

    for (let existingTag of existingTags) {
      const cleanTag = existingTag.replace(/^[+\-~]/, '');
      if (cleanTag === tag) {
        if (existingTag.startsWith('+')) return 'must';
        if (existingTag.startsWith('-')) return 'mustNot';
        if (existingTag.startsWith('~')) return 'like';
        return 'like'; // 默认无前缀为like
      }
    }
    return 'none'; // 不存在
  };

  // 循环切换标签状态: none -> like -> must -> mustNot -> (移除)
  const toggleTag = (tag) => {
    const currentState = getTagState(tag);

    // 首先移除该标签的所有形式
    const parts = searchInput.trim().split(/\s+/);
    const query = parts[0] || '';
    const filteredTags = parts.slice(1).filter(existingTag => {
      const cleanTag = existingTag.replace(/^[+\-~]/, '');
      return cleanTag !== tag;
    });

    let newInput = query;
    if (filteredTags.length > 0) {
      newInput += ' ' + filteredTags.join(' ');
    }

    // 然后根据状态转换添加新的标签形式
    if (currentState === 'none') {
      // 添加为like标签
      newInput += ' ~' + tag;
    } else if (currentState === 'like') {
      // 从like转为must
      newInput += ' +' + tag;
    } else if (currentState === 'must') {
      // 从must转为mustNot
      newInput += ' -' + tag;
    }
    // 如果是mustNot状态，则只移除，不添加新的

    setSearchInput(newInput.trim());
  };

  // 添加指定类型标签的辅助函数
  const addTagWithType = (tag, type = 'like') => {
    const prefix = type === 'must' ? '+' : type === 'mustNot' ? '-' : '~';
    const currentInput = searchInput.trim();
    const newTag = prefix + tag;
    const newInput = currentInput ? currentInput + ' ' + newTag : newTag;
    setSearchInput(newInput);
  };

  // 添加标签到搜索（保持原有功能用于右侧推荐标签）
  const addTag = (tag, type = 'like') => {
    const tagState = getTagState(tag);
    if (tagState === 'none') {
      addTagWithType(tag, type);
    }
  };

  // 移除标签
  const removeTag = (tagToRemove, type) => {
    const parts = searchInput.trim().split(/\s+/);
    const query = parts[0] || '';
    const prefix = type === 'must' ? '+' : type === 'mustNot' ? '-' : '~';

    const filteredTags = parts.slice(1).filter(tag =>
      tag !== prefix + tagToRemove && tag !== tagToRemove
    );

    const newInput = query + (filteredTags.length > 0 ? ' ' + filteredTags.join(' ') : '');
    setSearchInput(newInput.trim());
  };

  return (
    <div className="max-w-6xl mx-auto p-6 bg-gray-50 min-h-screen">
      <div className="bg-white rounded-lg shadow-lg p-6">
        {/* 标题 */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">NaviSearch</h1>
          <p className="text-gray-600">标签增强搜索引擎 - 精确导航至目标文档</p>
        </div>

        {/* 搜索框 */}
        <div className="mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="输入查询词和标签 (如: React +前端 -后端 ~JavaScript)"
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* 解析结果展示 */}
          <div className="mt-3 space-y-2">
            {parsedQuery.query && (
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-700">查询:</span>
                <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">
                  {parsedQuery.query}
                </span>
              </div>
            )}

            {parsedQuery.likeTags.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-gray-700">Like标签:</span>
                {parsedQuery.likeTags.map((tag, index) => (
                  <span key={index} className="flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 rounded text-sm">
                    ~{tag}
                    <X
                      className="h-3 w-3 cursor-pointer"
                      onClick={() => removeTag(tag, 'like')}
                    />
                  </span>
                ))}
              </div>
            )}

            {parsedQuery.mustTags.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-gray-700">Must标签:</span>
                {parsedQuery.mustTags.map((tag, index) => (
                  <span key={index} className="flex items-center gap-1 px-2 py-1 bg-red-100 text-red-800 rounded text-sm">
                    +{tag}
                    <X
                      className="h-3 w-3 cursor-pointer"
                      onClick={() => removeTag(tag, 'must')}
                    />
                  </span>
                ))}
              </div>
            )}

            {parsedQuery.mustNotTags.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-gray-700">Must Not标签:</span>
                {parsedQuery.mustNotTags.map((tag, index) => (
                  <span key={index} className="flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-800 rounded text-sm">
                    -{tag}
                    <X
                      className="h-3 w-3 cursor-pointer"
                      onClick={() => removeTag(tag, 'mustNot')}
                    />
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 搜索结果 */}
          <div className="lg:col-span-2">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <FileText className="h-5 w-5" />
              搜索结果 ({searchResults.length})
            </h2>

            <div className="space-y-4">
              {searchResults.map((doc) => (
                <div key={doc.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="font-medium text-gray-900">{doc.source}</h3>
                    <div className="flex gap-2 text-xs text-gray-500">
                      <span>相似度: {(doc.similarity * 100).toFixed(0)}%</span>
                      {doc.likeScore > 0 && <span>标签匹配: {doc.likeScore}</span>}
                    </div>
                  </div>

                  <p className="text-gray-700 mb-3 text-sm leading-relaxed">
                    {doc.content}
                  </p>

                  <div className="flex flex-wrap gap-1">
                    {doc.tags.map((tag, index) => {
                      const tagState = getTagState(tag);
                      const getTagStyle = () => {
                        switch(tagState) {
                          case 'like': return 'bg-green-100 text-green-800 border-green-200';
                          case 'must': return 'bg-red-100 text-red-800 border-red-200';
                          case 'mustNot': return 'bg-gray-100 text-gray-800 border-gray-400';
                          default: return 'bg-gray-100 hover:bg-gray-200 text-gray-700';
                        }
                      };

                      return (
                        <button
                          key={index}
                          onClick={() => toggleTag(tag)}
                          className={`px-2 py-1 rounded text-xs transition-colors border ${getTagStyle()}`}
                          title={`点击切换标签状态 (当前: ${tagState === 'none' ? '未选择' :
                            tagState === 'like' ? 'Like' :
                            tagState === 'must' ? 'Must' : 'Must Not'})`}
                        >
                          {tagState !== 'none' && (
                            <span className="mr-1">
                              {tagState === 'like' ? '~' : tagState === 'must' ? '+' : '-'}
                            </span>
                          )}
                          {tag}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}

              {searchResults.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  <FileText className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>没有找到匹配的文档</p>
                </div>
              )}
            </div>
          </div>

          {/* 推荐标签 */}
          <div>
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <Tag className="h-5 w-5" />
              推荐标签 (按EIG排序)
            </h2>

            <div className="space-y-3">
              {availableTags.map(({ tag, frequency, eig }) => (
                <div key={tag} className="border border-gray-200 rounded-lg p-3">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-medium text-gray-900">{tag}</span>
                    <span className="text-xs text-gray-500">
                      EIG: {eig.toFixed(1)}
                    </span>
                  </div>

                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm text-gray-600">
                      出现频次: {frequency}
                    </span>
                  </div>

                  <div className="flex gap-1">
                    <button
                      onClick={() => addTag(tag, 'like')}
                      className="flex-1 px-2 py-1 bg-green-100 hover:bg-green-200 text-green-800 rounded text-xs transition-colors"
                    >
                      Like
                    </button>
                    <button
                      onClick={() => addTag(tag, 'must')}
                      className="flex-1 px-2 py-1 bg-red-100 hover:bg-red-200 text-red-800 rounded text-xs transition-colors"
                    >
                      Must
                    </button>
                    <button
                      onClick={() => addTag(tag, 'mustNot')}
                      className="flex-1 px-2 py-1 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded text-xs transition-colors"
                    >
                      Not
                    </button>
                  </div>
                </div>
              ))}

              {availableTags.length === 0 && (
                <div className="text-center py-4 text-gray-500">
                  <Tag className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">暂无推荐标签</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 使用说明 */}
        <div className="mt-8 p-4 bg-blue-50 rounded-lg">
          <h3 className="font-semibold text-blue-900 mb-2">使用说明:</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• 输入查询词后，可添加标签进行精确搜索</li>
            <li>• 标签前缀: + (必须包含), - (必须不包含), ~ (喜欢包含，无前缀默认为~)</li>
            <li>• <strong>文档标签点击循环</strong>: 未选择 → Like(~) → Must(+) → Must Not(-) → 移除</li>
            <li>• 右侧推荐标签可直接添加为指定类型</li>
            <li>• 推荐标签按期望信息增益(EIG)排序，帮助优化搜索策略</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default NaviSearch;
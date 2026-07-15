import { Typography, Divider, Table, Tag, Input, Card, Row, Col, Alert } from 'antd';
import { useState, useMemo } from 'react';

const { Title, Paragraph, Text } = Typography;

interface ApiEndpoint {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  path: string;
  summary: string;
  params?: { name: string; type: string; required: boolean; desc: string }[];
  body?: string;
  responseExample: string;
}

const ENDPOINTS: ApiEndpoint[] = [
  {
    method: 'GET',
    path: '/api/v1/health',
    summary: '健康检查',
    responseExample: `{
  "status": "ok",
  "service": "kb-manager"
}`,
  },
  {
    method: 'GET',
    path: '/api/v1/stats',
    summary: '获取系统统计信息（文件数、片段数、数据库大小等）',
    responseExample: `{
  "total_files": 12,
  "total_chunks": 348,
  "ready_files": 10,
  "processing_files": 1,
  "failed_files": 1,
  "db_size_mb": 15.32,
  "embedding_dim": 2560
}`,
  },
  {
    method: 'POST',
    path: '/api/v1/files/upload',
    summary: '上传文件，自动触发分段+向量化（后台异步处理）',
    params: [
      { name: 'file', type: 'multipart/form-data', required: true, desc: '上传的文件（支持 txt/md/pdf/docx/csv/json/html）' },
    ],
    responseExample: `{
  "id": "a1b2c3d4-...",
  "filename": "report.pdf",
  "file_size": 1048576,
  "file_type": "pdf",
  "content_hash": "sha256...",
  "chunk_count": 0,
  "status": "pending",
  "created_at": "2026-07-15T10:00:00",
  "updated_at": "2026-07-15T10:00:00"
}`,
  },
  {
    method: 'GET',
    path: '/api/v1/files',
    summary: '获取文件列表',
    params: [
      { name: 'skip', type: 'int', required: false, desc: '跳过条数（默认 0）' },
      { name: 'limit', type: 'int', required: false, desc: '返回条数（默认 50）' },
      { name: 'status', type: 'string', required: false, desc: '按状态过滤：pending/processing/ready/failed' },
    ],
    responseExample: `{
  "total": 12,
  "items": [
    {
      "id": "a1b2c3d4-...",
      "filename": "report.pdf",
      "file_size": 1048576,
      "file_type": "pdf",
      "chunk_count": 28,
      "status": "ready",
      "created_at": "2026-07-15T10:00:00",
      "updated_at": "2026-07-15T10:02:30"
    }
  ]
}`,
  },
  {
    method: 'GET',
    path: '/api/v1/files/{file_id}',
    summary: '获取单个文件详情',
    responseExample: `{
  "id": "a1b2c3d4-...",
  "filename": "report.pdf",
  "file_size": 1048576,
  "file_type": "pdf",
  "content_hash": "sha256...",
  "chunk_count": 28,
  "status": "ready",
  "error_message": null,
  "created_at": "2026-07-15T10:00:00",
  "updated_at": "2026-07-15T10:02:30"
}`,
  },
  {
    method: 'DELETE',
    path: '/api/v1/files/{file_id}',
    summary: '删除文件及其所有分段和向量数据（级联删除）',
    responseExample: `{
  "message": "删除成功",
  "file_id": "a1b2c3d4-..."
}`,
  },
  {
    method: 'POST',
    path: '/api/v1/files/{file_id}/reprocess',
    summary: '重新分段+向量化（先清除旧分段，再重新处理）',
    responseExample: `{
  "file_id": "a1b2c3d4-...",
  "status": "pending",
  "message": "已加入处理队列"
}`,
  },
  {
    method: 'GET',
    path: '/api/v1/files/{file_id}/chunks',
    summary: '获取文件的分段列表',
    params: [
      { name: 'skip', type: 'int', required: false, desc: '跳过条数（默认 0）' },
      { name: 'limit', type: 'int', required: false, desc: '返回条数（默认 100）' },
    ],
    responseExample: `{
  "total": 28,
  "items": [
    {
      "id": "chunk-uuid-...",
      "file_id": "a1b2c3d4-...",
      "chunk_index": 0,
      "content": "这是第一个文本片段...",
      "char_count": 500,
      "char_offset": 0,
      "metadata": null,
      "created_at": "2026-07-15T10:01:00"
    }
  ]
}`,
  },
  {
    method: 'POST',
    path: '/api/v1/retrieve',
    summary: '语义检索：输入查询文本 → 向量化 → pgvector 余弦相似度检索 → 返回 Top-K 片段',
    body: `{
  "query": "什么是知识库",
  "top_k": 5,
  "distance_metric": "cosine",
  "score_threshold": 0.0,
  "kb_id": null,
  "file_id": null
}`,
    responseExample: `{
  "query": "什么是知识库",
  "total": 5,
  "results": [
    {
      "chunk_id": "chunk-uuid-...",
      "file_id": "a1b2c3d4-...",
      "filename": "kb_intro.pdf",
      "chunk_index": 3,
      "content": "知识库是结构化的信息集合...",
      "score": 0.8923,
      "metadata": {}
    }
  ]
}`,
  },
  {
    method: 'GET',
    path: '/api/v1/config',
    summary: '获取所有系统配置项',
    responseExample: `{
  "items": [
    { "key": "chunk_size", "value": 500, "description": "分段长度" },
    { "key": "embedding_model", "value": "qwen3-embedding:4b", "description": "向量模型名称" }
  ]
}`,
  },
  {
    method: 'PUT',
    path: '/api/v1/config',
    summary: '更新单个配置项',
    body: `{
  "key": "chunk_size",
  "value": 800
}`,
    responseExample: `{
  "message": "配置已更新",
  "key": "chunk_size",
  "value": 800
}`,
  },
];

const METHOD_COLORS: Record<string, string> = {
  GET: 'blue',
  POST: 'green',
  PUT: 'orange',
  DELETE: 'red',
};

export default function ApiDocs() {
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    if (!search.trim()) return ENDPOINTS;
    const q = search.toLowerCase();
    return ENDPOINTS.filter(
      (e) => e.path.toLowerCase().includes(q) || e.summary.toLowerCase().includes(q),
    );
  }, [search]);

  return (
    <div style={{ maxWidth: 960 }}>
      <Title level={3}>API 文档</Title>
      <Paragraph type="secondary">
        KB Manager 提供 11 个 RESTful API 端点。基础路径 <Text code>/api/v1</Text>，完整 OpenAPI 文档见{' '}
        <a href="/docs" target="_blank" rel="noreferrer">
          /docs
        </a>{' '}
        (Swagger UI)。
      </Paragraph>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="快速试用"
        description={
          <span>
            可直接在终端调用：<Text code copyable>{`curl -X POST http://localhost:8900/api/v1/retrieve -H "Content-Type: application/json" -d '{"query":"测试","top_k":3}'`}</Text>
          </span>
        }
      />

      <Input.Search
        placeholder="搜索接口路径或描述…"
        allowClear
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ marginBottom: 16, maxWidth: 400 }}
      />

      {filtered.map((ep, idx) => (
        <Card
          key={idx}
          size="small"
          style={{ marginBottom: 12 }}
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <Tag color={METHOD_COLORS[ep.method]} style={{ margin: 0, fontWeight: 600 }}>
                {ep.method}
              </Tag>
              <Text code style={{ fontSize: 13 }}>{ep.path}</Text>
            </div>
          }
        >
          <Paragraph style={{ marginBottom: 8 }}>{ep.summary}</Paragraph>

          {ep.params && ep.params.length > 0 && (
            <>
              <Text strong style={{ fontSize: 12 }}>参数</Text>
              <Table
                size="small"
                pagination={false}
                style={{ marginBottom: 8 }}
                dataSource={ep.params}
                rowKey="name"
                columns={[
                  { title: '名称', dataIndex: 'name', width: 120, render: (v: string) => <Text code>{v}</Text> },
                  { title: '类型', dataIndex: 'type', width: 140 },
                  {
                    title: '必填',
                    dataIndex: 'required',
                    width: 60,
                    render: (v: boolean) => (v ? <Tag color="red">是</Tag> : <Tag>否</Tag>),
                  },
                  { title: '说明', dataIndex: 'desc' },
                ]}
              />
            </>
          )}

          {ep.body && (
            <>
              <Text strong style={{ fontSize: 12 }}>请求体</Text>
              <pre style={{
                background: '#f6f8fa',
                padding: 12,
                borderRadius: 6,
                fontSize: 12,
                overflow: 'auto',
                margin: '4px 0 8px',
              }}>{ep.body}</pre>
            </>
          )}

          <Text strong style={{ fontSize: 12 }}>响应示例</Text>
          <pre style={{
            background: '#f6f8fa',
            padding: 12,
            borderRadius: 6,
            fontSize: 12,
            overflow: 'auto',
            margin: '4px 0 0',
          }}>{ep.responseExample}</pre>
        </Card>
      ))}

      <Divider />
      <Row gutter={16}>
        <Col span={8}>
          <Card size="small">
            <Text strong>文件状态流转</Text>
            <div style={{ marginTop: 8, fontSize: 12, lineHeight: 2 }}>
              <Tag>pending</Tag> 上传待处理
              <br />
              <Tag color="processing">processing</Tag> 分段+向量化中
              <br />
              <Tag color="success">ready</Tag> 处理完成，可检索
              <br />
              <Tag color="error">failed</Tag> 处理失败
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Text strong>支持的文件格式</Text>
            <div style={{ marginTop: 8 }}>
              {['txt', 'md', 'pdf', 'docx', 'csv', 'json', 'html'].map((t) => (
                <Tag key={t} style={{ marginBottom: 4 }}>{t}</Tag>
              ))}
            </div>
            <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
              PDF 解析优先使用 MinerU（版面分析/表格/OCR），未安装时降级 pypdf
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Text strong>配置项</Text>
            <div style={{ marginTop: 8, fontSize: 12, lineHeight: 1.8 }}>
              embedding_api_base · embedding_model<br />
              embedding_timeout · embedding_batch_size<br />
              chunk_size · chunk_overlap · chunk_strategy<br />
              retrieve_top_k · retrieve_distance_metric<br />
              retrieve_score_threshold
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

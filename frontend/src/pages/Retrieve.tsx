import { useState } from 'react';
import { Card, Input, Button, Table, Tag, Space, Statistic, Row, Col, Empty, Spin } from 'antd';
import { SearchOutlined, ClearOutlined } from '@ant-design/icons';
import { retrieve } from '../api';

interface SearchResult {
  chunk_id: string;
  file_id: string;
  filename: string;
  chunk_index: number;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
}

export default function Retrieve() {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searched, setSearched] = useState(false);
  const [latencyMs, setLatencyMs] = useState(0);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    const start = performance.now();
    try {
      const res = await retrieve({ query: query.trim(), top_k: topK });
      setResults(res.data.results);
      setLatencyMs(Math.round(performance.now() - start));
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setQuery('');
    setResults([]);
    setSearched(false);
  };

  const scoreColor = (score: number) => {
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'processing';
    if (score >= 0.4) return 'warning';
    return 'default';
  };

  const columns = [
    {
      title: '相似度',
      dataIndex: 'score',
      width: 100,
      render: (v: number) => <Tag color={scoreColor(v)}>{(v * 100).toFixed(1)}%</Tag>,
    },
    { title: '文件', dataIndex: 'filename', width: 200, ellipsis: true },
    { title: '#', dataIndex: 'chunk_index', width: 50 },
    { title: '内容', dataIndex: 'content', render: (v: string) => <div style={{ whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto' }}>{v}</div> },
  ];

  return (
    <div>
      <Card title="语义检索">
        <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
          <Input
            placeholder="输入查询文本..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onPressEnter={handleSearch}
            size="large"
          />
          <Button
            type="primary"
            size="large"
            icon={<SearchOutlined />}
            onClick={handleSearch}
            loading={loading}
          >
            检索
          </Button>
          <Button size="large" icon={<ClearOutlined />} onClick={handleClear}>清空</Button>
        </Space.Compact>

        <Space style={{ marginBottom: 16 }}>
          <span>返回数量 (Top-K):</span>
          <Input
            type="number"
            min={1}
            max={50}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value) || 5)}
            style={{ width: 80 }}
          />
        </Space>
      </Card>

      {loading && (
        <Card style={{ marginTop: 16, textAlign: 'center' }}>
          <Spin tip="正在检索..." />
        </Card>
      )}

      {!loading && searched && (
        <Card
          title="检索结果"
          style={{ marginTop: 16 }}
          extra={
            <Row gutter={16}>
              <Col><Statistic title="结果数" value={results.length} /></Col>
              <Col><Statistic title="耗时" value={latencyMs} suffix="ms" /></Col>
            </Row>
          }
        >
          {results.length === 0 ? (
            <Empty description="未找到相关结果" />
          ) : (
            <Table
              columns={columns}
              dataSource={results}
              rowKey="chunk_id"
              pagination={false}
              size="small"
            />
          )}
        </Card>
      )}
    </div>
  );
}

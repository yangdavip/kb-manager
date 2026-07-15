import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Table, Tag, Progress } from 'antd';
import { FileTextOutlined, DatabaseOutlined, CheckCircleOutlined, SyncOutlined } from '@ant-design/icons';
import { getStats, getFiles } from '../api';

interface Stats {
  total_files: number;
  total_chunks: number;
  ready_files: number;
  processing_files: number;
  failed_files: number;
  db_size_mb: number;
  embedding_dim: number;
  vector_index?: { name: string; def: string }[];
  hnsw_config?: Record<string, string>;
}

interface FileItem {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: string;
  created_at: string;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [recentFiles, setRecentFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [statsRes, filesRes] = await Promise.all([
          getStats(),
          getFiles({ limit: 10 }),
        ]);
        setStats(statsRes.data);
        setRecentFiles(filesRes.data.items);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const statusTag = (status: string) => {
    const map: Record<string, { color: string; icon?: React.ReactNode }> = {
      ready: { color: 'success', icon: <CheckCircleOutlined /> },
      processing: { color: 'processing', icon: <SyncOutlined spin /> },
      pending: { color: 'default' },
      failed: { color: 'error' },
    };
    const cfg = map[status] || { color: 'default' };
    return <Tag color={cfg.color} icon={cfg.icon}>{status}</Tag>;
  };

  const columns = [
    { title: '文件名', dataIndex: 'filename', ellipsis: true },
    { title: '类型', dataIndex: 'file_type', width: 80 },
    { title: '大小', dataIndex: 'file_size', width: 100, render: (v: number) => `${(v / 1024).toFixed(1)} KB` },
    { title: '分段', dataIndex: 'chunk_count', width: 70 },
    { title: '状态', dataIndex: 'status', width: 100, render: statusTag },
    { title: '上传时间', dataIndex: 'created_at', width: 180, render: (v: string) => new Date(v).toLocaleString('zh-CN') },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={4}>
          <Card>
            <Statistic
              title="文件总数"
              value={stats?.total_files ?? 0}
              prefix={<FileTextOutlined />}
              loading={loading}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="分段总数"
              value={stats?.total_chunks ?? 0}
              prefix={<DatabaseOutlined />}
              loading={loading}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="就绪文件"
              value={stats?.ready_files ?? 0}
              styles={{ content: { color: '#52c41a' } }}
              loading={loading}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="处理中"
              value={stats?.processing_files ?? 0}
              styles={{ content: { color: '#1677ff' } }}
              loading={loading}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="失败"
              value={stats?.failed_files ?? 0}
              styles={{ content: { color: '#ff4d4f' } }}
              loading={loading}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="数据库大小"
              value={stats?.db_size_mb ?? 0}
              suffix="MB"
              loading={loading}
            />
          </Card>
        </Col>
      </Row>

      <Card title="最近上传文件" loading={loading}>
        <Table
          columns={columns}
          dataSource={recentFiles}
          rowKey="id"
          pagination={false}
          size="small"
        />
      </Card>

      {stats && (
        <Card title="系统信息" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={6}><p>Embedding 维度: <strong>{stats.embedding_dim}</strong></p></Col>
            <Col span={6}><p>向量索引: {stats.vector_index && stats.vector_index.length > 0 ? <Tag color="success">HNSW</Tag> : <Tag>无</Tag>}</p></Col>
            <Col span={12}>
              <Progress
                percent={stats.total_files > 0 ? Math.round((stats.ready_files / stats.total_files) * 100) : 0}
                status="active"
                format={(p) => `${p}% 就绪`}
              />
            </Col>
          </Row>
        </Card>
      )}
    </div>
  );
}

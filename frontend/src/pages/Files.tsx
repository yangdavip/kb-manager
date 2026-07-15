import { useEffect, useState, useCallback } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Upload,
  Tag,
  Modal,
  message,
  Tooltip,
  Popconfirm,
  Typography,
  Progress,
} from 'antd';
import {
  UploadOutlined,
  DeleteOutlined,
  ReloadOutlined,
  EyeOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { getFiles, deleteFile, reprocessFile, getChunks, uploadFile } from '../api';

interface FileItem {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: string;
  progress_done: number;
  progress_total: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

interface ChunkItem {
  id: string;
  chunk_index: number;
  content: string;
  token_count: number;
  embed_status: string;
  metadata: Record<string, unknown>;
}

const { Paragraph, Text } = Typography;

export default function Files() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [chunksModal, setChunksModal] = useState<{ visible: boolean; fileId: string | null; chunks: ChunkItem[]; loading: boolean }>({
    visible: false,
    fileId: null,
    chunks: [],
    loading: false,
  });

  const loadFiles = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getFiles({ limit: 200 });
      setFiles(res.data.items);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setUploadProgress(0);
    try {
      await uploadFile(file, setUploadProgress);
      message.success(`${file.name} 上传成功`);
      await loadFiles();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '上传失败';
      message.error(msg);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
    return false; // 阻止 antd 默认上传
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteFile(id);
      message.success('删除成功');
      await loadFiles();
    } catch {
      message.error('删除失败');
    }
  };

  const handleReprocess = async (id: string) => {
    try {
      await reprocessFile(id);
      message.success('已重新提交处理');
      await loadFiles();
    } catch {
      message.error('重新处理失败');
    }
  };

  const handleViewChunks = async (fileId: string) => {
    setChunksModal({ visible: true, fileId, chunks: [], loading: true });
    try {
      const res = await getChunks(fileId, { limit: 100 });
      setChunksModal((prev) => ({ ...prev, chunks: res.data.items || res.data, loading: false }));
    } catch {
      message.error('获取分段失败');
      setChunksModal((prev) => ({ ...prev, loading: false }));
    }
  };

  const statusTag = (status: string) => {
    const map: Record<string, { color: string; icon?: React.ReactNode }> = {
      ready: { color: 'success', icon: <CheckCircleOutlined /> },
      processing: { color: 'processing', icon: <SyncOutlined spin /> },
      pending: { color: 'default', icon: <ClockCircleOutlined /> },
      failed: { color: 'error', icon: <ExclamationCircleOutlined /> },
    };
    const cfg = map[status] || { color: 'default' };
    return <Tag color={cfg.color} icon={cfg.icon}>{status}</Tag>;
  };

  const columns = [
    { title: '文件名', dataIndex: 'filename', ellipsis: true, width: 250 },
    { title: '类型', dataIndex: 'file_type', width: 70 },
    { title: '大小', dataIndex: 'file_size', width: 90, render: (v: number) => `${(v / 1024).toFixed(1)} KB` },
    { title: '分段数', dataIndex: 'chunk_count', width: 70 },
    { title: '状态', dataIndex: 'status', width: 100, render: statusTag },
    {
      title: '进度',
      width: 120,
      render: (_: unknown, record: FileItem) => {
        if (record.status === 'ready' || record.status === 'failed') return null;
        const total = record.progress_total || 0;
        const done = record.progress_done || 0;
        if (total === 0) return null;
        const pct = Math.round((done / total) * 100);
        return <Progress percent={pct} size="small" format={() => `${done}/${total}`} />;
      },
    },
    {
      title: '错误',
      dataIndex: 'error_message',
      width: 200,
      ellipsis: true,
      render: (v: string | null) => v ? <Tooltip title={v}><Text type="danger">{v}</Text></Tooltip> : '-',
    },
    { title: '上传时间', dataIndex: 'created_at', width: 160, render: (v: string) => new Date(v).toLocaleString('zh-CN') },
    {
      title: '操作',
      width: 180,
      render: (_: unknown, record: FileItem) => (
        <Space size="small">
          <Button size="small" icon={<EyeOutlined />} onClick={() => handleViewChunks(record.id)} disabled={record.chunk_count === 0}>
            分段
          </Button>
          <Button size="small" icon={<SyncOutlined />} onClick={() => handleReprocess(record.id)} disabled={record.status === 'processing'}>
            重处理
          </Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title="文件管理"
        extra={
          <Space>
            <Upload
              beforeUpload={handleUpload}
              showUploadList={false}
              accept=".txt,.md,.pdf,.docx,.html,.csv"
            >
              <Button
                type="primary"
                icon={<UploadOutlined />}
                loading={uploading}
              >
                上传文件
              </Button>
            </Upload>
            <Button icon={<ReloadOutlined />} onClick={loadFiles}>刷新</Button>
          </Space>
        }
      >
        {uploading && (
          <div style={{ marginBottom: 16 }}>
            <Progress percent={uploadProgress} status="active" />
          </div>
        )}
        <Table
          columns={columns}
          dataSource={files}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true }}
          size="small"
        />
      </Card>

      <Modal
        title="文件分段详情"
        open={chunksModal.visible}
        onCancel={() => setChunksModal({ visible: false, fileId: null, chunks: [], loading: false })}
        footer={null}
        width={800}
      >
        <Table
          dataSource={chunksModal.chunks}
          rowKey="id"
          loading={chunksModal.loading}
          pagination={{ pageSize: 10 }}
          size="small"
          columns={[
            { title: '#', dataIndex: 'chunk_index', width: 50 },
            { title: '内容', dataIndex: 'content', render: (v: string) => <Paragraph ellipsis={{ rows: 3 }}>{v}</Paragraph> },
            { title: 'Tokens', dataIndex: 'token_count', width: 80 },
            {
              title: '状态',
              dataIndex: 'embed_status',
              width: 80,
              render: (v: string) => {
                const colors: Record<string, string> = { done: 'success', pending: 'default', failed: 'error' };
                return <Tag color={colors[v] || 'default'}>{v}</Tag>;
              },
            },
          ]}
        />
      </Modal>
    </div>
  );
}


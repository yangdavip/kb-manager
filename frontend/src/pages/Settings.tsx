import { useEffect, useState } from 'react';
import { Card, Table, Button, Input, message, Tag, Tooltip } from 'antd';
import { ReloadOutlined, EditOutlined, CheckOutlined } from '@ant-design/icons';
import { getConfig, updateConfig } from '../api';

interface ConfigItem {
  key: string;
  value: string | number;
  description: string;
}

export default function Settings() {
  const [configs, setConfigs] = useState<ConfigItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editingValue, setEditingValue] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const res = await getConfig();
      setConfigs(res.data.items);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSave = async (key: string) => {
    try {
      await updateConfig(key, editingValue);
      message.success('配置已更新');
      setEditingKey(null);
      await load();
    } catch {
      message.error('更新失败');
    }
  };

  const columns = [
    { title: '配置项', dataIndex: 'key', width: 250 },
    {
      title: '值',
      dataIndex: 'value',
      render: (value: string, record: ConfigItem) => {
        if (editingKey === record.key) {
          return (
            <Input
              value={String(editingValue)}
              onChange={(e) => setEditingValue(e.target.value)}
              onPressEnter={() => handleSave(record.key)}
              size="small"
            />
          );
        }
        const isSecret = record.key.includes('key') || record.key.includes('secret');
        return isSecret ? <Tag>{value ? '***' : '未设置'}</Tag> : <span>{value}</span>;
      },
    },
    { title: '说明', dataIndex: 'description', ellipsis: true },
    {
      title: '操作',
      width: 100,
      render: (_: unknown, record: ConfigItem) => (
        editingKey === record.key ? (
          <Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => handleSave(record.key)}>保存</Button>
        ) : (
          <Tooltip title="编辑">
            <Button size="small" icon={<EditOutlined />} onClick={() => { setEditingKey(record.key); setEditingValue(String(record.value)); }} />
          </Tooltip>
        )
      ),
    },
  ];

  return (
    <Card
      title="系统设置"
      extra={<Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>}
    >
      <Table
        columns={columns}
        dataSource={configs}
        rowKey="key"
        loading={loading}
        pagination={false}
        size="small"
      />
    </Card>
  );
}

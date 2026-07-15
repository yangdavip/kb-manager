import { Layout, Menu, theme } from 'antd';
import {
  DashboardOutlined,
  FileTextOutlined,
  SearchOutlined,
  SettingOutlined,
  ApiOutlined,
} from '@ant-design/icons';
import { useState } from 'react';
import Dashboard from './pages/Dashboard';
import Files from './pages/Files';
import Retrieve from './pages/Retrieve';
import Settings from './pages/Settings';
import ApiDocs from './pages/ApiDocs';

const { Sider, Content } = Layout;

export default function App() {
  const [collapsed, setCollapsed] = useState(false);
  const [activeKey, setActiveKey] = useState('dashboard');
  const { token } = theme.useToken();

  const pages: Record<string, React.ReactNode> = {
    dashboard: <Dashboard />,
    files: <Files />,
    retrieve: <Retrieve />,
    api: <ApiDocs />,
    settings: <Settings />,
  };

  const menuItems = [
    { key: 'dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
    { key: 'files', icon: <FileTextOutlined />, label: '文件管理' },
    { key: 'retrieve', icon: <SearchOutlined />, label: '语义检索' },
    { key: 'api', icon: <ApiOutlined />, label: 'API 文档' },
    { key: 'settings', icon: <SettingOutlined />, label: '系统设置' },
  ];

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="light"
        style={{ borderRight: `1px solid ${token.colorBorderSecondary}` }}
      >
        <div
          style={{
            height: 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 700,
            fontSize: collapsed ? 14 : 16,
            color: token.colorPrimary,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
          }}
        >
          {collapsed ? 'KB' : 'KB Manager'}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[activeKey]}
          items={menuItems}
          onClick={(e) => setActiveKey(e.key)}
        />
      </Sider>
      <Layout>
        <Content style={{ overflow: 'auto', padding: 24 }}>{pages[activeKey]}</Content>
      </Layout>
    </Layout>
  );
}

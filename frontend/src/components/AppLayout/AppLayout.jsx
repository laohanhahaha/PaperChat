import Navbar from '../Navbar/Navbar';

// 带导航栏的布局组件
function AppLayout({ children }) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Navbar />
      <main style={{ flex: 1, marginLeft: '64px', overflowY: 'auto', minHeight: '100vh' }}>
        {children}
      </main>
    </div>
  );
}

export default AppLayout;

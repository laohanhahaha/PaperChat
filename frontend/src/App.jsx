import { useEffect, useState, lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import useTheme, { initializeTheme } from './hooks/useTheme';
import useAuthStore from './stores/authStore';
import useSettingsStore from './stores/settingsStore';
import Toast from './components/Toast/Toast';
import ErrorBoundary from './components/ErrorBoundary/ErrorBoundary';
import AppLayout from './components/AppLayout/AppLayout';
import SetupWizard from './components/Config/SetupWizard';
import OfflineBanner from './components/common/OfflineBanner';
import './App.css';

// 初始化主题（在应用启动时立即应用，避免闪烁）
initializeTheme();

// 懒加载页面组件（代码分割）
const PaperList = lazy(() => import('./pages/PaperList'));
const ChatPage = lazy(() => import('./pages/ChatPage'));
const WritingPage = lazy(() => import('./pages/WritingPage'));
const KnowledgePage = lazy(() => import('./pages/KnowledgePage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const ReaderPage = lazy(() => import('./pages/ReaderPage'));

// 页面加载中的 fallback 组件
const PageLoader = () => (
  <div style={{ 
    display: 'flex', 
    justifyContent: 'center', 
    alignItems: 'center', 
    height: '100vh',
    color: 'var(--color-text-secondary)',
    fontSize: '16px',
    background: 'var(--color-bg-primary)'
  }}>
    <div style={{ textAlign: 'center' }}>
      <div className="loading-spinner" style={{
        width: '40px',
        height: '40px',
        border: '3px solid var(--color-border)',
        borderTopColor: 'var(--color-accent)',
        borderRadius: '50%',
        animation: 'spin 1s linear infinite',
        margin: '0 auto 16px'
      }}></div>
      加载中...
    </div>
  </div>
);

// 路由配置组件
function App() {
  const { initialize } = useAuthStore();
  const fetchSettings = useSettingsStore(state => state.fetchSettings);

  // 新用户引导向导状态
  const [setupCompleted, setSetupCompleted] = useState(() => {
    return localStorage.getItem('setup_completed') === 'true';
  });

  // 应用主题
  useTheme();

  // 初始化认证状态
  useEffect(() => {
    initialize();
  }, [initialize]);

  // 加载设置（包含主题等外观配置）
  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  return (
    <ErrorBoundary>
      <OfflineBanner />
      <Toast />
      {/* 新用户引导向导 */}
      {!setupCompleted && (
        <SetupWizard onComplete={() => setSetupCompleted(true)} />
      )}
      <Routes>
        {/* 论文列表页 */}
        <Route
          path="/papers"
          element={
            <AppLayout>
              <ErrorBoundary>
                <Suspense fallback={<PageLoader />}>
                  <PaperList />
                </Suspense>
              </ErrorBoundary>
            </AppLayout>
          }
        />

        {/* 聊天页面 */}
        <Route
          path="/chat"
          element={
            <AppLayout>
              <ErrorBoundary>
                <Suspense fallback={<PageLoader />}>
                  <ChatPage />
                </Suspense>
              </ErrorBoundary>
            </AppLayout>
          }
        />
        
        {/* 阅读页面 - 不显示导航栏（ReaderPage 自带 Navbar） */}
        <Route
          path="/reader/:id"
          element={
            <ErrorBoundary>
              <Suspense fallback={<PageLoader />}>
                <ReaderPage />
              </Suspense>
            </ErrorBoundary>
          }
        />

        {/* 知识库页面 */}
        <Route
          path="/knowledge"
          element={
            <AppLayout>
              <ErrorBoundary>
                <Suspense fallback={<PageLoader />}>
                  <KnowledgePage />
                </Suspense>
              </ErrorBoundary>
            </AppLayout>
          }
        />

        {/* 写作辅助页面 */}
        <Route
          path="/writing"
          element={
            <AppLayout>
              <ErrorBoundary>
                <Suspense fallback={<PageLoader />}>
                  <WritingPage />
                </Suspense>
              </ErrorBoundary>
            </AppLayout>
          }
        />

        {/* 设置页面 */}
        <Route
          path="/settings"
          element={
            <AppLayout>
              <ErrorBoundary>
                <Suspense fallback={<PageLoader />}>
                  <SettingsPage />
                </Suspense>
              </ErrorBoundary>
            </AppLayout>
          }
        />
        
        {/* 根路径重定向 */}
        <Route
          path="/"
          element={
            <Navigate to="/papers" replace />
          }
        />
        
        {/* 404 页面 */}
        <Route path="*" element={
          <Suspense fallback={<PageLoader />}>
            <NotFoundPage />
          </Suspense>
        } />
      </Routes>
    </ErrorBoundary>
  );
}

export default App;

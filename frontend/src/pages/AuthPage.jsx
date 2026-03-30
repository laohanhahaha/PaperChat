import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import useAuthStore from '../stores/authStore';
import styles from './AuthPage.module.css';

function AuthPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [isLogin, setIsLogin] = useState(true);
  
  const { login, register, isAuthenticated, isLoading, error, clearError } = useAuthStore();

  // 表单状态
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [formError, setFormError] = useState('');

  // 如果已登录，跳转到主页
  useEffect(() => {
    if (isAuthenticated) {
      const from = location.state?.from?.pathname || '/';
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, location]);

  // 清除错误
  useEffect(() => {
    clearError();
    setFormError('');
  }, [isLogin, clearError]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setFormError('');
    clearError();
  };

  const validateForm = () => {
    if (!formData.username.trim()) {
      setFormError('请输入用户名');
      return false;
    }
    if (!isLogin && !formData.email.trim()) {
      setFormError('请输入邮箱');
      return false;
    }
    if (!formData.password) {
      setFormError('请输入密码');
      return false;
    }
    if (!isLogin && formData.password.length < 6) {
      setFormError('密码长度至少为 6 位');
      return false;
    }
    if (!isLogin && formData.password !== formData.confirmPassword) {
      setFormError('两次输入的密码不一致');
      return false;
    }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) return;

    if (isLogin) {
      // 登录
      const result = await login({
        username: formData.username,
        password: formData.password,
      });
      if (!result.success) {
        setFormError(result.error);
      }
    } else {
      // 注册
      const result = await register({
        username: formData.username,
        email: formData.email,
        password: formData.password,
      });
      if (result.success) {
        // 注册成功，自动切换到登录
        setIsLogin(true);
        setFormData(prev => ({ ...prev, password: '', confirmPassword: '' }));
        setFormError('注册成功，请登录');
      } else {
        setFormError(result.error);
      }
    }
  };

  const toggleMode = () => {
    setIsLogin(!isLogin);
    setFormData({
      username: '',
      email: '',
      password: '',
      confirmPassword: '',
    });
    setFormError('');
  };

  return (
    <div className={styles.authContainer}>
      <div className={styles.authCard}>
        {/* Logo 和标题 */}
        <div className={styles.authHeader}>
          <h1 className={styles.logo}>PaperChat</h1>
          <p className={styles.subtitle}>智能论文阅读与问答系统</p>
        </div>

        {/* Tab 切换 */}
        <div className={styles.tabContainer}>
          <button
            className={`${styles.tab} ${isLogin ? styles.tabActive : ''}`}
            onClick={() => setIsLogin(true)}
            type="button"
          >
            登录
          </button>
          <button
            className={`${styles.tab} ${!isLogin ? styles.tabActive : ''}`}
            onClick={() => setIsLogin(false)}
            type="button"
          >
            注册
          </button>
        </div>

        {/* 表单 */}
        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.inputGroup}>
            <label htmlFor="username" className={styles.label}>
              用户名
            </label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleInputChange}
              className={styles.input}
              placeholder="请输入用户名"
              disabled={isLoading}
            />
          </div>

          {!isLogin && (
            <div className={styles.inputGroup}>
              <label htmlFor="email" className={styles.label}>
                邮箱
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                className={styles.input}
                placeholder="请输入邮箱"
                disabled={isLoading}
              />
            </div>
          )}

          <div className={styles.inputGroup}>
            <label htmlFor="password" className={styles.label}>
              密码
            </label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleInputChange}
              className={styles.input}
              placeholder={isLogin ? '请输入密码' : '密码至少 6 位'}
              disabled={isLoading}
            />
          </div>

          {!isLogin && (
            <div className={styles.inputGroup}>
              <label htmlFor="confirmPassword" className={styles.label}>
                确认密码
              </label>
              <input
                type="password"
                id="confirmPassword"
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleInputChange}
                className={styles.input}
                placeholder="请再次输入密码"
                disabled={isLoading}
              />
            </div>
          )}

          {/* 错误提示 */}
          {(formError || error) && (
            <div className={`${styles.error} ${formError && !error && formError === '注册成功，请登录' ? styles.success : ''}`}>
              {formError || error}
            </div>
          )}

          {/* 提交按钮 */}
          <button
            type="submit"
            className={styles.submitBtn}
            disabled={isLoading}
          >
            {isLoading ? (
              <span className={styles.spinner}></span>
            ) : (
              isLogin ? '登录' : '注册'
            )}
          </button>
        </form>

        {/* 切换提示 */}
        <div className={styles.switchHint}>
          {isLogin ? '还没有账号？' : '已有账号？'}
          <button
            type="button"
            onClick={toggleMode}
            className={styles.switchLink}
          >
            {isLogin ? '立即注册' : '立即登录'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default AuthPage;

import { create } from 'zustand';

interface User {
  id: number;
  username: string;
  email: string;
}

interface AuthState {
  user: User;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  initialize: () => void;
  login: () => Promise<{ success: boolean }>;
  register: () => Promise<{ success: boolean }>;
  logout: () => void;
  fetchUser: () => Promise<void>;
  updateUser: () => Promise<{ success: boolean }>;
  clearError: () => void;
}

const useAuthStore = create<AuthState>(() => ({
  // 默认用户状态（个人使用模式，无需登录）
  user: { id: 1, username: 'default', email: 'default@local.dev' },
  isAuthenticated: true,  // 始终为 true
  isLoading: false,
  error: null,

  // 初始化（无需操作）
  initialize: () => {},

  // 以下方法保留但为空操作，以保持兼容性
  login: async () => ({ success: true }),
  register: async () => ({ success: true }),
  logout: () => {},
  fetchUser: async () => {},
  updateUser: async () => ({ success: true }),
  clearError: () => {},
}));

export default useAuthStore;

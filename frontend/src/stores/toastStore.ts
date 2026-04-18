import { create } from 'zustand';

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
  duration: number;
}

interface ToastState {
  toasts: Toast[];
  addToast: (message: string, type?: 'success' | 'error' | 'warning' | 'info', duration?: number) => void;
  removeToast: (id: number) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  warning: (message: string) => void;
  info: (message: string) => void;
}

const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  
  addToast: (message, type = 'error', duration = 4000) => {
    const id = Date.now() + Math.random();
    set(state => ({
      toasts: [...state.toasts, { id, message, type, duration }]
    }));
    setTimeout(() => {
      set(state => ({
        toasts: state.toasts.filter(t => t.id !== id)
      }));
    }, duration);
  },
  
  removeToast: (id) => {
    set(state => ({
      toasts: state.toasts.filter(t => t.id !== id)
    }));
  },
  
  success: (message) => get().addToast(message, 'success', 3000),
  error: (message) => get().addToast(message, 'error', 5000),
  warning: (message) => get().addToast(message, 'warning', 4000),
  info: (message) => get().addToast(message, 'info', 3000),
}));

export default useToastStore;

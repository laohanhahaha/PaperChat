/** @jest-environment jsdom */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import useToastStore from '../stores/toastStore';
import Toast from '../components/Toast/Toast';

// Mock CSS module
vi.mock('../components/Toast/Toast.module.css', () => ({
  default: {
    container: 'container',
    toast: 'toast',
    success: 'success',
    error: 'error',
    icon: 'icon',
    message: 'message',
    closeBtn: 'closeBtn',
    progressTrack: 'progressTrack',
    progressBar: 'progressBar',
  },
}));

describe('Toast 组件', () => {
  beforeEach(() => {
    // 重置 store 状态
    useToastStore.setState({ toasts: [] });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('无 toast 时不渲染任何内容', () => {
    const { container } = render(<Toast />);
    expect(container.innerHTML).toBe('');
  });

  it('success 方法应添加 success 类型的 toast', () => {
    const { success } = useToastStore.getState();
    success('操作成功');

    const { container } = render(<Toast />);
    expect(screen.getByText('操作成功')).toBeInTheDocument();
    expect(container.querySelector('.success')).toBeInTheDocument();
  });

  it('error 方法应添加 error 类型的 toast', () => {
    const { error } = useToastStore.getState();
    error('发生错误');

    const { container } = render(<Toast />);
    expect(screen.getByText('发生错误')).toBeInTheDocument();
    expect(container.querySelector('.error')).toBeInTheDocument();
  });

  it('点击关闭按钮应移除 toast', async () => {
    const { addToast } = useToastStore.getState();
    addToast('可关闭', 'info', 60000);

    render(<Toast />);
    expect(screen.getByText('可关闭')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('关闭'));
    await act(async () => {
      vi.advanceTimersByTime(400); // handleClose 有 300ms 延迟
    });
    expect(screen.queryByText('可关闭')).not.toBeInTheDocument();
  });
});

import api from './index';

/**
 * 获取用户画像摘要
 * @param userId 用户ID
 */
export const getProfile = (userId: number) => api.get(`/profile/${userId}`);

/**
 * 获取推荐论文
 * @param userId 用户ID
 */
export const getRecommendations = (userId: number) => api.get(`/profile/${userId}/recommendations`);

/**
 * 更新盲区状态
 * @param userId 用户ID
 * @param blindspotId 盲区ID
 * @param status 新状态 (blind/improving/mastered)
 */
export const updateBlindspot = (userId: number, blindspotId: number, status: string) =>
  api.put(`/profile/${userId}/blindspots/${blindspotId}`, { status });

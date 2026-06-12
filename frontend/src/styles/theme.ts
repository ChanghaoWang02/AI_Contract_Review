/**
 * 全局主题色常量
 * 替换散点硬编码颜色，统一管理主色调
 */
export const theme = {
  primary: '#4C6EF5',
  primaryHover: '#364FC7',
  success: '#52c41a',
  error: '#ff4d4f',
  warning: '#faad14',
  text: {
    primary: '#333',
    secondary: '#666',
    muted: '#999',
  },
  background: {
    page: '#f5f7fa',
    card: '#fff',
  },
  border: '#e8e8e8',
} as const

export type Theme = typeof theme
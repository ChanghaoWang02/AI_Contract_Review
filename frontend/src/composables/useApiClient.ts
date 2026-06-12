/**
 * 统一 API 调用封装
 * 替换散点 fetch()，统一处理：JSON 序列化、错误提取、HTTP 状态检查
 *
 * base URL 暂用相对路径（当前所有调用均为 /api/... 绝对路径），
 * 后续有环境切换需求时改为拼接 import.meta.env.VITE_API_BASE_URL || ''
 */
import { ref } from 'vue'

export interface ApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  body?: any
  headers?: Record<string, string>
}

export function useApiClient() {
  const loading = ref(false)

  async function request<T>(url: string, opts?: ApiOptions): Promise<T> {
    const method = opts?.method || 'GET'
    const headers: Record<string, string> = { ...opts?.headers }
    let body = opts?.body

    if (body && !(body instanceof FormData) && !(body instanceof Blob)) {
      headers['Content-Type'] = 'application/json'
      body = JSON.stringify(body)
    } else if (body instanceof FormData) {
      // 浏览器自动设置 Content-Type: multipart/form-data + boundary
    }

    const res = await fetch(url, { method, headers, body })
    if (!res.ok) {
      let detail = ''
      try { const err = await res.json(); detail = err.detail || '' } catch { /* ignore */ }
      throw new Error(detail || `请求失败 (HTTP ${res.status})`)
    }
    // 204 No Content
    if (res.status === 204) return undefined as T
    return res.json() as Promise<T>
  }

  return {
    loading,
    get: <T>(url: string) => request<T>(url, { method: 'GET' }),
    post: <T>(url: string, body: any) => request<T>(url, { method: 'POST', body }),
    put: <T>(url: string, body: any) => request<T>(url, { method: 'PUT', body }),
    delete: <T>(url: string) => request<T>(url, { method: 'DELETE' }),
  }
}
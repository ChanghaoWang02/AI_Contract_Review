/**
 * PDF 导出 composable
 * 调用后端导出 API，触发浏览器下载
 */
import { ref } from 'vue'
import { useMessage } from 'naive-ui'

export interface ExportOptions {
  risk_filter?: string   // 默认 "high,medium,low"
  sections?: string      // 默认 "cover,summary,clauses,disclaimer"
}

export function useExportPDF() {
  const exporting = ref(false)
  const message = useMessage()

  async function exportReviewPDF(
    reviewId: number,
    options: ExportOptions = {},
  ): Promise<boolean> {
    if (exporting.value) return false

    exporting.value = true

    const params = new URLSearchParams({
      risk_filter: options.risk_filter || 'high,medium,low',
      sections: options.sections || 'cover,summary,clauses,disclaimer',
    })

    const url = `/api/reviews/${reviewId}/export?${params.toString()}`

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 30_000)

    try {
      const res = await fetch(url, {
        signal: controller.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '导出失败' }))
        const detail: string = err.detail || '导出失败'

        if (res.status === 404) {
          message.error(detail)
        } else if (res.status === 409) {
          message.warning(detail)
        } else if (res.status === 422) {
          message.error(detail)
        } else {
          message.error(detail)
        }
        return false
      }

      // 处理 blob 下载
      const blob = await res.blob()
      const contentDisposition = res.headers.get('Content-Disposition')
      let filename = '审核报告.pdf'
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?([^"]+)"?/)
        if (match) {
          filename = decodeURIComponent(match[1])
        }
      }

      const downloadUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(downloadUrl)

      message.success('报告已下载')
      return true
    } catch (e: any) {
      if (e.name === 'AbortError') {
        message.error('导出超时，请检查网络后重试')
      } else if (e instanceof TypeError && e.message.includes('fetch')) {
        message.error('服务暂不可用，请稍后重试')
      } else {
        message.error('导出失败，请重试')
      }
      return false
    } finally {
      clearTimeout(timeoutId)
      exporting.value = false
    }
  }

  return {
    exporting,
    exportReviewPDF,
  }
}

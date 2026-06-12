/**
 * 审核流程 composable
 * 管理审核创建状态、报告弹窗
 */
import { ref } from 'vue'
import { useReviewStore } from '@/stores/review'
import { useChatStore } from '@/stores/chat'
import { useMessage } from 'naive-ui'

export function useReviewFlow() {
  const reviewStore = useReviewStore()
  const chatStore = useChatStore()
  const message = useMessage()

  const reviewCreating = ref(false)
  const showReport = ref(false)

  async function onSendMessage(content: string, reviewId: number) {
    await chatStore.sendMessage(content, reviewId)
  }

  return {
    reviewCreating,
    showReport,
    onSendMessage,
  }
}
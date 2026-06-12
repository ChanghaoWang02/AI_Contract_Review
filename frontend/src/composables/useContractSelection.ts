/**
 * 合同选择与删除 composable
 * 包含 activeContractId、activeReviewId 和 onSelectContract 逻辑
 */
import { ref } from 'vue'
import { useContractStore } from '@/stores/contract'
import { useReviewStore } from '@/stores/review'
import { useChatStore } from '@/stores/chat'
import { useMessage, useDialog } from 'naive-ui'

export function useContractSelection() {
  const contractStore = useContractStore()
  const reviewStore = useReviewStore()
  const chatStore = useChatStore()
  const message = useMessage()
  const dialog = useDialog()

  const activeContractId = ref<number | null>(null)
  const activeReviewId = ref<number | null>(null)

  async function onSelectContract(id: number, skipConfirm = false) {
    // 点击当前合同：不做任何操作（skipConfirm 时强制重新触发审核，跳过此检查）
    if (id === activeContractId.value && !skipConfirm) return

    activeContractId.value = id
    await contractStore.fetchContract(id)

    // 取消正在进行的 SSE 流并清理消息
    chatStore.clearMessages()

    // 检查是否有已有审核
    const reviews = await reviewStore.fetchReviews(id)
    if (reviews.length > 0) {
      const latest = reviews[0]
      reviewStore.currentReview = latest
      activeReviewId.value = latest.id
      await chatStore.loadHistory(latest.id)
    } else if (skipConfirm) {
      await startReview(id)
    } else {
      const isDraft = contractStore.currentContract?.source === 'draft'
      if (isDraft) {
        activeReviewId.value = null
        reviewStore.currentReview = null
        dialog.info({
          title: '合同尚未审核',
          content: '这份起草的合同还没有进行 AI 审核，要现在发起审核吗？',
          positiveText: '开始审核',
          negativeText: '取消',
          closable: true,
          onPositiveClick: () => {
            startReview(id)
          },
        })
      } else {
        await startReview(id)
      }
    }
  }

  async function startReview(contractId: number) {
    const result = await reviewStore.createReview(contractId)
    if (!result) {
      message.error('审核创建失败，请重试')
      return
    }
    activeReviewId.value = result.id
    contractStore.markReviewed(contractId)
    if (result.findings) {
      chatStore.clearMessages()
      chatStore.addMessage({
        review_id: result.id,
        role: 'assistant',
        content: `📋 **审核完成** — 综合评分 **${result.overall_score ?? '—'}** 分（${result.risk_level === 'high' ? '高风险' : result.risk_level === 'medium' ? '中风险' : '低风险'}）\n\n${result.summary || ''}\n\n点击右上角报告图标可查看逐条分析，也可以直接在下方输入框提问。`,
      })
    } else if (result.status === 'error') {
      message.error(result.summary || '审核失败，请重试')
    } else {
      message.warning('审核正在处理中，请稍候...')
      reviewStore.streamReview(result.id)
    }
  }

  async function onDeleteContract(id: number) {
    try {
      await contractStore.deleteContract(id)
      if (activeContractId.value === id) {
        activeContractId.value = null
        activeReviewId.value = null
        chatStore.clearMessages()
        reviewStore.currentReview = null
      }
      message.success('合同已删除')
    } catch (e: any) {
      message.error(e.message || '删除失败')
    }
  }

  return {
    activeContractId,
    activeReviewId,
    onSelectContract,
    onDeleteContract,
    startReview,
  }
}
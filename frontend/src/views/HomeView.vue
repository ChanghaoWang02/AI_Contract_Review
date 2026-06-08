<template>
  <div class="app-layout">
    <!-- 侧边栏 -->
    <Sidebar
      :contracts="contractStore.contracts"
      :active-id="activeContractId"
      :loading="contractStore.loading"
      @select="onSelectContract"
      @upload="onUploadClick"
      @delete="onDeleteContract"
    />

    <!-- 主内容区 -->
    <div class="main-area">
      <!-- 聊天面板 -->
      <ChatPanel
        :review-id="activeReviewId"
        :review-status="reviewStore.currentReview?.status"
        @send="onSendMessage"
      />

      <!-- 合同面板 (可收起) -->
      <transition name="slide">
        <ContractViewer
          v-if="showContractPanel"
          :contract="contractStore.currentContract"
          :findings="reviewStore.currentReview?.findings"
          @clause-click="onClauseClick"
          @close="showContractPanel = false"
        />
      </transition>
    </div>

    <!-- 上传弹窗 -->
    <UploadDialog
      v-model:show="showUpload"
      @uploaded="onUploaded"
    />

    <!-- 审核中遮罩 -->
    <n-modal v-model:show="reviewCreating" :mask-closable="false" :closable="false" style="width: 420px">
      <div class="loading-modal">
        <n-spin size="large" />
        <h3>AI 正在审核合同...</h3>
        <p>正在逐条分析条款风险，请稍候</p>
        <n-progress type="line" :percentage="100" :indicator-placement="'inside'" processing />
      </div>
    </n-modal>

    <!-- 审核报告弹窗 -->
    <n-modal v-model:show="showReport" style="width: 900px; max-width: 95vw">
      <ReviewReport
        v-if="reviewStore.currentReview?.findings"
        :findings="reviewStore.currentReview.findings"
        :risk-level="reviewStore.currentReview.risk_level"
        :overall-score="reviewStore.currentReview.overall_score || 0"
        :review-id="reviewStore.currentReview?.id ?? 0"
      />
      <div v-else class="loading-modal">
        <n-spin size="large" />
        <p>正在加载审核结果...</p>
      </div>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NModal, NSpin, NProgress, useMessage } from 'naive-ui'
import { useContractStore } from '@/stores/contract'
import { useReviewStore } from '@/stores/review'
import { useChatStore } from '@/stores/chat'
import Sidebar from '@/components/layout/Sidebar.vue'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import ContractViewer from '@/components/contract/ContractViewer.vue'
import UploadDialog from '@/components/contract/UploadDialog.vue'
import ReviewReport from '@/components/review/ReviewReport.vue'

const message = useMessage()
const contractStore = useContractStore()
const reviewStore = useReviewStore()
const chatStore = useChatStore()

const showUpload = ref(false)
const showContractPanel = ref(true)
const showReport = ref(false)
const reviewCreating = ref(false)
const activeContractId = ref<number | null>(null)
const activeReviewId = ref<number | null>(null)

onMounted(() => {
  contractStore.fetchContracts()
})

const onSelectContract = async (id: number) => {
  // 点击当前合同：不做任何操作，避免打断正在进行的 AI 流式回复
  if (id === activeContractId.value) return

  activeContractId.value = id
  showContractPanel.value = true
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
  } else {
    // 自动创建审核
    reviewCreating.value = true
    try {
      const review = await reviewStore.createReview(id)
      // createReview 可能返回 null 但 currentReview 已通过流设置
      const result = review || reviewStore.currentReview
      if (!result) {
        message.error('审核创建失败，请重试')
        return
      }
      // 使用服务器返回的真实 review_id（此前因 Bug 硬编码为 0，现已修复）
      const reviewId = result.id
      activeReviewId.value = reviewId
      if (result.findings) {
        showReport.value = true
        // 在聊天中注入审核摘要，让用户一眼看到结果
        chatStore.clearMessages()
        chatStore.addMessage({
          review_id: reviewId,
          role: 'assistant',
          content: `📋 **审核完成** — 综合评分 **${result.overall_score ?? '—'}** 分（${result.risk_level === 'high' ? '高风险' : result.risk_level === 'medium' ? '中风险' : '低风险'}）\n\n${result.summary || ''}\n\n点击右上角报告图标可查看逐条分析，也可以直接在下方输入框提问。`,
        })
      } else if (result.status === 'error') {
        message.error(result.summary || '审核失败，请重试')
      } else {
        message.warning('审核正在处理中，请稍候...')
        reviewStore.streamReview(reviewId)
      }
    } catch (e: any) {
      message.error(e.message || '审核创建失败')
    } finally {
      reviewCreating.value = false
    }
  }
}

const onUploadClick = () => {
  showUpload.value = true
}

const onUploaded = async (contract: any) => {
  showUpload.value = false
  message.success('合同上传成功，正在分析...')
  await onSelectContract(contract.id)
}

const onDeleteContract = async (id: number) => {
  try {
    await contractStore.deleteContract(id)
    if (activeContractId.value === id) {
      activeContractId.value = null
      activeReviewId.value = null
      chatStore.clearMessages()
      reviewStore.currentReview = null
      showContractPanel.value = false
    }
    message.success('合同已删除')
  } catch (e: any) {
    message.error(e.message || '删除失败')
  }
}

const onSendMessage = async (content: string) => {
  if (activeReviewId.value == null) return
  await chatStore.sendMessage(content, activeReviewId.value)
}

const onClauseClick = (clauseId: string, clauseText: string) => {
  chatStore.setAnchor(clauseId, clauseText)
}
</script>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: #f5f7fa;
}

.main-area {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}
.slide-enter-from,
.slide-leave-to {
  width: 0 !important;
  opacity: 0;
  transform: translateX(20px);
}

.loading-modal {
  text-align: center;
  padding: 40px 20px;
  background: #fff;
  border-radius: 8px;
}
.loading-modal h3 {
  margin: 16px 0 8px;
  color: #333;
}
.loading-modal p {
  color: #999;
  font-size: 14px;
}
</style>

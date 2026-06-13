<template>
  <div class="app-layout">
    <!-- 侧边栏 -->
    <Sidebar
      :contracts="contractStore.contracts"
      :active-id="contractSel.activeContractId.value"
      :loading="contractStore.loading"
      :disabled="reviewStore.isStreaming"
      @select="contractSel.onSelectContract"
      @upload="onUploadClick"
      @delete="contractSel.onDeleteContract"
      @review="onReviewClick"
      @translate="onTranslateClick"
      @compare="onCompareClick"
    />

    <!-- 主内容区 -->
    <div class="main-content">
      <div class="main-area">
        <!-- 翻译界面 -->
        <template v-if="mainView === 'translate'">
          <TranslatePanel
            :contract-id="contractSel.activeContractId.value"
            :contract-content="contractStore.currentContract?.content || ''"
            active-tab="translate"
            @saved="onTranslationSaved"
          />
        </template>

        <!-- 审核界面 -->
        <template v-else>
          <ChatPanel
            :review-id="contractSel.activeReviewId.value"
            :review-status="reviewStore.currentReview?.status"
            :contract-collapsed="!showContractPanel"
            @send="(content) => reviewFlow.onSendMessage(content, contractSel.activeReviewId.value!)"
            @expand-contract="showContractPanel = true"
          />

          <transition name="slide">
            <ContractViewer
              v-if="showContractPanel"
              :contract="contractStore.currentContract"
              :findings="reviewStore.currentReview?.findings"
              @clause-click="onClauseClick"
              @close="showContractPanel = false"
              @compare="onCompareClick"
            />
          </transition>
        </template>
      </div>
    </div>

    <!-- 上传弹窗 -->
    <UploadDialog
      v-model:show="showUpload"
      @uploaded="onUploaded"
    />

    <!-- 审核中遮罩 -->
    <n-modal v-model:show="reviewStore.isStreaming" :mask-closable="false" :closable="false" style="width: 420px">
      <div class="loading-modal">
        <n-spin size="large" />
        <h3>AI 正在审核合同...</h3>
        <p>正在逐条分析条款风险，请稍候</p>
      </div>
    </n-modal>

    <!-- 审核报告弹窗 -->
    <n-modal v-model:show="reviewFlow.showReport.value" style="width: 900px; max-width: 95vw">
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

    <!-- 对比上传弹窗 -->
    <CompareUploadDialog
      v-model:show="compareFlow.showCompareUpload.value"
      @confirm="compareFlow.onCompareConfirm"
    />

    <!-- 对比全屏弹窗 -->
    <CompareModal
      ref="compareModalRef"
      :show="compareFlow.showCompare.value"
      :contract="contractStore.currentContract"
      @update:show="compareFlow.showCompare.value = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NModal, NSpin, useMessage } from 'naive-ui'
import { useContractStore } from '@/stores/contract'
import { useReviewStore } from '@/stores/review'
import { useChatStore } from '@/stores/chat'
import Sidebar from '@/components/layout/Sidebar.vue'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import ContractViewer from '@/components/contract/ContractViewer.vue'
import UploadDialog from '@/components/contract/UploadDialog.vue'
import CompareUploadDialog from '@/components/contract/CompareUploadDialog.vue'
import CompareModal from '@/components/compare/CompareModal.vue'
import ReviewReport from '@/components/review/ReviewReport.vue'
import TranslatePanel from '@/components/translate/TranslatePanel.vue'

import { useContractSelection } from '@/composables/useContractSelection'
import { useReviewFlow } from '@/composables/useReviewFlow'
import { useCompareFlow } from '@/composables/useCompareFlow'

const message = useMessage()
const route = useRoute()
const router = useRouter()
const contractStore = useContractStore()
const reviewStore = useReviewStore()
const chatStore = useChatStore()

// 主视图状态：'review' | 'translate'
const mainView = ref<'review' | 'translate'>('review')
const showContractPanel = ref(true)

// Composable 实例
const contractSel = useContractSelection()
const reviewFlow = useReviewFlow()
const compareModalRef = ref<InstanceType<typeof CompareModal> | null>(null)
const compareFlow = useCompareFlow(compareModalRef)

const showUpload = ref(false)

onMounted(async () => {
  await contractStore.fetchContracts()
  const reviewContractId = route.query.review_contract
  if (reviewContractId) {
    const id = Number(reviewContractId)
    if (!isNaN(id)) {
      router.replace({ path: '/', query: {} })
      await contractSel.onSelectContract(id, true)
    }
  }
})

function onReviewClick() {
  mainView.value = 'review'
  const id = contractSel.activeContractId.value
  if (id) {
    contractSel.onSelectContract(id)
  }
}

function onTranslateClick() {
  mainView.value = 'translate'
}

function onCompareClick() {
  if (!contractSel.activeContractId.value) {
    message.warning('请先选择一份合同')
    return
  }
  compareFlow.showCompareUpload.value = true
}

function onUploadClick() {
  showUpload.value = true
}

async function onUploaded(contract: any) {
  showUpload.value = false
  mainView.value = 'review'
  message.success('合同上传成功，正在分析...')
  await contractSel.onSelectContract(contract.id)
}

function onClauseClick(clauseId: string, clauseText: string) {
  chatStore.setAnchor(clauseId, clauseText)
}

function onTranslationSaved(_childId: number) {
  message.success('译文已保存')
  contractStore.fetchContracts()
}
</script>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: #f5f7fa;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
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
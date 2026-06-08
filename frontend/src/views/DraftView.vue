<template>
  <div class="draft-page">
    <!-- 顶部栏 -->
    <div class="draft-header">
      <n-button text @click="goBack">
        <n-icon><arrow-back-outline /></n-icon>
        返回
      </n-button>
      <h2>合同起草</h2>
    </div>

    <!-- 步骤指示器 -->
    <n-steps :current="draft.currentStep" class="steps-bar">
      <n-step title="选类型" />
      <n-step title="填信息" />
      <n-step title="AI 生成" />
      <n-step title="预览编辑" />
      <n-step title="保存" />
    </n-steps>

    <!-- 步骤内容 -->
    <div class="step-content">
      <TypeSelector v-if="draft.currentStep === 0" />
      <InfoForm v-else-if="draft.currentStep === 1" />
      <GenerateView v-else-if="draft.currentStep === 2" />
      <EditView v-else-if="draft.currentStep === 3" />
      <SaveView v-else-if="draft.currentStep === 4" />
    </div>

    <!-- 草稿恢复弹窗 -->
    <n-modal v-model:show="showDraftRecovery" :closable="false" :mask-closable="false">
      <div class="recovery-modal">
        <h3>检测到未完成的草稿</h3>
        <p>是否继续上次的起草？</p>
        <div class="recovery-actions">
          <n-button @click="discardDraft">丢弃，重新开始</n-button>
          <n-button type="primary" @click="continueDraft">继续起草</n-button>
        </div>
      </div>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { NButton, NIcon, NSteps, NStep, NModal, useDialog } from 'naive-ui'
import { ArrowBackOutline } from '@vicons/ionicons5'
import { useDraftStore } from '@/stores/draft'
import TypeSelector from '@/components/draft/TypeSelector.vue'
import InfoForm from '@/components/draft/InfoForm.vue'
import GenerateView from '@/components/draft/GenerateView.vue'
import EditView from '@/components/draft/EditView.vue'
import SaveView from '@/components/draft/SaveView.vue'

const router = useRouter()
const draft = useDraftStore()
const dialog = useDialog()
const showDraftRecovery = ref(false)

onMounted(() => {
  if (draft.loadFromLocalStorage()) {
    showDraftRecovery.value = true
  }
})

function continueDraft() {
  showDraftRecovery.value = false
}

function discardDraft() {
  draft.clearLocalStorage()
  draft.clearDraft()
  showDraftRecovery.value = false
}

function goBack() {
  if (draft.currentStep >= 2 && draft.hasDraft) {
    // 展示离开确认（通过 onBeforeRouteLeave 处理）
  }
  router.push('/')
}

// 导航守卫
onBeforeRouteLeave((_to, _from, next) => {
  if (draft.currentStep >= 2 && draft.hasDraft) {
    dialog.warning({
      title: '正在起草中，离开将丢失进度',
      positiveText: '保存草稿',
      negativeText: '直接清除',
      closable: true,
      onPositiveClick: () => {
        draft.saveToLocalStorage()
        draft.clearDraft()
        next()
      },
      onNegativeClick: () => {
        draft.clearLocalStorage()
        draft.clearDraft()
        next()
      },
      onClose: () => {
        next(false)  // 取消导航
      },
    })
  } else {
    next()
  }
})
</script>

<style scoped>
.draft-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}
.draft-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.draft-header h2 { margin: 0; }
.steps-bar { margin-bottom: 24px; }
.step-content { min-height: 400px; }
.recovery-modal {
  padding: 24px;
  background: #fff;
  border-radius: 8px;
  text-align: center;
}
.recovery-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 16px;
}
</style>

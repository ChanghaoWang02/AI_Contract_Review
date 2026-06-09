<template>
  <n-modal
    :show="show"
    @update:show="$emit('update:show', $event)"
    title="合同对比"
    style="width: 480px"
  >
    <div class="compare-dialog">
      <p class="dialog-desc">上传新版合同文件，选择分析视角</p>

      <n-upload
        :accept="'.pdf,.docx,.doc,.txt'"
        :max-file-size-mb="10"
        :show-file-list="true"
        :custom-request="customUpload"
        @error="onUploadError"
      >
        <n-upload-dragger>
          <div class="upload-area">
            <n-icon size="36"><cloud-upload-outline /></n-icon>
            <p class="upload-title">点击或拖拽新版合同文件</p>
            <p class="upload-hint">支持 PDF、DOCX、TXT，最大 10MB</p>
          </div>
        </n-upload-dragger>
      </n-upload>

      <div v-if="selectedFile" class="perspective-section">
        <n-divider />
        <p class="section-label">分析视角</p>
        <n-radio-group v-model:value="perspective">
          <n-space>
            <n-radio value="party_a">甲方</n-radio>
            <n-radio value="party_b">乙方</n-radio>
            <n-radio value="neutral">中立</n-radio>
          </n-space>
        </n-radio-group>
        <p class="perspective-hint">
          {{ perspectiveHint }}
        </p>
      </div>

      <div class="dialog-actions">
        <n-button @click="$emit('update:show', false)">取消</n-button>
        <n-button
          type="primary"
          :disabled="!selectedFile"
          :loading="uploading"
          @click="onConfirm"
        >
          开始对比
        </n-button>
      </div>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  NModal, NUpload, NUploadDragger, NIcon, NButton,
  NDivider, NRadioGroup, NRadio, NSpace, useMessage,
} from 'naive-ui'
import { CloudUploadOutline } from '@vicons/ionicons5'
import type { UploadCustomRequestOptions } from 'naive-ui'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  confirm: [file: File, perspective: string]
}>()

const message = useMessage()
const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const perspective = ref('neutral')

const perspectiveHint = computed(() => {
  switch (perspective.value) {
    case 'party_a': return '甲方：合同中先出现的角色方（出租方/卖方/用人单位/委托方等）'
    case 'party_b': return '乙方：合同中后出现的角色方（承租方/买方/劳动者/服务方等）'
    case 'neutral': return '中立：不偏向任一方，仅分析变更的客观影响'
  }
})

// 每次打开弹窗时重置状态
watch(() => props.show, (val) => {
  if (val) {
    selectedFile.value = null
    uploading.value = false
  }
})

function customUpload({ file, onFinish }: UploadCustomRequestOptions) {
  if (file.file) {
    selectedFile.value = file.file
    onFinish()
  }
}

function onUploadError() {
  message.error('文件上传失败')
}

function onConfirm() {
  if (!selectedFile.value) return
  uploading.value = true
  emit('confirm', selectedFile.value, perspective.value)
  // uploading reset by parent after SSE starts
}
</script>

<style scoped>
.compare-dialog {
  padding: 24px;
  background: #fff;
  border-radius: 8px;
}
.dialog-desc {
  margin: 0 0 16px;
  color: #666;
  font-size: 14px;
}
.upload-area {
  text-align: center;
  padding: 24px 16px;
}
.upload-title {
  font-size: 15px;
  color: #333;
  margin: 12px 0 4px;
}
.upload-hint {
  font-size: 13px;
  color: #999;
  margin: 0;
}
.perspective-section {
  margin-top: 4px;
}
.section-label {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}
.perspective-hint {
  font-size: 12px;
  color: #999;
  margin: 8px 0 0;
}
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
</style>

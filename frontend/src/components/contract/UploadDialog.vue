<template>
  <n-modal
    :show="show"
    @update:show="$emit('update:show', $event)"
    title="上传合同"
    style="width: 480px"
  >
    <div class="upload-dialog">
      <n-upload
        :accept="'.pdf,.docx,.doc,.txt'"
        :max-file-size-mb="20"
        :show-file-list="true"
        :custom-request="customUpload"
        @error="onError"
      >
        <n-upload-dragger>
          <div class="upload-area">
            <n-icon size="40"><cloud-upload-outline /></n-icon>
            <p class="upload-title">点击或拖拽文件到此处</p>
            <p class="upload-hint">支持 PDF、DOCX、TXT，最大 20MB</p>
          </div>
        </n-upload-dragger>
      </n-upload>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { NModal, NUpload, NUploadDragger, NIcon } from 'naive-ui'
import { CloudUploadOutline } from '@vicons/ionicons5'
import { useContractStore } from '@/stores/contract'
import type { UploadCustomRequestOptions } from 'naive-ui'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  uploaded: [contract: any]
}>()

const contractStore = useContractStore()

async function customUpload({ file, onFinish, onError }: UploadCustomRequestOptions) {
  try {
    const contract = await contractStore.uploadContract(file.file!)
    onFinish()
    emit('uploaded', contract)
  } catch (e: any) {
    onError()
  }
}

function onError() {
  // 错误由 store 处理
}
</script>

<style scoped>
.upload-dialog {
  padding: 24px;
  background: #fff;
  border-radius: 8px;
}

.upload-area {
  text-align: center;
  padding: 32px 16px;
}

.upload-title {
  font-size: 16px;
  color: #333;
  margin: 12px 0 4px;
}

.upload-hint {
  font-size: 13px;
  color: #999;
  margin: 0;
}
</style>

/**
 * 对比流程 composable
 */
import { ref } from 'vue'

interface CompareModalHandle {
  startCompare(file: File, perspective: string): Promise<void>
}

export function useCompareFlow(compareModalRef: { value: CompareModalHandle | null }) {
  const showCompareUpload = ref(false)
  const showCompare = ref(false)

  function onCompareClick() {
    showCompareUpload.value = true
  }

  function onCompareConfirm(file: File, perspective: string) {
    showCompareUpload.value = false
    showCompare.value = true
    setTimeout(() => {
      compareModalRef.value?.startCompare(file, perspective)
    }, 100)
  }

  return {
    showCompareUpload,
    showCompare,
    onCompareClick,
    onCompareConfirm,
  }
}
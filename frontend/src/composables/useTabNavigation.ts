/**
 * Tab 切换逻辑 composable
 */
import { reactive } from 'vue'
import { useMessage } from 'naive-ui'
import { useTranslateStore } from '@/stores/translate'

export function useTabNavigation() {
  const state = reactive({
    activeTab: 'review' as 'review' | 'translate' | 'compare',
    showContractPanel: true,
  })
  const message = useMessage()
  const translateStore = useTranslateStore()

  function switchTab(tab: 'review' | 'translate' | 'compare') {
    // 对比 Tab 由 HomeView 单独处理（handleTabClick 直接打开上传弹窗，不走此函数）
    if (tab === 'compare') return

    state.activeTab = tab
    // 翻译 Tab 激活时自动折叠合同面板
    if (tab === 'translate') {
      state.showContractPanel = false
    }
    // 清理翻译状态
    if (tab !== 'translate') {
      translateStore.reset()
    }
  }

  function requestShowContractPanel() {
    state.showContractPanel = true
  }

  return {
    state,
    switchTab,
    requestShowContractPanel,
  }
}
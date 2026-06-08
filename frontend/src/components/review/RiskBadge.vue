<template>
  <n-tag :type="tagType" :size="size" :bordered="false">
    {{ label }}
  </n-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NTag } from 'naive-ui'

const props = withDefaults(defineProps<{
  level: string
  size?: 'small' | 'medium' | 'large'
}>(), {
  size: 'small',
})

const tagType = computed(() => {
  switch (props.level) {
    case 'high': return 'error'
    case 'medium': return 'warning'
    case 'low': return 'success'
    default: return 'default'
  }
})

const label = computed(() => {
  switch (props.level) {
    case 'high': return '高风险'
    case 'medium': return '中风险'
    case 'low': return '低风险'
    default: return props.level
  }
})
</script>

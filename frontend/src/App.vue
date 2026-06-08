<template>
  <n-config-provider :locale="zhCN" :theme="theme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { NConfigProvider, NMessageProvider, NDialogProvider, darkTheme } from 'naive-ui'
import { zhCN } from 'naive-ui'

const theme = ref(null) // null = 自动跟随系统

const themeOverrides = {
  common: {
    primaryColor: '#4C6EF5',
    primaryColorHover: '#3B5BDB',
    borderRadius: '8px',
  },
}
</script>

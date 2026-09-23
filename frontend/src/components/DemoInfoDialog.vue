<script setup lang="ts">
import { demoConfig } from '../demo/config'
import ModalFrame from './ModalFrame.vue'
defineEmits<{ close: [] }>()
const labels: Record<keyof typeof demoConfig, string> = { mode: '演示范围', ranking: '排行榜', recommendation: '推荐顺序', replies: '交流与商家回复', session: '会话状态', purchase: '模拟购买', privacy: '信息可见范围' }
</script>
<template>
  <ModalFrame title="演示配置说明" @close="$emit('close')"><div class="modal-body"><span class="demo-badge">暂定、可修改 · 非正式实验算法</span><dl class="config-list"><div v-for="(value, key) in demoConfig" :key="key"><dt>{{ labels[key] }}</dt><dd>{{ value }}</dd></div></dl><p class="dialog-small-note">此版验证买方操作流程；未接入实验核心、模型或真实支付。</p></div><template #actions><button class="btn primary" @click="$emit('close')">知道了</button></template></ModalFrame>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import Icon from './Icon.vue'
const props = withDefaults(defineProps<{ title: string; busy?: boolean }>(), { busy: false })
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
onMounted(() => dialog.value?.showModal())
onUnmounted(() => dialog.value?.close())
function close() { if (!props.busy) emit('close') }
function backdrop(event: MouseEvent) {
  if (event.target !== dialog.value) return
  const box = dialog.value!.getBoundingClientRect()
  if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) close()
}
</script>
<template>
  <dialog ref="dialog" aria-labelledby="modal-title" :aria-busy="busy" @cancel.prevent="close" @click="backdrop">
    <div class="modal-head"><h2 id="modal-title">{{ title }}</h2><button type="button" class="close-btn" aria-label="关闭弹窗" :disabled="busy" @click="close"><Icon name="close" /></button></div>
    <slot /><div v-if="$slots.actions" class="modal-actions"><slot name="actions" /></div>
  </dialog>
</template>

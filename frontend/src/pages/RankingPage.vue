<script setup lang="ts">
import { computed } from 'vue'
import type { LeaderboardRow, Page } from '../domain/types'
import { amount } from '../domain/format'
import Icon from '../components/Icon.vue'
import MerchantAvatar from '../components/MerchantAvatar.vue'
import PageHeader from '../components/PageHeader.vue'
import Notice from '../components/Notice.vue'
const props = defineProps<{ rows: LeaderboardRow[] }>()
defineEmits<{ navigate: [page: Page, merchantId?: string]; info: [] }>()
const podium = computed(() => [props.rows[1], props.rows[0], ...props.rows.slice(2)].filter((row): row is LeaderboardRow => !!row))
</script>
<template>
  <PageHeader title="看看商家们的表现" subtitle="浏览排名，发现商品，也可以先聊聊再决定。" @info="$emit('info')" />
  <Notice>演示榜单 · 按模拟累计成交额排序，含预置数据；购买后同步更新。</Notice>
  <div class="standings">
    <article v-for="m in podium" :key="m.id" class="standing" :class="{ first: m.rank === 1 }">
      <span class="position">0{{ m.rank }}</span><template v-if="m.rank === 1"><div class="medal-label">当前领先</div><br /></template>
      <MerchantAvatar :merchant="m" /><h3>{{ m.name }}</h3><div class="subline">{{ m.tag }}</div><div class="rank-label">模拟累计成交额</div><div class="money">¥ {{ amount(m.revenueCents) }}</div><div class="subline">已成交 {{ m.sold }} 件</div>
      <button type="button" class="btn" :class="{ primary: m.rank === 1 }" @click="$emit('navigate', 'products', m.id)">逛逛这家 <Icon name="arrow" /></button>
    </article>
  </div>
  <div class="section-title"><h2>商家一览</h2><span>{{ rows.length }} 家商家 · 排名向买家公开</span></div>
  <div class="panel table-wrap"><table><thead><tr><th>排名</th><th>商家</th><th>模拟成交额</th><th>成交件数</th><th>了解商家</th></tr></thead><tbody>
    <tr v-for="m in rows" :key="m.id"><td><span class="rank-num">0{{ m.rank }}</span></td><td><div class="seller-cell"><MerchantAvatar :merchant="m" /><div><strong>{{ m.name }}</strong><small>{{ m.tag }}</small></div></div></td><td><strong>¥ {{ amount(m.revenueCents) }}</strong></td><td>{{ m.sold }} 件</td><td><div class="row-actions"><button class="text-btn" @click="$emit('navigate', 'public', m.id)">公开交流</button><button class="text-btn" @click="$emit('navigate', 'private', m.id)">私聊商家</button></div></td></tr>
  </tbody></table></div>
  <div class="rank-footer"><span>排名只代表当前演示成交情况。按自己的需要选择，随时可以不购买。</span><button class="btn soft" @click="$emit('navigate', 'products')">浏览全部商品 <Icon name="arrow" /></button></div>
</template>

<script setup lang="ts">
import type { LeaderboardSnapshot } from '../platform/types'
defineProps<{ snapshot: LeaderboardSnapshot | null }>()
</script>
<template>
  <div class="notice" data-testid="leaderboard-context" :data-snapshot-id="snapshot?.leaderboard_snapshot_id">
    <template v-if="snapshot">
      <strong>利润（开发口径） · Development Metric</strong>
      <div>{{ snapshot.source_publication_version === 0 ? '初始榜单' : `截至 Round ${snapshot.round_index} / Tick ${snapshot.tick_index}` }} · 榜单来源 Publication {{ snapshot.source_publication_version }} · {{ snapshot.refresh_policy === 'tick_close' ? '每个完整市场 Tick 后更新' : '每个完整 Round 后更新' }}</div>
      <small>累计销售收入 − 累计采购支出；未售库存不计价值。同利润按 Seller ID 稳定展示，不代表更优。不影响商品推荐顺序，也不是最终 benchmark 指标。</small>
    </template>
    <template v-else>此历史场次未启用开发利润榜单；不会补造此前未发布的排名。</template>
  </div>
</template>
<style scoped>
.notice { display: block; }
.notice > div { margin: 3px 0; }
small { display: block; }
</style>

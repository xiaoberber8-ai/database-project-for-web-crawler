<template>
  <div class="dashboard-page">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-item" style="background: linear-gradient(135deg, #409EFF, #66b1ff);">
            <el-icon :size="40" color="#fff"><Document /></el-icon>
            <div class="stat-info">
              <div class="stat-number">{{ stats.webpageCount }}</div>
              <div class="stat-label">爬取网页数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-item" style="background: linear-gradient(135deg, #67C23A, #85ce61);">
            <el-icon :size="40" color="#fff"><Notebook /></el-icon>
            <div class="stat-info">
              <div class="stat-number">{{ stats.contentCount }}</div>
              <div class="stat-label">文本内容数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-item" style="background: linear-gradient(135deg, #E6A23C, #ebb563);">
            <el-icon :size="40" color="#fff"><Picture /></el-icon>
            <div class="stat-info">
              <div class="stat-number">{{ stats.imageCount }}</div>
              <div class="stat-label">图片数量</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-item" style="background: linear-gradient(135deg, #F56C6C, #f78989);">
            <el-icon :size="40" color="#fff"><Connection /></el-icon>
            <div class="stat-info">
              <div class="stat-number">{{ stats.taskCount }}</div>
              <div class="stat-label">任务总数</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 当前任务指标 -->
    <el-row :gutter="16" class="stat-row" style="margin-top: 16px;">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>当前任务指标</span>
              <el-tag v-if="crawlStatus.thread_alive" type="warning" effect="dark" size="small">
                <el-icon style="vertical-align: middle;"><Loading /></el-icon>
                实时更新中
              </el-tag>
              <el-tag v-else type="info" size="small">无运行中任务</el-tag>
            </div>
          </template>
          <el-row :gutter="16">
            <el-col :span="6">
              <div class="current-stat" style="border-left: 4px solid #409EFF;">
                <div class="current-stat-label">当前任务网页数</div>
                <div class="current-stat-value">{{ currentTaskStats.webpages }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="current-stat" style="border-left: 4px solid #67C23A;">
                <div class="current-stat-label">当前任务文本数</div>
                <div class="current-stat-value">{{ currentTaskStats.contents }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="current-stat" style="border-left: 4px solid #E6A23C;">
                <div class="current-stat-label">当前任务图片数</div>
                <div class="current-stat-value">{{ currentTaskStats.images }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="current-stat" style="border-left: 4px solid #F56C6C;">
                <div class="current-stat-label">当前任务抓取条目</div>
                <div class="current-stat-value">{{ currentTaskStats.items }}</div>
              </div>
            </el-col>
          </el-row>
          <el-row :gutter="16" style="margin-top: 12px;" v-if="crawlStatus.thread_alive && currentTask">
            <el-col :span="24">
              <el-descriptions :column="4" size="small" border>
                <el-descriptions-item label="任务ID">{{ currentTask.id }}</el-descriptions-item>
                <el-descriptions-item label="策略ID">{{ currentTask.strategy_id }}</el-descriptions-item>
                <el-descriptions-item label="开始时间">{{ formatTime(currentTask.start_time) }}</el-descriptions-item>
                <el-descriptions-item label="运行时长">{{ currentTaskDuration }}</el-descriptions-item>
              </el-descriptions>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px;">
      <!-- 最近任务 -->
      <el-col :span="14">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>最近任务</span>
              <el-button text type="primary" @click="$router.push('/crawler')">查看全部</el-button>
            </div>
          </template>
          <el-table :data="recentTasks" stripe style="width: 100%">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="strategy_id" label="策略ID" width="80" />
            <el-table-column prop="Status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getTaskStatusType(row)">{{ getTaskStatusText(row) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="item_count" label="抓取条目" width="100" />
            <el-table-column prop="start_time" label="开始时间">
              <template #default="{ row }">{{ formatTime(row.start_time) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 爬虫状态 + 策略概览 -->
      <el-col :span="10">
        <el-card shadow="hover" style="margin-bottom: 16px;">
          <template #header><span>爬虫运行状态</span></template>
          <div class="status-display">
            <div class="status-dot" :class="{ active: crawlStatus.thread_alive }"></div>
            <span class="status-text">{{ crawlStatus.thread_alive ? '运行中' : '未运行' }}</span>
            <div style="margin-top: 12px;">
              <el-descriptions :column="1" size="small" border>
                <el-descriptions-item label="线程状态">{{ crawlStatus.thread_alive ? '活跃' : '空闲' }}</el-descriptions-item>
                <el-descriptions-item label="暂停">{{ crawlStatus.paused ? '是' : '否' }}</el-descriptions-item>
                <el-descriptions-item label="停止">{{ crawlStatus.stopped ? '是' : '否' }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </div>
        </el-card>

        <el-card shadow="hover">
          <template #header><span>策略概览</span></template>
          <div v-for="s in strategies.slice(0, 5)" :key="s.id" class="strategy-item">
            <div class="strategy-name">{{ s.name }}</div>
            <el-tag size="small" :type="s.Status === 'enabled' ? 'success' : 'info'">{{ s.Status === 'enabled' ? '启用' : '禁用' }}</el-tag>
          </div>
          <el-empty v-if="strategies.length === 0" description="暂无策略" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { getStrategies, getCrawlStatus, getTasks, getWebpages, getContents, getImages } from '../api'
import { Loading } from '@element-plus/icons-vue'

const stats = reactive({
  webpageCount: 0,
  contentCount: 0,
  imageCount: 0,
  taskCount: 0
})
const recentTasks = ref([])
const strategies = ref([])
const crawlStatus = ref({ thread_alive: false, paused: false, stopped: false })
const currentTask = ref(null)
const currentTaskStats = reactive({
  webpages: 0,
  contents: 0,
  images: 0,
  items: 0
})
const now = ref(Date.now())
let timer = null
let statsTimer = null

const formatTime = (t) => {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

// 运行时长计算
const currentTaskDuration = computed(() => {
  if (!currentTask.value?.start_time) return '-'
  const start = new Date(currentTask.value.start_time).getTime()
  const diff = Math.floor((now.value - start) / 1000)
  if (diff < 60) return `${diff}秒`
  if (diff < 3600) return `${Math.floor(diff / 60)}分${diff % 60}秒`
  return `${Math.floor(diff / 3600)}时${Math.floor((diff % 3600) / 60)}分`
})

const statusType = (s) => ({ running: 'warning', completed: 'success', pending: 'info', failed: 'danger', cancelled: 'info', interrupted: 'danger' }[s] || 'info')
const statusText = (s) => ({ running: '运行中', completed: '已完成', pending: '等待中', failed: '失败', cancelled: '已取消', interrupted: '已中断' }[s] || s)

// 修正任务状态：如果任务记录是running但线程已死，则显示为"已结束"
const getTaskStatus = (task) => {
  if (task.Status === 'running' && !crawlStatus.value.thread_alive) {
    return 'completed'
  }
  return task.Status
}
const getTaskStatusType = (task) => statusType(getTaskStatus(task))
const getTaskStatusText = (task) => statusText(getTaskStatus(task))

const loadStats = async () => {
  try {
    const [webpages, contents, images, tasks] = await Promise.all([
      getWebpages(),
      getContents(),
      getImages(),
      getTasks()
    ])
    stats.webpageCount = webpages.length
    stats.contentCount = contents.length
    stats.imageCount = images.length
    stats.taskCount = tasks.length
    recentTasks.value = tasks.slice(0, 5)

    // 查找当前运行中的任务
    const running = tasks.find(t => t.Status === 'running')
    if (running && crawlStatus.value.thread_alive) {
      currentTask.value = running
      // 统计当前任务的数据量
      const taskId = running.id
      // content 和 image 表没有 task_id 字段，需要通过 webpage_id 关联
      const taskWebpageIds = new Set(
        webpages.filter(w => w.task_id === taskId).map(w => w.id)
      )
      currentTaskStats.webpages = taskWebpageIds.size
      currentTaskStats.contents = contents.filter(c => taskWebpageIds.has(c.webpage_id)).length
      currentTaskStats.images = images.filter(i => taskWebpageIds.has(i.webpage_id)).length
      currentTaskStats.items = running.item_count || 0
    } else {
      currentTask.value = null
      currentTaskStats.webpages = 0
      currentTaskStats.contents = 0
      currentTaskStats.images = 0
      currentTaskStats.items = 0
    }
  } catch {}
}

const refreshStatus = async () => {
  try {
    crawlStatus.value = await getCrawlStatus()
    // 爬虫运行时同时刷新统计数据
    if (crawlStatus.value.thread_alive) {
      await loadStats()
    }
  } catch {}
}

onMounted(async () => {
  try { strategies.value = await getStrategies() } catch {}
  loadStats()
  refreshStatus()
  // 每3秒刷新爬虫状态和统计数据
  timer = setInterval(() => {
    refreshStatus()
  }, 3000)
  // 每1秒更新运行时长
  statsTimer = setInterval(() => {
    now.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (statsTimer) clearInterval(statsTimer)
})
</script>

<style scoped>
.stat-row {
  margin-bottom: 0;
}
.stat-card {
  border: none;
}
.stat-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-radius: 8px;
  color: #fff;
}
.stat-number {
  font-size: 28px;
  font-weight: bold;
}
.stat-label {
  font-size: 13px;
  opacity: 0.9;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.status-display {
  text-align: center;
}
.status-dot {
  display: inline-block;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #909399;
  margin-right: 8px;
  vertical-align: middle;
}
.status-dot.active {
  background: #67C23A;
  box-shadow: 0 0 8px rgba(103, 194, 58, 0.6);
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.status-text {
  font-size: 18px;
  font-weight: bold;
  vertical-align: middle;
}
.strategy-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.strategy-item:last-child {
  border-bottom: none;
}
.strategy-name {
  font-size: 14px;
  color: #303133;
}
.current-stat {
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
}
.current-stat-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 4px;
}
.current-stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}
</style>

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
              <el-tag v-if="crawlStatus.thread_alive && currentTask && currentTask.Status === 'running'" type="warning" effect="dark" size="small">
                <el-icon style="vertical-align: middle;"><Loading /></el-icon>
                实时更新中
              </el-tag>
              <el-tag v-else-if="currentTask && currentTask.Status === 'completed'" type="success" size="small">
                任务已完成
              </el-tag>
              <el-tag v-else-if="currentTask && currentTask.Status === 'failed'" type="danger" size="small">
                任务失败
              </el-tag>
              <el-tag v-else-if="currentTask" type="info" size="small">
                {{ currentTask.Status }}
              </el-tag>
              <el-tag v-else type="info" size="small">无任务记录</el-tag>
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
          <el-row :gutter="16" style="margin-top: 12px;" v-if="currentTask">
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

    <!-- 爬虫运行状态（含蜘蛛动画） -->
    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>爬虫运行状态</span>
              <el-tag v-if="crawlStatus.thread_alive" type="success" effect="dark" size="small">
                <el-icon style="vertical-align: middle;"><Loading /></el-icon>
                运行中
              </el-tag>
              <el-tag v-else type="info" size="small">未运行</el-tag>
            </div>
          </template>

          <!-- 运行中：展示蜘蛛搬运数据动画 -->
          <div v-if="crawlStatus.thread_alive" class="status-running-block">
            <SpiderAnimation />
            <el-row :gutter="16" style="margin-top: 12px;">
              <el-col :span="8">
                <div class="status-mini-stat">
                  <div class="status-mini-label">线程状态</div>
                  <div class="status-mini-value text-success">活跃</div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="status-mini-stat">
                  <div class="status-mini-label">暂停</div>
                  <div class="status-mini-value">{{ crawlStatus.paused ? '是' : '否' }}</div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="status-mini-stat">
                  <div class="status-mini-label">停止</div>
                  <div class="status-mini-value">{{ crawlStatus.stopped ? '是' : '否' }}</div>
                </div>
              </el-col>
            </el-row>
          </div>

          <!-- 未运行：展示睡觉的小蜘蛛 -->
          <div v-else class="status-running-block">
            <SpiderAnimation sleeping />
            <el-row :gutter="16" style="margin-top: 12px;">
              <el-col :span="8">
                <div class="status-mini-stat">
                  <div class="status-mini-label">线程状态</div>
                  <div class="status-mini-value">空闲</div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="status-mini-stat">
                  <div class="status-mini-label">暂停</div>
                  <div class="status-mini-value">否</div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="status-mini-stat">
                  <div class="status-mini-label">停止</div>
                  <div class="status-mini-value">否</div>
                </div>
              </el-col>
            </el-row>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近任务 -->
    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>最近任务</span>
              <el-button text type="primary" @click="$router.push('/crawler')">查看全部</el-button>
            </div>
          </template>
          <el-table :data="recentTasks" stripe style="width: 100%">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="strategy_id" label="策略ID" width="100" />
            <el-table-column prop="Status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="getTaskStatusType(row)">{{ getTaskStatusText(row) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="item_count" label="抓取条目" width="120" />
            <el-table-column prop="start_time" label="开始时间">
              <template #default="{ row }">{{ formatTime(row.start_time) }}</template>
            </el-table-column>
            <el-table-column prop="end_time" label="结束时间">
              <template #default="{ row }">{{ formatTime(row.end_time) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { getCrawlStatus, getTasks, getWebpages, getContents, getImages } from '../api'
import { Loading } from '@element-plus/icons-vue'
import SpiderAnimation from '../components/SpiderAnimation.vue'

const stats = reactive({
  webpageCount: 0,
  contentCount: 0,
  imageCount: 0,
  taskCount: 0
})
const recentTasks = ref([])
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
      // 任务运行中：实时更新指标
      currentTask.value = running
      const taskId = running.id
      const taskWebpageIds = new Set(
        webpages.filter(w => w.task_id === taskId).map(w => w.id)
      )
      currentTaskStats.webpages = taskWebpageIds.size
      currentTaskStats.contents = contents.filter(c => taskWebpageIds.has(c.webpage_id)).length
      currentTaskStats.images = images.filter(i => taskWebpageIds.has(i.webpage_id)).length
      currentTaskStats.items = running.item_count || 0
    } else if (currentTask.value) {
      // 任务刚结束：做最后一次刷新，保留最终指标（图片此时已全部入库）
      const finishedTask = tasks.find(t => t.id === currentTask.value.id)
      if (finishedTask && finishedTask.Status !== 'running') {
        currentTask.value = finishedTask
        const taskId = finishedTask.id
        const taskWebpageIds = new Set(
          webpages.filter(w => w.task_id === taskId).map(w => w.id)
        )
        currentTaskStats.webpages = taskWebpageIds.size
        currentTaskStats.contents = contents.filter(c => taskWebpageIds.has(c.webpage_id)).length
        currentTaskStats.images = images.filter(i => taskWebpageIds.has(i.webpage_id)).length
        currentTaskStats.items = finishedTask.item_count || 0
      }
    } else {
      // 无任务记录：显示最近完成的任务指标
      const latestFinished = tasks.find(t => t.Status !== 'running')
      if (latestFinished) {
        currentTask.value = latestFinished
        const taskId = latestFinished.id
        const taskWebpageIds = new Set(
          webpages.filter(w => w.task_id === taskId).map(w => w.id)
        )
        currentTaskStats.webpages = taskWebpageIds.size
        currentTaskStats.contents = contents.filter(c => taskWebpageIds.has(c.webpage_id)).length
        currentTaskStats.images = images.filter(i => taskWebpageIds.has(i.webpage_id)).length
        currentTaskStats.items = latestFinished.item_count || 0
      }
    }
  } catch {}
}

const refreshStatus = async () => {
  try {
    const prevThreadAlive = crawlStatus.value?.thread_alive
    crawlStatus.value = await getCrawlStatus()
    // 爬虫运行时持续刷新统计数据
    if (crawlStatus.value.thread_alive) {
      await loadStats()
    } else if (prevThreadAlive) {
      // 爬虫刚结束：做最后一次刷新，确保图片等慢入库数据被正确统计
      await loadStats()
    }
  } catch {}
}

onMounted(async () => {
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
.status-text {
  font-size: 18px;
  font-weight: bold;
  vertical-align: middle;
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
.status-running-block {
  text-align: left;
}
.status-mini-stat {
  padding: 10px 14px;
  background: #f5f7fa;
  border-radius: 4px;
  text-align: center;
}
.status-mini-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.status-mini-value {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}
.text-success {
  color: #67C23A;
}
</style>

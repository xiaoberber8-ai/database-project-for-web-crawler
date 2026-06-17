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
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { getStrategies, getCrawlStatus, getTasks, getWebpages, getContents, getImages } from '../api'

const stats = reactive({
  webpageCount: 0,
  contentCount: 0,
  imageCount: 0,
  taskCount: 0
})
const recentTasks = ref([])
const strategies = ref([])
const crawlStatus = ref({ thread_alive: false, paused: false, stopped: false })
let timer = null

const formatTime = (t) => {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

const statusType = (s) => ({ running: 'warning', completed: 'success', pending: 'info', failed: 'danger' }[s] || 'info')
const statusText = (s) => ({ running: '运行中', completed: '已完成', pending: '等待中', failed: '失败' }[s] || s)

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
  } catch {}
}

const refreshStatus = async () => {
  try { crawlStatus.value = await getCrawlStatus() } catch {}
}

onMounted(async () => {
  try { strategies.value = await getStrategies() } catch {}
  loadStats()
  refreshStatus()
  timer = setInterval(() => {
    refreshStatus()
  }, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
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
</style>

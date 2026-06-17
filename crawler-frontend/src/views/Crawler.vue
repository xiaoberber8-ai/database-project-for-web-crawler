<template>
  <div class="crawler-page">
    <!-- 爬虫状态卡片 -->
    <el-row :gutter="16" class="status-row">
      <el-col :span="6">
        <el-card shadow="hover" class="status-card">
          <div class="status-item">
            <el-icon :size="32" :color="crawlStatus.thread_alive ? '#67C23A' : '#909399'"><VideoPlay /></el-icon>
            <div>
              <div class="status-label">爬虫状态</div>
              <div class="status-value">{{ crawlStatus.thread_alive ? '运行中' : '未运行' }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="status-card">
          <div class="status-item">
            <el-icon :size="32" :color="crawlStatus.paused ? '#E6A23C' : '#409EFF'"><VideoPause /></el-icon>
            <div>
              <div class="status-label">暂停状态</div>
              <div class="status-value">{{ crawlStatus.paused ? '已暂停' : '正常' }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="status-card">
          <div class="status-item">
            <el-icon :size="32" :color="crawlStatus.stopped ? '#F56C6C' : '#67C23A'"><CircleClose /></el-icon>
            <div>
              <div class="status-label">停止状态</div>
              <div class="status-value">{{ crawlStatus.stopped ? '已停止' : '正常' }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="status-card">
          <div class="status-item">
            <el-icon :size="32" color="#409EFF"><Document /></el-icon>
            <div>
              <div class="status-label">策略数量</div>
              <div class="status-value">{{ strategies.length }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 爬虫控制按钮 -->
    <el-card shadow="hover" class="control-card">
      <template #header>
        <div class="card-header">
          <span>爬虫控制</span>
          <div class="control-btns">
            <el-select v-model="selectedStrategyId" placeholder="选择策略" style="width: 200px; margin-right: 12px;">
              <el-option v-for="s in strategies" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
            <el-button type="success" :icon="VideoPlay" :disabled="crawlStatus.thread_alive" @click="handleStart">启动</el-button>
            <el-button type="warning" :icon="VideoPause" :disabled="!crawlStatus.thread_alive || crawlStatus.paused" @click="handlePause">暂停</el-button>
            <el-button type="primary" :icon="VideoPlay" :disabled="!crawlStatus.paused" @click="handleResume">恢复</el-button>
            <el-button type="danger" :icon="CircleClose" :disabled="!crawlStatus.thread_alive" @click="handleStop">停止</el-button>
            <el-button :icon="Refresh" @click="refreshStatus">刷新状态</el-button>
          </div>
        </div>
      </template>
    </el-card>

    <!-- 策略列表 -->
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>爬虫策略管理</span>
          <el-button type="primary" :icon="Plus" @click="showCreateDialog">新建策略</el-button>
        </div>
      </template>
      <el-table :data="strategies" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="策略名称" width="160" />
        <el-table-column prop="target_url" label="目标URL" min-width="200" show-overflow-tooltip />
        <el-table-column prop="Status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.Status === 'enabled' ? 'success' : 'info'">{{ row.Status === 'enabled' ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="Frequency" label="频率" width="100" />
        <el-table-column prop="rules.depth" label="深度" width="70" />
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :icon="Edit" @click="showEditDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" :icon="Delete" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 任务列表 -->
    <el-card shadow="hover" style="margin-top: 16px;">
      <template #header>
        <div class="card-header">
          <span>任务记录</span>
          <el-button :icon="Refresh" @click="loadTasks">刷新</el-button>
        </div>
      </template>
      <el-table :data="tasks" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="strategy_id" label="策略ID" width="80" />
        <el-table-column prop="Status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getTaskStatusType(row)">{{ getTaskStatusText(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="item_count" label="抓取条目" width="100" />
        <el-table-column prop="start_time" label="开始时间" width="170">
          <template #default="{ row }">{{ formatTime(row.start_time) }}</template>
        </el-table-column>
        <el-table-column prop="end_time" label="结束时间" width="170">
          <template #default="{ row }">{{ formatTime(row.end_time) }}</template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" min-width="150" show-overflow-tooltip />
      </el-table>
    </el-card>

    <!-- 创建/编辑策略对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑策略' : '新建策略'" width="700px" destroy-on-close>
      <el-form ref="strategyFormRef" :model="strategyForm" :rules="strategyRules" label-width="110px">
        <el-form-item label="策略名称" prop="name">
          <el-input v-model="strategyForm.name" placeholder="如：新浪新闻爬虫" />
        </el-form-item>
        <el-form-item label="目标URL" prop="target_url">
          <el-input v-model="strategyForm.target_url" placeholder="如：https://news.sina.com.cn" />
        </el-form-item>
        <el-divider content-position="left">爬取规则</el-divider>
        <el-form-item label="爬取深度" prop="rules.depth">
          <el-input-number v-model="strategyForm.rules.depth" :min="1" :max="5" />
        </el-form-item>
        <el-form-item label="允许域名">
          <div style="width: 100%">
            <div v-for="(d, i) in strategyForm.rules.allowed_domains" :key="i" style="display: flex; gap: 8px; margin-bottom: 4px;">
              <el-input v-model="strategyForm.rules.allowed_domains[i]" placeholder="如：news.sina.com.cn" />
              <el-button :icon="Delete" @click="strategyForm.rules.allowed_domains.splice(i, 1)" />
            </div>
            <el-button :icon="Plus" @click="strategyForm.rules.allowed_domains.push('')">添加域名</el-button>
          </div>
        </el-form-item>
        <el-form-item label="起始URL">
          <div style="width: 100%">
            <div v-for="(u, i) in strategyForm.rules.start_urls" :key="i" style="display: flex; gap: 8px; margin-bottom: 4px;">
              <el-input v-model="strategyForm.rules.start_urls[i]" placeholder="起始URL" />
              <el-button :icon="Delete" @click="strategyForm.rules.start_urls.splice(i, 1)" />
            </div>
            <el-button :icon="Plus" @click="strategyForm.rules.start_urls.push('')">添加URL</el-button>
          </div>
        </el-form-item>
        <el-divider content-position="left">文本规则</el-divider>
        <el-form-item label="标题选择器">
          <el-input v-model="strategyForm.rules.text_rules.title_selector" placeholder="如：h1" />
        </el-form-item>
        <el-form-item label="正文选择器">
          <el-input v-model="strategyForm.rules.text_rules.body_selector" placeholder="如：.article 或 body" />
        </el-form-item>
        <el-divider content-position="left">图片规则</el-divider>
        <el-form-item label="图片选择器">
          <el-input v-model="strategyForm.rules.image_rules.image_selector" placeholder="如：img" />
        </el-form-item>
        <el-form-item label="下载图片">
          <el-switch v-model="strategyForm.rules.image_rules.download_images" />
        </el-form-item>
        <el-form-item label="图片目录">
          <el-input v-model="strategyForm.rules.image_rules.image_dir" placeholder="如：./images" />
        </el-form-item>
        <el-divider content-position="left">请求设置</el-divider>
        <el-form-item label="超时时间(秒)">
          <el-input-number v-model="strategyForm.rules.timeout" :min="5" :max="120" />
        </el-form-item>
        <el-form-item label="请求频率">
          <el-input-number v-model="strategyForm.rules.rate_limit" :min="0.1" :max="10" :step="0.5" :precision="1" />
        </el-form-item>
        <el-divider content-position="left">其他设置</el-divider>
        <el-form-item label="策略状态">
          <el-select v-model="strategyForm.Status">
            <el-option label="启用" value="enabled" />
            <el-option label="禁用" value="disabled" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行频率">
          <el-select v-model="strategyForm.Frequency">
            <el-option label="手动" value="manual" />
            <el-option label="每天" value="daily" />
            <el-option label="每周" value="weekly" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">{{ isEdit ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getStrategies, createStrategy, updateStrategy, deleteStrategy,
  startCrawl, pauseCrawl, resumeCrawl, stopCrawl, getCrawlStatus,
  getTasks
} from '../api'
import api from '../api'

const strategies = ref([])
const tasks = ref([])
const selectedStrategyId = ref(null)
const crawlStatus = ref({ thread_alive: false, paused: false, stopped: false })
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const submitLoading = ref(false)
const strategyFormRef = ref(null)
let statusTimer = null

const defaultForm = () => ({
  name: '',
  target_url: '',
  rules: {
    depth: 1,
    allowed_domains: [],
    start_urls: [],
    text_rules: { title_selector: 'h1', body_selector: 'body' },
    image_rules: { image_selector: 'img', download_images: true, image_dir: './images' },
    headers: { 'User-Agent': 'Mozilla/5.0' },
    timeout: 30,
    rate_limit: 1
  },
  Status: 'enabled',
  Frequency: 'manual',
  creator_id: null
})

const strategyForm = reactive(defaultForm())

const strategyRules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
  target_url: [{ required: true, message: '请输入目标URL', trigger: 'blur' }]
}

const formatTime = (t) => {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

const statusType = (s) => ({ running: 'warning', completed: 'success', pending: 'info', failed: 'danger' }[s] || 'info')
const statusText = (s) => ({ running: '运行中', completed: '已完成', pending: '等待中', failed: '失败' }[s] || s)

// 修正任务状态：如果任务记录是running但线程已死，则显示为"已完成"
const getTaskStatusType = (row) => {
  if (row.Status === 'running' && !crawlStatus.value.thread_alive) return 'success'
  return statusType(row.Status)
}
const getTaskStatusText = (row) => {
  if (row.Status === 'running' && !crawlStatus.value.thread_alive) return '已完成'
  return statusText(row.Status)
}

const refreshStatus = async () => {
  try { crawlStatus.value = await getCrawlStatus() } catch {}
}

const loadStrategies = async () => {
  try { strategies.value = await getStrategies() } catch {}
}

const loadTasks = async () => {
  try { tasks.value = await getTasks() } catch {}
}

const showCreateDialog = () => {
  isEdit.value = false
  editId.value = null
  Object.assign(strategyForm, defaultForm())
  dialogVisible.value = true
}

const showEditDialog = (row) => {
  isEdit.value = true
  editId.value = row.id
  Object.assign(strategyForm, {
    name: row.name,
    target_url: row.target_url,
    rules: JSON.parse(JSON.stringify(row.rules)),
    Status: row.Status,
    Frequency: row.Frequency,
    creator_id: row.creator_id
  })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  const valid = await strategyFormRef.value.validate().catch(() => false)
  if (!valid) return
  submitLoading.value = true
  try {
    if (isEdit.value) {
      // 使用数据代理服务更新策略（绕过后端 model_dump_json bug）
      await api.put(`/data-api/strategies/${editId.value}`, strategyForm)
      ElMessage.success('更新成功')
    } else {
      await createStrategy(strategyForm)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadStrategies()
  } finally {
    submitLoading.value = false
  }
}

const handleDelete = async (row) => {
  // 检查是否有关联任务
  const relatedTasks = tasks.value.filter(t => t.strategy_id === row.id)
  if (relatedTasks.length > 0) {
    await ElMessageBox.confirm(
      `策略「${row.name}」下有 ${relatedTasks.length} 条关联任务记录及对应数据。选择「强制删除」将同时删除所有关联数据（任务、网页、内容、图片），此操作不可恢复！`,
      '该策略有关联数据',
      {
        confirmButtonText: '强制删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    // 级联删除：通过数据代理一次性删除策略及所有关联数据
    try {
      await api.delete(`/data-api/strategy/${row.id}/cascade`)
      ElMessage.success('删除成功（已清理所有关联数据）')
      loadStrategies()
      loadTasks()
    } catch (e) {
      ElMessage.error('强制删除失败：' + (e.response?.data?.detail || e.message))
    }
    return
  }
  await ElMessageBox.confirm(`确定删除策略「${row.name}」？`, '提示', { type: 'warning' })
  try {
    await deleteStrategy(row.id)
    ElMessage.success('删除成功')
    loadStrategies()
  } catch (e) {
    ElMessage.error('删除失败，该策略可能有关联数据。请尝试强制删除')
  }
}

const handleStart = async () => {
  if (!selectedStrategyId.value) {
    ElMessage.warning('请先选择策略')
    return
  }
  await startCrawl(selectedStrategyId.value)
  ElMessage.success('爬虫已启动')
  refreshStatus()
}

const handlePause = async () => {
  await pauseCrawl()
  ElMessage.success('已暂停')
  refreshStatus()
}

const handleResume = async () => {
  await resumeCrawl()
  ElMessage.success('已恢复')
  refreshStatus()
}

const handleStop = async () => {
  await stopCrawl()
  ElMessage.success('已停止')
  refreshStatus()
}

onMounted(() => {
  loadStrategies()
  loadTasks()
  refreshStatus()
  statusTimer = setInterval(() => {
    refreshStatus()
    if (crawlStatus.value.thread_alive) loadTasks()
  }, 3000)
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
})
</script>

<style scoped>
.crawler-page {
  padding: 0;
}
.status-row {
  margin-bottom: 16px;
}
.status-card {
  height: 90px;
}
.status-item {
  display: flex;
  align-items: center;
  gap: 12px;
}
.status-label {
  font-size: 13px;
  color: #909399;
}
.status-value {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
}
.control-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.control-btns {
  display: flex;
  align-items: center;
}
</style>

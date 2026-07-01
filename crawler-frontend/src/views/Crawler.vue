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
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="strategyTypeTag(row)" size="small">{{ strategyTypeLabel(row) }}</el-tag>
          </template>
        </el-table-column>
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

    <!-- 策略类型选择对话框 -->
    <el-dialog v-model="typeDialogVisible" title="选择策略类型" width="680px" :close-on-click-modal="false">
      <div class="strategy-type-cards">
        <div class="type-card" @click="selectType('baby')">
          <div class="type-icon" style="background: #fef3c7; color: #92400e;">
            <el-icon :size="36"><Sunny /></el-icon>
          </div>
          <div class="type-title">宝宝策略</div>
          <div class="type-desc">只需输入网址 URL，其余参数全部使用默认值（爬取深度=1），一键开始爬取。适合快速抓取单个页面。</div>
        </div>
        <div class="type-card" @click="selectType('professional')">
          <div class="type-icon" style="background: #dbeafe; color: #1e40af;">
            <el-icon :size="36"><Setting /></el-icon>
          </div>
          <div class="type-title">专业模式</div>
          <div class="type-desc">完整配置爬取深度、选择器、图片规则、请求参数等所有选项。适合有经验的高级用户精确控制爬虫行为。</div>
        </div>
      </div>
    </el-dialog>

    <!-- 宝宝策略对话框 -->
    <el-dialog v-model="babyDialogVisible" title="宝宝策略 - 快速爬取" width="500px" destroy-on-close>
      <el-form ref="babyFormRef" :model="babyForm" :rules="babyRules" label-width="100px">
        <el-form-item label="策略名称" prop="name">
          <el-input v-model="babyForm.name" placeholder="如：快速爬取测试" />
        </el-form-item>
        <el-form-item label="目标网址" prop="target_url">
          <el-input v-model="babyForm.target_url" placeholder="如：https://example.com/page" />
        </el-form-item>
      </el-form>
      <el-alert title="宝宝策略将使用默认参数：爬取深度=1，不下载图片，仅抓取当前页面文本内容" type="info" :closable="false" style="margin-bottom: 12px;" />
      <template #footer>
        <el-button @click="babyDialogVisible = false">取消</el-button>
        <el-button type="warning" :loading="submitLoading" @click="handleBabySubmit">创建并爬取</el-button>
      </template>
    </el-dialog>

    <!-- 创建/编辑策略对话框（专业模式） -->
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
        <el-form-item label="图片容器选择器">
          <el-input v-model="strategyForm.rules.image_rules.image_container_selector" placeholder="如：.article-content（留空则回退正文区域）" />
        </el-form-item>
        <el-form-item label="只抓正文图片">
          <el-switch v-model="strategyForm.rules.image_rules.only_article_images" />
        </el-form-item>
        <el-form-item label="最小宽度(px)">
          <el-input-number v-model="strategyForm.rules.image_rules.min_width" :min="0" :max="5000" :step="10" />
        </el-form-item>
        <el-form-item label="最小高度(px)">
          <el-input-number v-model="strategyForm.rules.image_rules.min_height" :min="0" :max="5000" :step="10" />
        </el-form-item>
        <el-form-item label="最小面积(px²)">
          <el-input-number v-model="strategyForm.rules.image_rules.min_area" :min="0" :max="10000000" :step="1000" />
        </el-form-item>
        <el-form-item label="最大宽高比">
          <el-input-number v-model="strategyForm.rules.image_rules.max_ratio" :min="1" :max="50" :step="0.5" :precision="1" />
        </el-form-item>
        <el-form-item label="过滤广告关键词">
          <el-select
            v-model="strategyForm.rules.image_rules.exclude_keywords"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入关键词后回车，如 ad、logo"
          />
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
        <el-form-item label="重复数据处理">
          <el-select v-model="strategyForm.rules.duplicate_action">
            <el-option label="覆盖（重新抓取已爬过的页面）" value="overwrite" />
            <el-option label="跳过（不重复抓取已爬过的页面）" value="skip" />
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
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Edit, Delete, Refresh, VideoPlay, VideoPause, CircleClose,
  Document, Sunny, Setting
} from '@element-plus/icons-vue'
import {
  getStrategies, createStrategy, updateStrategy, deleteStrategy,
  startCrawl, pauseCrawl, resumeCrawl, stopCrawl, getCrawlStatus,
  getTasks
} from '../api'
import axios from 'axios'

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
    strategy_type: 'professional',
    depth: 1,
    allowed_domains: [],
    start_urls: [],
    text_rules: { title_selector: 'h1', body_selector: 'body' },
    image_rules: {
      image_selector: 'img',
      download_images: true,
      image_dir: './images',
      image_container_selector: null,
      only_article_images: true,
      min_width: 150,
      min_height: 150,
      min_area: 30000,
      max_ratio: 5.0,
      exclude_keywords: ['ad', 'ads', 'advert', 'banner', 'logo', 'icon', 'sprite', 'avatar', 'share', 'wechat', 'wx', 'tracking', 'pixel', 'recommend']
    },
    headers: { 'User-Agent': 'Mozilla/5.0' },
    timeout: 30,
    rate_limit: 1,
    duplicate_action: 'overwrite'
  },
  Status: 'enabled',
  Frequency: 'manual',
  creator_id: null
})

// ===== 策略类型选择 =====
const typeDialogVisible = ref(false)

// ===== 宝宝策略 =====
const babyDialogVisible = ref(false)
const babyFormRef = ref(null)
const babyForm = reactive({ name: '', target_url: '' })
const babyRules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
  target_url: [{ required: true, message: '请输入目标网址', trigger: 'blur' }]
}

const strategyForm = reactive(defaultForm())

const strategyRules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
  target_url: [{ required: true, message: '请输入目标URL', trigger: 'blur' }]
}

const formatTime = (t) => {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

const statusType = (s) => ({ running: 'warning', completed: 'success', pending: 'info', failed: 'danger', cancelled: 'info', interrupted: 'danger' }[s] || 'info')
const statusText = (s) => ({ running: '运行中', completed: '已完成', pending: '等待中', failed: '失败', cancelled: '已取消', interrupted: '已中断' }[s] || s)

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
  // 打开类型选择对话框
  typeDialogVisible.value = true
}

const selectType = (type) => {
  typeDialogVisible.value = false
  if (type === 'baby') {
    babyForm.name = ''
    babyForm.target_url = ''
    babyDialogVisible.value = true
  } else if (type === 'professional') {
    isEdit.value = false
    editId.value = null
    Object.assign(strategyForm, defaultForm())
    strategyForm.rules.strategy_type = 'professional'
    dialogVisible.value = true
  }
}

// 策略类型标签
const strategyTypeLabel = (row) => {
  const t = row.rules?.strategy_type || 'professional'
  return { baby: '宝宝策略', professional: '专业模式' }[t] || '专业模式'
}
const strategyTypeTag = (row) => {
  const t = row.rules?.strategy_type || 'professional'
  return { baby: 'warning', professional: '' }[t] || ''
}

// ===== 宝宝策略提交 =====
const handleBabySubmit = async () => {
  const valid = await babyFormRef.value.validate().catch(() => false)
  if (!valid) return
  submitLoading.value = true
  try {
    const payload = {
      name: babyForm.name,
      target_url: babyForm.target_url,
      rules: {
        strategy_type: 'baby',
        depth: 1,
        allowed_domains: [],
        start_urls: [babyForm.target_url],
        text_rules: { title_selector: 'h1', body_selector: 'body' },
        image_rules: {
          image_selector: 'img',
          download_images: false,
          image_dir: './images',
          image_container_selector: null,
          only_article_images: true,
          min_width: 150,
          min_height: 150,
          min_area: 30000,
          max_ratio: 5.0,
          exclude_keywords: ['ad', 'ads', 'advert', 'banner', 'logo', 'icon', 'sprite', 'avatar', 'share', 'wechat', 'wx', 'tracking', 'pixel', 'recommend']
        },
        headers: { 'User-Agent': 'Mozilla/5.0' },
        timeout: 30,
        rate_limit: 1,
        duplicate_action: 'overwrite'
      },
      Status: 'enabled',
      Frequency: 'manual',
      creator_id: null
    }
    const created = await createStrategy(payload)
    ElMessage.success('宝宝策略创建成功，即将开始爬取')
    babyDialogVisible.value = false
    loadStrategies()
    // 自动启动爬取
    if (created && created.id) {
      await startCrawl(created.id)
      selectedStrategyId.value = created.id
      refreshStatus()
    }
  } catch (e) {
    ElMessage.error('创建失败：' + (e.response?.data?.detail || e.message))
  } finally {
    submitLoading.value = false
  }
}

const showEditDialog = (row) => {
  isEdit.value = true
  editId.value = row.id
  const defaults = defaultForm()
  const mergedRules = {
    ...defaults.rules,
    ...JSON.parse(JSON.stringify(row.rules)),
    text_rules: { ...defaults.rules.text_rules, ...(row.rules?.text_rules || {}) },
    image_rules: { ...defaults.rules.image_rules, ...(row.rules?.image_rules || {}) }
  }
  Object.assign(strategyForm, {
    name: row.name,
    target_url: row.target_url,
    rules: mergedRules,
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
      await updateStrategy(editId.value, strategyForm)
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
      await axios.delete(`/data-api/strategy/${row.id}/cascade`)
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

/* ===== 策略类型选择卡片 ===== */
.strategy-type-cards {
  display: flex;
  gap: 16px;
}
.type-card {
  flex: 1;
  border: 2px solid #e4e7ed;
  border-radius: 10px;
  padding: 20px 16px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s;
}
.type-card:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.15);
  transform: translateY(-2px);
}
.type-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
}
.type-title {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 8px;
}
.type-desc {
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
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

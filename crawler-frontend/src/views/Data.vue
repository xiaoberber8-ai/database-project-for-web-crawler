<template>
  <div class="data-page">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 网页数据 -->
      <el-tab-pane label="网页数据" name="webpage">
        <div class="tab-header">
          <el-button :icon="Refresh" @click="loadWebpages">刷新</el-button>
          <el-tag type="info">共 {{ webpages.length }} 条</el-tag>
        </div>
        <el-table :data="paginatedWebpages" stripe style="width: 100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="url" label="URL" min-width="250" show-overflow-tooltip />
          <el-table-column prop="http_status" label="HTTP状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.http_status === 200 ? 'success' : 'danger'">{{ row.http_status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="process_status" label="处理状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.process_status === 'parsed' ? 'success' : 'warning'">{{ row.process_status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="task_id" label="任务ID" width="80" />
          <el-table-column prop="fetch_time" label="爬取时间" width="170">
            <template #default="{ row }">{{ formatTime(row.fetch_time) }}</template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="webpagePage"
          :page-size="pageSize"
          :total="webpages.length"
          layout="prev, pager, next"
          style="margin-top: 12px; justify-content: center;"
        />
      </el-tab-pane>

      <!-- 文本内容 -->
      <el-tab-pane label="文本内容" name="content">
        <div class="tab-header">
          <div class="tab-header-left">
            <el-button :icon="Refresh" @click="loadContents">刷新</el-button>
            <el-button
              type="danger"
              :icon="Delete"
              :disabled="selectedContents.length === 0"
              @click="handleBatchDeleteContents"
            >批量删除 ({{ selectedContents.length }})</el-button>
            <el-button
              type="success"
              :icon="Download"
              :disabled="selectedContents.length === 0"
              @click="handleBatchExportContents"
            >导出选中 ({{ selectedContents.length }})</el-button>
            <el-button :icon="Download" @click="handleExportAllContents">导出全部</el-button>
          </div>
          <el-tag type="info">共 {{ filteredContents.length }} 条</el-tag>
        </div>
        <div class="filter-bar">
          <el-input v-model="contentFilter.taskId" placeholder="按任务ID筛选" clearable size="small" style="width: 140px;" />
          <el-input v-model="contentFilter.strategyId" placeholder="按策略ID筛选" clearable size="small" style="width: 140px;" />
          <el-button size="small" :icon="Search" @click="contentPage = 1">筛选</el-button>
          <el-button size="small" @click="resetContentFilter">重置</el-button>
        </div>
        <el-table
          ref="contentTableRef"
          :data="paginatedContents"
          stripe
          style="width: 100%"
          @selection-change="onContentSelectionChange"
        >
          <el-table-column type="selection" width="45" />
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="Title" label="标题" width="200" show-overflow-tooltip />
          <el-table-column prop="text_body" label="正文预览" min-width="300" show-overflow-tooltip>
            <template #default="{ row }">{{ (row.text_body || '').substring(0, 150) }}...</template>
          </el-table-column>
          <el-table-column prop="webpage_id" label="网页ID" width="80" />
          <el-table-column prop="task_id" label="任务ID" width="80" />
          <el-table-column prop="strategy_id" label="策略ID" width="80" />
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" :icon="View" @click="viewContent(row)">查看</el-button>
              <el-button size="small" :icon="Download" @click="handleExportContent(row)">导出</el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="handleDeleteContent(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="contentPage"
          :page-size="pageSize"
          :total="filteredContents.length"
          layout="prev, pager, next"
          style="margin-top: 12px; justify-content: center;"
        />
      </el-tab-pane>

      <!-- 图片数据 -->
      <el-tab-pane label="图片数据" name="image">
        <div class="tab-header">
          <div class="tab-header-left">
            <el-button :icon="Refresh" @click="loadImages">刷新</el-button>
            <el-button
              type="danger"
              :icon="Delete"
              :disabled="selectedImages.length === 0"
              @click="handleBatchDeleteImages"
            >批量删除 ({{ selectedImages.length }})</el-button>
          </div>
          <el-tag type="info">共 {{ filteredImages.length }} 条</el-tag>
        </div>
        <div class="filter-bar">
          <el-input v-model="imageFilter.taskId" placeholder="按任务ID筛选" clearable size="small" style="width: 140px;" />
          <el-input v-model="imageFilter.strategyId" placeholder="按策略ID筛选" clearable size="small" style="width: 140px;" />
          <el-button size="small" :icon="Search" @click="imagePage = 1">筛选</el-button>
          <el-button size="small" @click="resetImageFilter">重置</el-button>
        </div>
        <el-table
          ref="imageTableRef"
          :data="paginatedImages"
          stripe
          style="width: 100%"
          @selection-change="onImageSelectionChange"
        >
          <el-table-column type="selection" width="45" />
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column label="缩略图" width="100">
            <template #default="{ row }">
              <el-image
                v-if="row.id"
                :src="getImageSrc(row)"
                :preview-src-list="[getImageSrc(row)]"
                preview-teleported
                fit="cover"
                style="width: 60px; height: 60px; border-radius: 4px;"
                :hide-on-click-modal="true"
              >
                <template #error>
                  <div class="img-error">
                    <el-icon><Picture /></el-icon>
                  </div>
                </template>
              </el-image>
            </template>
          </el-table-column>
          <el-table-column prop="image_url" label="图片URL" min-width="200" show-overflow-tooltip />
          <el-table-column prop="local_path" label="本地路径" width="180" show-overflow-tooltip />
          <el-table-column prop="description" label="描述" width="150" show-overflow-tooltip />
          <el-table-column prop="webpage_id" label="网页ID" width="80" />
          <el-table-column prop="task_id" label="任务ID" width="80" />
          <el-table-column prop="strategy_id" label="策略ID" width="80" />
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button size="small" :icon="View" @click="handlePreviewImage(row)">预览</el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="handleDeleteImage(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="imagePage"
          :page-size="pageSize"
          :total="filteredImages.length"
          layout="prev, pager, next"
          style="margin-top: 12px; justify-content: center;"
        />
      </el-tab-pane>
    </el-tabs>

    <!-- 内容查看对话框 -->
    <el-dialog v-model="contentDialogVisible" :title="currentContent.Title || '内容详情'" width="700px">
      <div class="content-detail">
        <h3>{{ currentContent.Title }}</h3>
        <el-divider />
        <div class="content-body">{{ currentContent.text_body }}</div>
      </div>
    </el-dialog>

    <!-- 图片预览对话框 -->
    <el-dialog v-model="imageDialogVisible" title="图片预览" width="700px">
      <div class="image-preview-container">
        <el-image
          v-if="currentImage.id"
          :src="getImageSrc(currentImage)"
          fit="contain"
          style="max-width: 100%; max-height: 500px;"
          :preview-src-list="[getImageSrc(currentImage)]"
          preview-teleported
        >
          <template #error>
            <div class="img-error-large">
              <el-icon :size="48"><Picture /></el-icon>
              <p>图片无法加载</p>
            </div>
          </template>
        </el-image>
        <div class="image-info">
          <p><strong>ID：</strong>{{ currentImage.id }}</p>
          <p><strong>URL：</strong>{{ currentImage.image_url }}</p>
          <p v-if="currentImage.description"><strong>描述：</strong>{{ currentImage.description }}</p>
          <p v-if="currentImage.local_path"><strong>本地路径：</strong>{{ currentImage.local_path }}</p>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, View, Delete, Download, Picture, Search } from '@element-plus/icons-vue'
import {
  getWebpages, getContents, getImages,
  deleteContent, batchDeleteContents,
  deleteImage, batchDeleteImages
} from '../api'

const activeTab = ref('webpage')
const webpages = ref([])
const contents = ref([])
const images = ref([])
const webpagePage = ref(1)
const contentPage = ref(1)
const imagePage = ref(1)
const pageSize = 15
const contentDialogVisible = ref(false)
const currentContent = ref({})
const imageDialogVisible = ref(false)
const currentImage = ref({})

// 多选选中项
const selectedContents = ref([])
const selectedImages = ref([])

// 筛选条件
const contentFilter = ref({ taskId: '', strategyId: '' })
const imageFilter = ref({ taskId: '', strategyId: '' })

const formatTime = (t) => {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

// 图片显示源：优先走 data_proxy 本地图片代理，避免外链 token 失效/防盗链
const getImageSrc = (row) => {
  return `/data-api/image_file/${row.id}`
}

const paginatedWebpages = computed(() => {
  const start = (webpagePage.value - 1) * pageSize
  return webpages.value.slice(start, start + pageSize)
})

// 文本内容筛选：按任务ID、策略ID
const filteredContents = computed(() => {
  const { taskId, strategyId } = contentFilter.value
  let results = contents.value
  if (taskId) {
    const tid = parseInt(taskId, 10)
    if (!isNaN(tid)) {
      results = results.filter(c => c.task_id === tid)
    }
  }
  if (strategyId) {
    const sid = parseInt(strategyId, 10)
    if (!isNaN(sid)) {
      results = results.filter(c => c.strategy_id === sid)
    }
  }
  return results
})
const paginatedContents = computed(() => {
  const start = (contentPage.value - 1) * pageSize
  return filteredContents.value.slice(start, start + pageSize)
})

// 图片数据筛选：按任务ID、策略ID
const filteredImages = computed(() => {
  const { taskId, strategyId } = imageFilter.value
  let results = images.value
  if (taskId) {
    const tid = parseInt(taskId, 10)
    if (!isNaN(tid)) {
      results = results.filter(i => i.task_id === tid)
    }
  }
  if (strategyId) {
    const sid = parseInt(strategyId, 10)
    if (!isNaN(sid)) {
      results = results.filter(i => i.strategy_id === sid)
    }
  }
  return results
})
const paginatedImages = computed(() => {
  const start = (imagePage.value - 1) * pageSize
  return filteredImages.value.slice(start, start + pageSize)
})

// 重置筛选
const resetContentFilter = () => {
  contentFilter.value = { taskId: '', strategyId: '' }
  contentPage.value = 1
}
const resetImageFilter = () => {
  imageFilter.value = { taskId: '', strategyId: '' }
  imagePage.value = 1
}

const loadWebpages = async () => {
  try { webpages.value = await getWebpages() } catch { webpages.value = [] }
}
const loadContents = async () => {
  try { contents.value = await getContents() } catch { contents.value = [] }
}
const loadImages = async () => {
  try { images.value = await getImages() } catch { images.value = [] }
}

const viewContent = (row) => {
  currentContent.value = row
  contentDialogVisible.value = true
}

// ===== 多选处理 =====
const onContentSelectionChange = (rows) => {
  selectedContents.value = rows
}
const onImageSelectionChange = (rows) => {
  selectedImages.value = rows
}

// ===== 内容删除 =====
const handleDeleteContent = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除内容「${row.Title || row.id}」？此操作将同步删除数据库记录，不可恢复。`, '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteContent(row.id)
    ElMessage.success('删除成功')
    loadContents()
  } catch (e) {
    ElMessage.error('删除失败：' + (e.response?.data?.detail || e.message))
  }
}

const handleBatchDeleteContents = async () => {
  if (selectedContents.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确定批量删除选中的 ${selectedContents.value.length} 条内容？此操作不可恢复。`, '批量删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    const ids = selectedContents.value.map(r => r.id)
    const res = await batchDeleteContents(ids)
    ElMessage.success(`批量删除成功，共删除 ${res.deleted_count} 条`)
    selectedContents.value = []
    loadContents()
  } catch (e) {
    ElMessage.error('批量删除失败：' + (e.response?.data?.detail || e.message))
  }
}

// ===== 图片删除 =====
const handleDeleteImage = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除图片（ID: ${row.id}）？此操作将同步删除数据库记录，不可恢复。`, '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteImage(row.id)
    ElMessage.success('删除成功')
    loadImages()
  } catch (e) {
    ElMessage.error('删除失败：' + (e.response?.data?.detail || e.message))
  }
}

const handleBatchDeleteImages = async () => {
  if (selectedImages.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确定批量删除选中的 ${selectedImages.value.length} 张图片？此操作不可恢复。`, '批量删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    const ids = selectedImages.value.map(r => r.id)
    const res = await batchDeleteImages(ids)
    ElMessage.success(`批量删除成功，共删除 ${res.deleted_count} 张`)
    selectedImages.value = []
    loadImages()
  } catch (e) {
    ElMessage.error('批量删除失败：' + (e.response?.data?.detail || e.message))
  }
}

// ===== 图片预览 =====
const handlePreviewImage = (row) => {
  currentImage.value = row
  imageDialogVisible.value = true
}

// ===== Excel 导出 =====
// 无需第三方依赖：生成 Excel 可直接打开的 HTML 表格文件（.xls）
const exportToExcel = (data, filename, columns) => {
  if (!data || data.length === 0) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  // 构建 HTML 表格，\ufeff BOM 保证中文在 Excel 中正确显示
  let html = '<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel">'
  html += '<head><meta charset="UTF-8"><!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet><x:Name>Sheet1</x:Name><x:WorksheetOptions><x:DisplayGridlines/></x:WorksheetOptions></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]--></head><body><table border="1">'
  // 表头
  html += '<tr>' + columns.map(c => `<th style="background:#409EFF;color:#fff;">${escapeHtml(c.label)}</th>`).join('') + '</tr>'
  // 数据行
  data.forEach(row => {
    html += '<tr>' + columns.map(c => {
      let val = row[c.prop]
      if (val === null || val === undefined) val = ''
      // 日期格式化
      if (c.prop === 'publish_time' || c.prop === 'crawl_time' || c.prop === 'fetch_time') {
        val = formatTime(val)
      }
      return `<td>${escapeHtml(String(val))}</td>`
    }).join('') + '</tr>'
  })
  html += '</table></body></html>'

  const blob = new Blob(['\ufeff' + html], { type: 'application/vnd.ms-excel;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename + '.xls'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const escapeHtml = (text) => {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
  return text.replace(/[&<>"']/g, m => map[m])
}

// 内容导出列定义
const contentColumns = [
  { prop: 'id', label: 'ID' },
  { prop: 'Title', label: '标题' },
  { prop: 'text_body', label: '正文内容' },
  { prop: 'webpage_id', label: '网页ID' },
  { prop: 'crawl_time', label: '爬取时间' },
  { prop: 'strategy_id', label: '策略ID' },
  { prop: 'Publisher', label: '发布者' },
  { prop: 'datasource_url', label: '来源URL' }
]

const handleExportContent = (row) => {
  exportToExcel([row], `内容_${row.id}_${row.Title || '未命名'}`, contentColumns)
  ElMessage.success('导出成功')
}

const handleBatchExportContents = () => {
  if (selectedContents.value.length === 0) return
  exportToExcel(selectedContents.value, `文本内容_选中${selectedContents.value.length}条_${formatDate(new Date())}`, contentColumns)
  ElMessage.success(`已导出 ${selectedContents.value.length} 条内容`)
}

const handleExportAllContents = () => {
  if (contents.value.length === 0) {
    ElMessage.warning('暂无内容可导出')
    return
  }
  exportToExcel(contents.value, `文本内容_全部${contents.value.length}条_${formatDate(new Date())}`, contentColumns)
  ElMessage.success(`已导出全部 ${contents.value.length} 条内容`)
}

const formatDate = (d) => {
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`
}

onMounted(() => {
  loadWebpages()
  loadContents()
  loadImages()
})
</script>

<style scoped>
.tab-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.tab-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
}
.content-detail h3 {
  margin: 0 0 8px;
}
.content-body {
  white-space: pre-wrap;
  line-height: 1.8;
  max-height: 500px;
  overflow-y: auto;
}
.img-error {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  border-radius: 4px;
  color: #c0c4cc;
}
.img-error-large {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: #c0c4cc;
}
.img-error-large p {
  margin-top: 8px;
}
.image-preview-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.image-info {
  width: 100%;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.8;
}
.image-info p {
  margin: 0;
  word-break: break-all;
}
</style>

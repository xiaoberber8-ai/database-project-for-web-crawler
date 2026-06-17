<template>
  <div class="search-page">
    <el-card shadow="hover">
      <template #header>
        <span>高级检索</span>
      </template>
      <el-form :model="searchForm" inline>
        <el-form-item label="关键字">
          <el-input v-model="searchForm.keyword" placeholder="搜索标题或正文" clearable style="width: 220px;" />
        </el-form-item>
        <el-form-item label="发布者">
          <el-input v-model="searchForm.publisher" placeholder="发布者名称" clearable style="width: 160px;" />
        </el-form-item>
        <el-form-item label="任务ID">
          <el-input v-model="searchForm.taskId" placeholder="输入任务ID" clearable style="width: 120px;" />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="searchForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 260px;"
          />
        </el-form-item>
        <el-form-item label="域名">
          <el-input v-model="searchForm.domain" placeholder="如：sina.com.cn" clearable style="width: 160px;" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 搜索结果统计 -->
    <el-card shadow="hover" style="margin-top: 16px;" v-if="searched">
      <template #header>
        <div class="card-header">
          <span>搜索结果（共 {{ filteredContents.length }} 条）</span>
          <el-tag>耗时 {{ searchTime }} ms</el-tag>
        </div>
      </template>
      <el-table :data="paginatedResults" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="Title" label="标题" width="250" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-html="highlightKeyword(row.Title)"></span>
          </template>
        </el-table-column>
        <el-table-column prop="text_body" label="正文预览" min-width="350" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-html="highlightKeyword(getPreview(row.text_body))"></span>
          </template>
        </el-table-column>
        <el-table-column prop="Publisher" label="发布者" width="120" show-overflow-tooltip />
        <el-table-column prop="Publish_Date" label="发布时间" width="120" show-overflow-tooltip />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :icon="View" @click="viewContent(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="resultPage"
        :page-size="pageSize"
        :total="filteredContents.length"
        layout="prev, pager, next, total"
        style="margin-top: 12px; justify-content: center;"
      />
    </el-card>

    <!-- 内容查看对话框 -->
    <el-dialog v-model="contentDialogVisible" :title="currentContent.Title || '内容详情'" width="800px" top="5vh">
      <div class="content-detail">
        <h3 v-html="highlightKeyword(currentContent.Title)"></h3>
        <div class="content-meta" v-if="currentContent.Publisher || currentContent.Publish_Date">
          <el-tag v-if="currentContent.Publisher" size="small">{{ currentContent.Publisher }}</el-tag>
          <el-tag v-if="currentContent.Publish_Date" size="small" type="info">{{ currentContent.Publish_Date }}</el-tag>
        </div>
        <el-divider />

        <!-- 关联图片展示 -->
        <div class="content-images" v-if="currentContentImages.length">
          <div class="images-header">
            <span>关联图片（{{ currentContentImages.length }} 张）</span>
            <el-tag size="small" type="success">来自同一网页</el-tag>
          </div>
          <div class="images-grid">
            <div
              v-for="(img, idx) in currentContentImages"
              :key="img.id"
              class="image-item"
            >
              <el-image
                :src="resolveImageUrl(img)"
                fit="cover"
                :preview-src-list="currentContentImages.map(resolveImageUrl)"
                :initial-index="idx"
                hide-on-click-modal
                preview-teleported
                class="image-thumb"
              >
                <template #error>
                  <div class="image-error">
                    <el-icon><Picture /></el-icon>
                    <span>加载失败</span>
                  </div>
                </template>
                <template #placeholder>
                  <div class="image-placeholder">
                    <el-icon class="is-loading"><Loading /></el-icon>
                  </div>
                </template>
              </el-image>
              <div class="image-desc" v-if="img.description" :title="img.description">
                {{ img.description }}
              </div>
            </div>
          </div>
          <el-divider />
        </div>
        <div v-else class="no-images">
          <el-tag size="small" type="info">该内容暂无关联图片</el-tag>
          <el-divider />
        </div>

        <div class="content-body" v-html="highlightKeyword(currentContent.text_body)"></div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getContents, getWebpages, getImages } from '../api'
import { Search, View, Picture, Loading } from '@element-plus/icons-vue'

const allContents = ref([])
const allWebpages = ref([])
const allImages = ref([])
const searched = ref(false)
const searchTime = ref(0)
const resultPage = ref(1)
const pageSize = 15
const contentDialogVisible = ref(false)
const currentContent = ref({})
const currentContentImages = ref([])

const searchForm = ref({
  keyword: '',
  publisher: '',
  taskId: '',
  dateRange: null,
  domain: ''
})

const filteredContents = computed(() => {
  let results = allContents.value
  const { keyword, publisher, taskId, dateRange, domain } = searchForm.value

  if (keyword) {
    const kw = keyword.toLowerCase()
    results = results.filter(c =>
      (c.Title || '').toLowerCase().includes(kw) ||
      (c.text_body || '').toLowerCase().includes(kw)
    )
  }

  if (publisher) {
    const pub = publisher.toLowerCase()
    results = results.filter(c => (c.Publisher || '').toLowerCase().includes(pub))
  }

  if (taskId) {
    const tid = parseInt(taskId, 10)
    if (!isNaN(tid)) {
      const matchingWebpageIds = allWebpages.value
        .filter(w => w.task_id === tid)
        .map(w => w.id)
      results = results.filter(c => matchingWebpageIds.includes(c.webpage_id))
    }
  }

  if (dateRange && dateRange.length === 2) {
    const [start, end] = dateRange
    results = results.filter(c => {
      if (!c.Publish_Date) return false
      return c.Publish_Date >= start && c.Publish_Date <= end
    })
  }

  if (domain) {
    const d = domain.toLowerCase()
    const matchingWebpageIds = allWebpages.value
      .filter(w => (w.url || '').toLowerCase().includes(d))
      .map(w => w.id)
    results = results.filter(c => matchingWebpageIds.includes(c.webpage_id))
  }

  return results
})

const paginatedResults = computed(() => {
  const start = (resultPage.value - 1) * pageSize
  return filteredContents.value.slice(start, start + pageSize)
})

const getPreview = (text) => {
  if (!text) return ''
  return text.substring(0, 200)
}

const highlightKeyword = (text) => {
  if (!text || !searchForm.value.keyword) return text
  const kw = searchForm.value.keyword
  const regex = new RegExp(`(${kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return text.replace(regex, '<mark>$1</mark>')
}

const handleSearch = () => {
  const start = performance.now()
  searched.value = true
  resultPage.value = 1
  searchTime.value = Math.round(performance.now() - start)
}

const handleReset = () => {
  searchForm.value = { keyword: '', publisher: '', taskId: '', dateRange: null, domain: '' }
  searched.value = false
}

// 解析图片URL：优先使用本地路径（若可访问），否则使用远程URL
const resolveImageUrl = (img) => {
  if (!img) return ''
  // local_path 是服务器路径，前端无法直接访问，优先使用 image_url
  if (img.image_url) return img.image_url
  if (img.local_path) return img.local_path
  return ''
}

// 查看内容详情，同时加载关联图片
const viewContent = (row) => {
  currentContent.value = row
  // 通过 webpage_id 关联查询同一网页下的所有图片
  currentContentImages.value = allImages.value.filter(img => img.webpage_id === row.webpage_id)
  contentDialogVisible.value = true
}

onMounted(async () => {
  try {
    const [contentsData, webpagesData, imagesData] = await Promise.all([
      getContents(),
      getWebpages(),
      getImages()
    ])
    allContents.value = contentsData
    allWebpages.value = webpagesData
    allImages.value = imagesData
  } catch {}
})
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.content-detail h3 {
  margin: 0 0 8px;
}
.content-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.content-body {
  white-space: pre-wrap;
  line-height: 1.8;
  max-height: 500px;
  overflow-y: auto;
}

/* 关联图片展示样式 */
.content-images {
  margin: 12px 0;
}
.images-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
  color: #303133;
}
.images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}
.image-item {
  cursor: pointer;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  overflow: hidden;
  transition: all 0.2s;
  background: #fafafa;
}
.image-item:hover {
  border-color: #409EFF;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.2);
  transform: translateY(-2px);
}
.image-thumb {
  width: 100%;
  height: 120px;
  display: block;
  background: #f5f7fa;
}
.image-error,
.image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #c0c4cc;
  gap: 4px;
  font-size: 12px;
}
.image-error .el-icon,
.image-placeholder .el-icon {
  font-size: 24px;
}
.image-desc {
  padding: 6px 8px;
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  border-top: 1px solid #f0f0f0;
}
.no-images {
  margin: 12px 0;
}
</style>

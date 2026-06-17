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
          <el-table-column prop="crawled_at" label="爬取时间" width="170">
            <template #default="{ row }">{{ formatTime(row.crawled_at) }}</template>
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
          <el-button :icon="Refresh" @click="loadContents">刷新</el-button>
          <el-tag type="info">共 {{ contents.length }} 条</el-tag>
        </div>
        <el-table :data="paginatedContents" stripe style="width: 100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="Title" label="标题" width="200" show-overflow-tooltip />
          <el-table-column prop="text_body" label="正文预览" min-width="300" show-overflow-tooltip>
            <template #default="{ row }">{{ (row.text_body || '').substring(0, 150) }}...</template>
          </el-table-column>
          <el-table-column prop="webpage_id" label="网页ID" width="80" />
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button size="small" :icon="View" @click="viewContent(row)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="contentPage"
          :page-size="pageSize"
          :total="contents.length"
          layout="prev, pager, next"
          style="margin-top: 12px; justify-content: center;"
        />
      </el-tab-pane>

      <!-- 图片数据 -->
      <el-tab-pane label="图片数据" name="image">
        <div class="tab-header">
          <el-button :icon="Refresh" @click="loadImages">刷新</el-button>
          <el-tag type="info">共 {{ images.length }} 条</el-tag>
        </div>
        <el-table :data="paginatedImages" stripe style="width: 100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="image_url" label="图片URL" min-width="250" show-overflow-tooltip />
          <el-table-column prop="local_path" label="本地路径" width="200" show-overflow-tooltip />
          <el-table-column prop="description" label="描述" width="150" show-overflow-tooltip />
          <el-table-column prop="webpage_id" label="网页ID" width="80" />
        </el-table>
        <el-pagination
          v-model:current-page="imagePage"
          :page-size="pageSize"
          :total="images.length"
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getWebpages, getContents, getImages } from '../api'

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

const formatTime = (t) => {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

const paginatedWebpages = computed(() => {
  const start = (webpagePage.value - 1) * pageSize
  return webpages.value.slice(start, start + pageSize)
})
const paginatedContents = computed(() => {
  const start = (contentPage.value - 1) * pageSize
  return contents.value.slice(start, start + pageSize)
})
const paginatedImages = computed(() => {
  const start = (imagePage.value - 1) * pageSize
  return images.value.slice(start, start + pageSize)
})

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
.content-detail h3 {
  margin: 0 0 8px;
}
.content-body {
  white-space: pre-wrap;
  line-height: 1.8;
  max-height: 500px;
  overflow-y: auto;
}
</style>

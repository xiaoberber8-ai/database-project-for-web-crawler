import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

// 策略管理
export const getStrategies = () => api.get('/strategies')
export const getStrategy = (id) => api.get(`/strategies/${id}`)
export const createStrategy = (data) => api.post('/strategies', data)
export const updateStrategy = (id, data) => api.put(`/strategies/${id}`, data)
export const deleteStrategy = (id) => api.delete(`/strategies/${id}`)

// 爬虫控制
export const startCrawl = (strategyId) => api.post('/crawl/start', { strategy_id: strategyId })
export const pauseCrawl = () => api.post('/crawl/pause')
export const resumeCrawl = () => api.post('/crawl/resume')
export const stopCrawl = () => api.post('/crawl/stop')
export const getCrawlStatus = () => api.get('/crawl/status')

// 任务查询
export const getTasks = (strategyId) => api.get('/tasks', { params: { strategy_id: strategyId } })
export const getTask = (id) => api.get(`/tasks/${id}`)

// 数据查询 - 通过数据代理服务查询
const dataApi = axios.create({
  baseURL: '/data-api',
  timeout: 30000
})

dataApi.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export const getWebpages = () => dataApi.get('/webpages')
export const getContents = () => dataApi.get('/contents')
export const getImages = () => dataApi.get('/images')
export const getWebsites = () => dataApi.get('/websites')

export default api

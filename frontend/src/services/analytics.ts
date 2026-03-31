import { api } from './api'
import type { ROI, AnalyticsSummary } from '@/types'

interface CreateROIData {
  camera_id: string
  name: string
  ia_type: string
  polygon_points: number[][]
  config?: Record<string, unknown>
}

interface UpdateROIData {
  name?: string
  ia_type?: string
  polygon_points?: number[][]
  config?: Record<string, unknown>
  is_active?: boolean
}

interface ListROIsParams {
  camera_id?: string
}

interface SummaryParams {
  hours?: number
  camera_id?: string
}

interface ROIEventsParams {
  page?: number
  page_size?: number
}

export const analyticsService = {
  async listROIs(cameraId?: string): Promise<ROI[]> {
    const params: ListROIsParams = {}
    if (cameraId) params.camera_id = cameraId
    const res = await api.get<ROI[]>('/analytics/rois', { params })
    return res.data
  },

  async createROI(data: CreateROIData): Promise<ROI> {
    const res = await api.post<ROI>('/analytics/rois', data)
    return res.data
  },

  async updateROI(id: string, data: UpdateROIData): Promise<ROI> {
    const res = await api.patch<ROI>(`/analytics/rois/${id}`, data)
    return res.data
  },

  async deleteROI(id: string): Promise<void> {
    await api.delete(`/analytics/rois/${id}`)
  },

  async roiEvents(roiId: string, params?: ROIEventsParams): Promise<unknown> {
    const res = await api.get(`/analytics/rois/${roiId}/events`, { params })
    return res.data
  },

  async summary(params?: SummaryParams): Promise<AnalyticsSummary> {
    const res = await api.get<AnalyticsSummary>('/analytics/summary', { params })
    return res.data
  },
}

import { api } from './api'
import type { Camera, StreamUrls, RtmpConfig } from '@/types'

interface ListCamerasParams {
  page?: number
  page_size?: number
  search?: string
}

interface CreateCameraData {
  name: string
  location?: string
  manufacturer?: string
  retention_days?: number
  stream_protocol: string
  rtsp_url?: string
  agent_id?: string
  onvif_url?: string
  onvif_username?: string
  onvif_password?: string
}

interface UpdateCameraData {
  name?: string
  location?: string
  rtsp_url?: string
  onvif_url?: string
  onvif_username?: string
  onvif_password?: string
  manufacturer?: string
  retention_days?: number
  agent_id?: string
  is_active?: boolean
}

export const camerasService = {
  async list(params?: ListCamerasParams): Promise<Camera[]> {
    const res = await api.get<Camera[]>('/cameras', { params })
    return res.data
  },

  async get(id: string): Promise<Camera> {
    const res = await api.get<Camera>(`/cameras/${id}`)
    return res.data
  },

  async create(data: CreateCameraData): Promise<Camera> {
    const res = await api.post<Camera>('/cameras', data)
    return res.data
  },

  async update(id: string, data: UpdateCameraData): Promise<Camera> {
    const res = await api.patch<Camera>(`/cameras/${id}`, data)
    return res.data
  },

  async del(id: string): Promise<void> {
    await api.delete(`/cameras/${id}`)
  },

  async streamUrls(id: string): Promise<StreamUrls> {
    const res = await api.get<StreamUrls>(`/cameras/${id}/stream-urls`)
    return res.data
  },

  async snapshot(id: string): Promise<Blob> {
    const res = await api.get(`/cameras/${id}/snapshot`, { responseType: 'blob' })
    return res.data
  },

  async rtmpConfig(id: string): Promise<RtmpConfig> {
    const res = await api.get<RtmpConfig>(`/cameras/${id}/rtmp-config`)
    return res.data
  },

  async onvifProbe(data: { onvif_url: string; username: string; password: string }): Promise<unknown> {
    const res = await api.post('/cameras/onvif-probe', data)
    return res.data
  },

  async discover(data: { subnet: string }): Promise<unknown> {
    const res = await api.post('/cameras/discover', data)
    return res.data
  },
}

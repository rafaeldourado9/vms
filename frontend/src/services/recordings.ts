import { api } from './api'
import type { RecordingSegment, Clip, TimelineHour } from '@/types'

interface ListSegmentsParams {
  camera_id: string
  started_after?: string
  started_before?: string
  page?: number
  page_size?: number
}

interface ListClipsParams {
  camera_id?: string
  page?: number
  page_size?: number
}

interface CreateClipData {
  camera_id: string
  name: string
  started_at: string
  ended_at: string
}

interface SegmentListResponse {
  items: RecordingSegment[]
  total: number
  page: number
  page_size: number
  pages: number
}

interface ClipListResponse {
  items: Clip[]
  total: number
  page: number
  page_size: number
  pages: number
}

export const recordingsService = {
  async listSegments(params: ListSegmentsParams): Promise<SegmentListResponse> {
    const res = await api.get<SegmentListResponse>('/recordings', { params })
    return res.data
  },

  async timeline(cameraId: string, params?: { date?: string }): Promise<TimelineHour[]> {
    const res = await api.get<TimelineHour[]>(`/cameras/${cameraId}/timeline`, { params })
    return res.data
  },

  async createClip(data: CreateClipData): Promise<Clip> {
    const res = await api.post<Clip>('/recordings/clips', data)
    return res.data
  },

  async getClip(id: string): Promise<Clip> {
    const res = await api.get<Clip>(`/recordings/clips/${id}`)
    return res.data
  },

  async listClips(params?: ListClipsParams): Promise<ClipListResponse> {
    const res = await api.get<ClipListResponse>('/recordings/clips', { params })
    return res.data
  },
}

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
  starts_at: string
  ends_at: string
  vms_event_id?: string
}

export interface VerifyIntegrityResult {
  verified: boolean
  reason?: string
  stored_hash: string | null
  current_hash: string | null
  verified_at: string
}

export interface CustodyChainEntry {
  action: string
  timestamp: string
  actor: string
  user_email?: string
  file_path?: string
  zip_size_bytes?: number
  hmac_signature?: string
}

export interface CustodyChainResult {
  recording_id: string
  tenant_id: string
  custody_chain: CustodyChainEntry[]
  total_entries: number
}

export interface ForensicExportResult {
  recording_id: string
  exported_at: string
  exported_by: string
  file_path: string
  download_url: string
  zip_size_bytes: number
  sha256_hash: string
  hmac_signature: string
  integrity_verified: boolean
}

export const recordingsService = {
  async listSegments(params: ListSegmentsParams): Promise<{ items: RecordingSegment[]; total: number; page: number; page_size: number }> {
    const { data } = await api.get('/recordings', { params })
    return data
  },

  async getTimeline(camera_id: string, started_after?: string, started_before?: string): Promise<TimelineHour[]> {
    const { data } = await api.get(`/cameras/${camera_id}/timeline`, {
      params: { started_after, started_before },
    })
    return data
  },

  async download(recordingId: string): Promise<{ download_url: string; file_path: string }> {
    const { data } = await api.get(`/recordings/${recordingId}/download`)
    return data
  },

  async listClips(params: ListClipsParams = {}): Promise<{ items: Clip[]; total: number; page: number; page_size: number }> {
    const { data } = await api.get('/recordings/clips', { params })
    return data
  },

  async getClip(clipId: string): Promise<Clip> {
    const { data } = await api.get(`/recordings/clips/${clipId}`)
    return data
  },

  async createClip(data: CreateClipData): Promise<Clip> {
    const { data: clip } = await api.post('/recordings/clips', data)
    return clip
  },

  // ── Cadeia de Custódia ───────────────────────────────────────────

  async verifyIntegrity(recordingId: string): Promise<VerifyIntegrityResult> {
    const { data } = await api.get(`/recordings/${recordingId}/verify-integrity`)
    return data
  },

  async getCustodyChain(recordingId: string): Promise<CustodyChainResult> {
    const { data } = await api.get(`/recordings/${recordingId}/custody-chain`)
    return data
  },

  async exportForensic(recordingId: string): Promise<ForensicExportResult> {
    const { data } = await api.post(`/recordings/${recordingId}/export-forensic`)
    return data
  },

  /**
   * Cria path temporário no MediaMTX para streaming HLS de um segmento.
   * O MediaMTX lê o MP4 e serve como HLS (remux, sem reencoding).
   * Path expira automaticamente em 1h de ociosidade.
   */
  async prepareHls(recordingId: string): Promise<{
    hls_url: string
    path_name: string
    recording_id: string
    camera_id: string
    started_at: string
    duration_seconds: number
  }> {
    const { data } = await api.post(`/recordings/${recordingId}/hls`)
    return data
  },

  /**
   * URL HLS única cobrindo toda a janela gravada de um dia.
   * MediaMTX costura os segmentos fMP4 em um m3u8 linear — player
   * não recarrega a cada 60s. Retorna também intervals para a UI
   * renderizar gaps na barra de progresso.
   */
  async getDayHls(cameraId: string, date: string): Promise<{
    hls_url: string
    path_name: string
    camera_id: string
    started_at: string
    ended_at: string
    window_seconds: number
    intervals: Array<{
      id: string
      started_at: string
      ended_at: string
      duration_seconds: number
    }>
  }> {
    const { data } = await api.get(`/cameras/${cameraId}/recordings/day-hls`, {
      params: { date },
    })
    return data
  },

  /** Remove o path temporário do MediaMTX (cleanup imediato). */
  async removeHls(recordingId: string): Promise<void> {
    await api.delete(`/recordings/${recordingId}/hls`)
  },
}

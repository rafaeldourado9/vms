import { api } from './api'

export interface VODStream {
  id: string
  tenant_id: string
  camera_id: string
  started_at: string
  ended_at: string
  playlist_path: string
  status: 'pending' | 'generating' | 'ready' | 'failed'
  error: string | null
  created_at: string
}

export interface VODPlaylistURL {
  playlist_url: string
  status: string
  stream_id: string
}

export interface CreateVODStreamRequest {
  camera_id: string
  segment_ids: string[]
  starts_at: string
  ends_at: string
}

export const vodService = {
  /**
   * Cria stream VOD a partir de segmentos de gravação
   */
  async createStream(data: CreateVODStreamRequest): Promise<VODStream> {
    const res = await api.post<VODStream>('/vod/streams', data)
    return res.data
  },

  /**
   * Obtém status de um stream VOD (para polling)
   */
  async getStream(streamId: string): Promise<VODStream> {
    const res = await api.get<VODStream>(`/vod/streams/${streamId}`)
    return res.data
  },

  /**
   * Obtém URL da playlist HLS para streaming
   */
  async getPlaylistUrl(streamId: string): Promise<VODPlaylistURL> {
    const res = await api.get<VODPlaylistURL>(`/vod/streams/${streamId}/playlist`)
    return res.data
  },

  /**
   * Lista streams VOD
   */
  async listStreams(params?: {
    camera_id?: string
    status_filter?: string
  }): Promise<VODStream[]> {
    const res = await api.get<VODStream[]>('/vod/streams', { params })
    return res.data
  },

  /**
   * Remove stream VOD
   */
  async deleteStream(streamId: string): Promise<void> {
    await api.delete(`/vod/streams/${streamId}`)
  },

  /**
   * Aguarda stream ficar pronto (polling)
   * Timeout padrão: 30 segundos
   */
  async waitForReady(streamId: string, timeoutMs: number = 30000): Promise<string> {
    const startTime = Date.now()
    const pollInterval = 1000 // 1 segundo

    while (Date.now() - startTime < timeoutMs) {
      const stream = await this.getStream(streamId)

      if (stream.status === 'ready') {
        const playlist = await this.getPlaylistUrl(streamId)
        return playlist.playlist_url
      }

      if (stream.status === 'failed') {
        throw new Error(`Falha ao gerar stream: ${stream.error}`)
      }

      // Aguarda próxima verificação
      await new Promise((resolve) => setTimeout(resolve, pollInterval))
    }

    throw new Error('Timeout aguardando stream VOD ficar pronto')
  },
}

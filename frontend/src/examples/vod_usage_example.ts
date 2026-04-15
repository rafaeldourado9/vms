/**
 * Exemplo de uso do serviço VOD
 * 
 * Este arquivo demonstra como criar e consumir streams VOD
 * para playback eficiente de gravações.
 */

import { vodService } from '@/services/vod'
import { recordingsService } from '@/services/recordings'

/**
 * Exemplo 1: Criar stream VOD de um único segmento
 */
async function exemploSimples() {
  // 1. Lista segmentos disponíveis
  const segmentos = await recordingsService.listSegments({
    camera_id: 'cam-123',
    started_after: '2026-04-12T00:00:00Z',
    started_before: '2026-04-12T23:59:59Z',
  })

  if (segmentos.items.length === 0) {
    console.log('Nenhum segmento encontrado')
    return
  }

  // 2. Pega o primeiro segmento
  const primeiroSegmento = segmentos.items[0]

  // 3. Cria stream VOD
  const stream = await vodService.createStream({
    camera_id: 'cam-123',
    segment_ids: [primeiroSegmento.id],
    starts_at: primeiroSegmento.started_at,
    ends_at: primeiroSegmento.ended_at,
  })

  console.log('Stream criado:', stream.id)
  console.log('Status:', stream.status) // "pending"

  // 4. Aguarda ficar pronto (polling automático)
  const playlistUrl = await vodService.waitForReady(stream.id, 30000)

  console.log('Playlist URL:', playlistUrl)
  // → "/vod-streams/tenant-1/cam-123/stream-id/playlist.m3u8"

  return playlistUrl
}

/**
 * Exemplo 2: Criar stream VOD de múltiplos segmentos (ex: 1 hora de gravação)
 */
async function exemploMultiploSegmentos() {
  // 1. Lista todos os segmentos de uma hora
  const segmentos = await recordingsService.listSegments({
    camera_id: 'cam-123',
    started_after: '2026-04-12T10:00:00Z',
    started_before: '2026-04-12T11:00:00Z',
    page_size: 500,
  })

  console.log(`Encontrados ${segmentos.items.length} segmentos`)

  if (segmentos.items.length === 0) {
    return
  }

  // 2. Ordena por tempo
  const segmentosOrdenados = segmentos.items.sort(
    (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
  )

  // 3. Cria stream VOD com todos os segmentos
  const stream = await vodService.createStream({
    camera_id: 'cam-123',
    segment_ids: segmentosOrdenados.map(s => s.id),
    starts_at: segmentosOrdenados[0].started_at,
    ends_at: segmentosOrdenados[segmentosOrdenados.length - 1].ended_at,
  })

  console.log('Stream criado com', segmentosOrdenados.length, 'segmentos')

  // 4. Aguarda processamento (pode demorar mais para muitos segmentos)
  const playlistUrl = await vodService.waitForReady(stream.id, 60000) // 60s timeout

  console.log('Stream pronto:', playlistUrl)

  return playlistUrl
}

/**
 * Exemplo 3: Criar clipe de evento específico
 */
async function exemploClipDeEvento(_eventId: string, cameraId: string) {
  // 1. Encontra segmentos próximos ao evento (ex: ±5 minutos)
  const segmentos = await recordingsService.listSegments({
    camera_id: cameraId,
    page_size: 500,
  })

  // Filtra segmentos em janela de tempo do evento
  // (lógica simplificada - na prática viria do evento)
  const segmentosDoEvento = segmentos.items.slice(0, 3) // ex: 3 segmentos

  if (segmentosDoEvento.length === 0) {
    console.log('Nenhum segmento encontrado para o evento')
    return
  }

  // 2. Cria stream VOD do evento
  const stream = await vodService.createStream({
    camera_id: cameraId,
    segment_ids: segmentosDoEvento.map(s => s.id),
    starts_at: segmentosDoEvento[0].started_at,
    ends_at: segmentosDoEvento[segmentosDoEvento.length - 1].ended_at,
  })

  // 3. Aguarda ficar pronto
  const playlistUrl = await vodService.waitForReady(stream.id)

  console.log('Clip do evento pronto:', playlistUrl)

  return {
    streamId: stream.id,
    playlistUrl,
    segmentCount: segmentosDoEvento.length,
  }
}

/**
 * Exemplo 4: Listar todos os streams VOD de uma câmera
 */
async function listarStreams(cameraId?: string) {
  const streams = await vodService.listStreams({
    camera_id: cameraId,
    // status_filter: 'ready', // opcional: filtrar por status
  })

  console.log(`Encontrados ${streams.length} streams VOD`)

  streams.forEach(stream => {
    console.log(`- ${stream.id}: ${stream.status} (${stream.started_at} → ${stream.ended_at})`)
  })

  return streams
}

/**
 * Exemplo 5: Cleanup - remover streams antigos
 */
async function cleanupStreams() {
  const streams = await vodService.listStreams()

  // Remove streams com mais de 7 dias
  const seteDiasAtras = new Date()
  seteDiasAtras.setDate(seteDiasAtras.getDate() - 7)

  let removidos = 0
  for (const stream of streams) {
    if (new Date(stream.created_at) < seteDiasAtras) {
      await vodService.deleteStream(stream.id)
      removidos++
      console.log(`Stream removido: ${stream.id}`)
    }
  }

  console.log(`Cleanup concluído: ${removidos} streams removidos`)
}

/**
 * Exemplo 6: Uso com componente React
 */
// @ts-ignore - Apenas exemplo documental
function ExemploComponent() {
  // Usando o componente RecordingPlayer (veja RecordingsPage.tsx)
  return `
    <RecordingPlayer
      segmentIds={['seg-1', 'seg-2', 'seg-3']}
      cameraId="cam-123"
      startsAt="2026-04-12T10:00:00Z"
      endsAt="2026-04-12T10:03:00Z"
      className="w-full h-full"
      onReady={() => console.log('Stream pronto!')}
      onError={(err) => console.error('Erro:', err)}
    />
  `
}

// Exporta funções de exemplo
export {
  exemploSimples,
  exemploMultiploSegmentos,
  exemploClipDeEvento,
  listarStreams,
  cleanupStreams,
}

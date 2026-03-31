// ─── Auth ────────────────────────────────────────────────────────────────────

export type UserRole = 'admin' | 'operator' | 'viewer'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  tenant_id: string
  is_active: boolean
  created_at: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

// ─── Tenant ──────────────────────────────────────────────────────────────────

export interface Tenant {
  id: string
  name: string
  slug: string
  is_active: boolean
  created_at: string
}

// ─── Camera ──────────────────────────────────────────────────────────────────

export type StreamProtocol = 'rtsp_pull' | 'rtmp_push' | 'onvif'

export type CameraManufacturer = 'generic' | 'hikvision' | 'intelbras' | 'axis' | 'dahua'

export interface Camera {
  id: string
  tenant_id: string
  name: string
  location: string | null
  stream_protocol: StreamProtocol
  rtsp_url: string | null
  rtmp_stream_key: string | null
  onvif_url: string | null
  onvif_username: string | null
  manufacturer: string
  retention_days: number
  is_active: boolean
  is_online: boolean
  agent_id: string | null
  last_seen_at: string | null
  created_at: string
}

export interface StreamUrls {
  hls_url: string
  webrtc_url: string
  rtsp_url: string | null
  token: string
  expires_at: string
}

export interface RtmpConfig {
  rtmp_url: string
  stream_key: string
}

// ─── Agent ───────────────────────────────────────────────────────────────────

export type AgentStatus = 'online' | 'offline' | 'unknown'

export interface Agent {
  id: string
  tenant_id: string
  name: string
  is_active: boolean
  last_heartbeat_at: string | null
  created_at: string
}

export interface AgentConfig {
  agent_id: string
  cameras: CameraConfigItem[]
}

export interface CameraConfigItem {
  id: string
  name: string
  rtsp_url: string
  stream_path: string
}

// ─── ROI ─────────────────────────────────────────────────────────────────────

export type ROIType =
  | 'intrusion'
  | 'people_count'
  | 'vehicle_count'
  | 'lpr_parking'
  | 'weapon_detection'
  | 'face_recognition'
  | 'vehicle_dwell'

export interface ROI {
  id: string
  tenant_id: string
  camera_id: string
  name: string
  ia_type: ROIType
  polygon_points: number[][]
  config: Record<string, unknown>
  is_active: boolean
  created_at: string
}

// ─── Events ──────────────────────────────────────────────────────────────────

export interface VmsEvent {
  id: string
  tenant_id: string
  camera_id: string
  event_type: string
  plate: string | null
  manufacturer: string | null
  raw_payload: Record<string, unknown>
  deduplicated: boolean
  occurred_at: string
  created_at: string
}

// ─── Recordings ──────────────────────────────────────────────────────────────

export interface RecordingSegment {
  id: string
  tenant_id: string
  camera_id: string
  file_path: string
  started_at: string
  ended_at: string
  duration_seconds: number
  file_size_bytes: number
  created_at: string
}

export interface TimelineHour {
  hour: number
  coverage_pct: number
  segment_count: number
}

export interface Clip {
  id: string
  tenant_id: string
  camera_id: string
  name: string
  started_at: string
  ended_at: string
  status: 'pending' | 'processing' | 'ready' | 'error'
  file_path: string | null
  created_at: string
}

// ─── Notifications ───────────────────────────────────────────────────────────

export interface NotificationRule {
  id: string
  tenant_id: string
  name: string
  event_type_pattern: string
  destination_url: string
  is_active: boolean
  created_at: string
}

export interface NotificationLog {
  id: string
  tenant_id: string
  rule_id: string
  event_id: string
  destination_url: string
  status_code: number | null
  attempt_count: number
  last_error: string | null
  sent_at: string | null
  created_at: string
}

// ─── Analytics ───────────────────────────────────────────────────────────────

export interface AnalyticsSummary {
  tenant_id: string
  period_hours: number
  total_events: number
  by_type: Record<string, number>
  by_camera: Record<string, number>
}

// ─── Pagination ──────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

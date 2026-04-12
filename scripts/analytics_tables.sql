-- Analytics tables migration
-- Run: psql -U vms -d vms -f analytics_tables.sql

-- Plugin installations table
CREATE TABLE IF NOT EXISTS plugin_installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plugin_id VARCHAR(50) NOT NULL,
    plugin_name VARCHAR(100) NOT NULL,
    version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    edge_agent_id VARCHAR(100) NOT NULL,
    tenant_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'installed',
    settings JSONB NOT NULL DEFAULT '{}',
    model_path VARCHAR(500),
    fps_target INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_plugin_installations_tenant ON plugin_installations(tenant_id);
CREATE INDEX idx_plugin_installations_plugin_id ON plugin_installations(plugin_id);
CREATE INDEX idx_plugin_installations_edge_agent ON plugin_installations(edge_agent_id);
CREATE INDEX idx_plugin_installations_status ON plugin_installations(status);

-- Analytics events table
CREATE TABLE IF NOT EXISTS analytics_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plugin_installation_id UUID REFERENCES plugin_installations(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL,
    camera_id VARCHAR(100) NOT NULL,
    camera_name VARCHAR(200),
    plugin_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'info',
    confidence FLOAT,
    payload JSONB NOT NULL DEFAULT '{}',
    snapshot_path VARCHAR(500),
    occurred_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_analytics_events_tenant ON analytics_events(tenant_id);
CREATE INDEX idx_analytics_events_camera ON analytics_events(camera_id);
CREATE INDEX idx_analytics_events_plugin ON analytics_events(plugin_id);
CREATE INDEX idx_analytics_events_event_type ON analytics_events(event_type);
CREATE INDEX idx_analytics_events_severity ON analytics_events(severity);
CREATE INDEX idx_analytics_events_occurred ON analytics_events(occurred_at DESC);

import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { Layout } from '@/components/layout/Layout'
import { useAuthStore } from '@/store/authStore'
import { OnboardingWizard } from '@/components/wizard/OnboardingWizard'
import { useOnboarding } from '@/hooks/useOnboarding'

import { LoginPage }           from '@/pages/LoginPage'
import { DashboardPage }       from '@/pages/DashboardPage'
import { CamerasPage }         from '@/pages/CamerasPage'
import { CameraDetailPage }    from '@/pages/CameraDetailPage'
import { MosaicPage }          from '@/pages/MosaicPage'
import { RecordingsPage }      from '@/pages/RecordingsPage'
import { EventsPage }          from '@/pages/EventsPage'
import { NotificationsPage }   from '@/pages/NotificationsPage'
import { UsersPage }           from '@/pages/UsersPage'
import { SettingsPage }        from '@/pages/SettingsPage'
import { ROIManagementPage }    from '@/pages/ROIManagementPage'
import { TacticalViewPage }    from '@/pages/TacticalViewPage'
import { ReportsPage }         from '@/pages/ReportsPage'
import { AuditPage }           from '@/pages/AuditPage'
import { BillingPage }         from '@/pages/BillingPage'
import { LGPDPage }            from '@/pages/LGPDPage'
import { SystemHealthPage }    from '@/pages/SystemHealthPage'
import { AnalyticsDashboardPage } from '@/pages/AnalyticsDashboardPage'
import { AgentsPage }          from '@/pages/AgentsPage'

// ─── Proteções de segurança no frontend ───────────────────────────────────────

// Desabilitar menu de contexto em produção (previne inspeção casual)
if (import.meta.env.PROD) {
  // Desabilitar atalhos de devtools
  document.addEventListener('keydown', (e) => {
    // F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+U
    if (
      e.key === 'F12' ||
      (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'J')) ||
      (e.ctrlKey && e.key === 'U')
    ) {
      e.preventDefault()
    }
  })
}

function RequireAuth() {
  const { isAuthenticated } = useAuthStore()
  if (!isAuthenticated()) return <Navigate to="/login" replace />
  return <Outlet />
}

function AuthenticatedApp() {
  const { complete, markComplete } = useOnboarding()

  if (!complete) {
    return <OnboardingWizard onComplete={markComplete} />
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard"     element={<DashboardPage />} />
        <Route path="/cameras"       element={<CamerasPage />} />
        <Route path="/cameras/:id"   element={<CameraDetailPage />} />
        <Route path="/mosaic"        element={<MosaicPage />} />
        <Route path="/tactical"      element={<TacticalViewPage />} />
        <Route path="/recordings"    element={<RecordingsPage />} />
        <Route path="/events"        element={<EventsPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/analytics"     element={<ROIManagementPage />} />
        <Route path="/analytics-dashboard" element={<AnalyticsDashboardPage />} />
        <Route path="/agents"        element={<AgentsPage />} />
        <Route path="/reports"       element={<ReportsPage />} />
        <Route path="/audit"         element={<AuditPage />} />
        <Route path="/billing"       element={<BillingPage />} />
        <Route path="/lgpd"          element={<LGPDPage />} />
        <Route path="/health"        element={<SystemHealthPage />} />
        <Route path="/users"         element={<UsersPage />} />
        <Route path="/settings"      element={<SettingsPage />} />
        <Route path="*"              element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background:   'var(--surface)',
            color:        'var(--text-1)',
            border:       '1px solid var(--border)',
            borderRadius: '10px',
            fontSize:     '13px',
          },
          success: { iconTheme: { primary: '#22C55E', secondary: '#111118' } },
          error:   { iconTheme: { primary: '#EF4444', secondary: '#111118' } },
          duration: 3000,
        }}
      />
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route element={<RequireAuth />}>
          <Route path="/*" element={<AuthenticatedApp />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

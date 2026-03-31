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
import { ROIEditorPage }       from '@/pages/ROIEditorPage'
import { MosaicPage }          from '@/pages/MosaicPage'
import { RecordingsPage }      from '@/pages/RecordingsPage'
import { EventsPage }          from '@/pages/EventsPage'
import { AnalyticsPage }       from '@/pages/AnalyticsPage'
import { AgentsPage }          from '@/pages/AgentsPage'
import { NotificationsPage }   from '@/pages/NotificationsPage'
import { UsersPage }           from '@/pages/UsersPage'
import { SettingsPage }        from '@/pages/SettingsPage'

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
        <Route path="/cameras/:id/roi" element={<ROIEditorPage />} />
        <Route path="/mosaic"        element={<MosaicPage />} />
        <Route path="/recordings"    element={<RecordingsPage />} />
        <Route path="/events"        element={<EventsPage />} />
        <Route path="/analytics"     element={<AnalyticsPage />} />
        <Route path="/agents"        element={<AgentsPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/users"         element={<UsersPage />} />
        <Route path="/settings"      element={<SettingsPage />} />
        <Route path="*"              element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
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

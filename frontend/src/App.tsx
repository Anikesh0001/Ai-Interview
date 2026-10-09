import { Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/Layout'
import { HealthProvider } from './components/HealthContext'
import Landing from './pages/Landing'
import DashboardPage from './pages/Dashboard'
import ResumePage from './pages/Resume'
import InterviewSetup from './pages/InterviewSetup'
import InterviewRoom from './pages/InterviewRoom'
import ReportPage from './pages/Report'
import HistoryPage from './pages/History'
import SettingsPage from './pages/Settings'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <HealthProvider>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/resume" element={<ResumePage />} />
          <Route path="/interview/setup" element={<InterviewSetup />} />
          <Route path="/interview/:id" element={<InterviewRoom />} />
          <Route path="/interview/:id/report" element={<ReportPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </HealthProvider>
  )
}

import { Routes, Route, Navigate } from 'react-router-dom'
import { AppProvider } from './hooks/useAppState'
import BottomNav from './components/common/BottomNav'
import DiscoverPage from './pages/DiscoverPage'
import MatchesPage from './pages/MatchesPage'
import ChatPage from './pages/ChatPage'
import ProfilePage from './pages/ProfilePage'
import './App.css'

function App() {
  return (
    <AppProvider>
      <div className="app-shell">
        <main className="app-content">
          <Routes>
            <Route path="/" element={<Navigate to="/discover" replace />} />
            <Route path="/discover" element={<DiscoverPage />} />
            <Route path="/matches" element={<MatchesPage />} />
            <Route path="/chat/:matchId" element={<ChatPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Routes>
        </main>
        <BottomNav />
      </div>
    </AppProvider>
  )
}

export default App

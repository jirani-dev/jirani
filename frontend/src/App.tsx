import { ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Home from './pages/Home'
import Library from './pages/Library'
import Book from './pages/Book'
import Setup from './pages/Setup'

// Every library endpoint requires a signed-in account, so these pages have
// nothing to show a guest. This is navigation convenience, not access control:
// the API enforces the roles.
const RequireAuth = ({ children }: { children: ReactNode }) => {
    const { isGuest } = useAuth()
    return isGuest ? <Navigate to="/" replace /> : children
}

function App() {
    return (
        <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/library" element={<RequireAuth><Library /></RequireAuth>} />
            <Route path="/read/:uid" element={<RequireAuth><Book /></RequireAuth>} />
            <Route path="/setup" element={<Setup />} />
        </Routes>
    )
}

export default App

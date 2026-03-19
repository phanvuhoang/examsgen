import { useState, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Generate from './pages/Generate'
import QuestionBank from './pages/QuestionBank'
import Regulations from './pages/Regulations'
import Settings from './pages/Settings'

export default function App() {
  const [authed, setAuthed] = useState(!!localStorage.getItem('token'))

  useEffect(() => {
    const handler = () => setAuthed(!!localStorage.getItem('token'))
    window.addEventListener('storage', handler)
    return () => window.removeEventListener('storage', handler)
  }, [])

  if (!authed) {
    return <Login onLogin={() => setAuthed(true)} />
  }

  return (
    <Layout onLogout={() => { localStorage.removeItem('token'); setAuthed(false) }}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/generate" element={<Generate />} />
        <Route path="/bank" element={<QuestionBank />} />
        <Route path="/regulations" element={<Regulations />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/login" element={<Navigate to="/" />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Layout>
  )
}

import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import './styles.css'
import App from './App'
import Leads from './pages/Leads'
import Login from './pages/Login'

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <div className="container py-4">
        <header className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-semibold">Platsannonser – Kök & Servering</h1>
          <nav className="flex gap-3">
            <Link className="btn" to="/">Annonser</Link>
            <Link className="btn" to="/leads">Leads</Link>
            <Link className="btn" to="/login">Logga in</Link>
          </nav>
        </header>
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/leads" element={<Leads />} />
          <Route path="/login" element={<Login />} />
        </Routes>
      </div>
    </BrowserRouter>
  </React.StrictMode>
)

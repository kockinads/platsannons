import React, { useState } from 'react'
import { setAccessToken } from '../api'
import { useNavigate } from 'react-router-dom'

export default function Login(){
  const [token, setToken] = useState('')
  const navigate = useNavigate()

  const submit = (e) => {
    e.preventDefault()
    if(!token) return
    setAccessToken(token)
    navigate('/')
  }

  return (
    <div className="card max-w-md mx-auto">
      <h2 className="text-xl font-semibold mb-2">Logga in</h2>
      <p className="text-sm text-gray-600 mb-3">Skriv åtkomstkoden du fått av administratören.</p>
      <form onSubmit={submit} className="space-y-3">
        <input className="input" type="password" placeholder="Åtkomstkod" value={token} onChange={e=>setToken(e.target.value)} />
        <button className="btn" type="submit">Fortsätt</button>
      </form>
      <p className="text-xs text-gray-500 mt-3">Tips: Om du fastnar på "Du är inte inloggad", gå hit och skriv koden igen.</p>
    </div>
  )
}

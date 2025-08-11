import React, { useEffect, useState } from 'react'
import { exportLeadsCSV, fetchLeads } from '../api'

export default function Leads() {
  const [tier, setTier] = useState('')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true); setError('')
    try { setItems(await fetchLeads({ tier })) } catch(e){ setError(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [tier])

  return (
    <div className="space-y-3">
      <div className="card flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span>Filter:</span>
          <select className="select" value={tier} onChange={e => setTier(e.target.value)}>
            <option value="">Alla</option>
            {['A','B','C','U'].map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <button className="btn" onClick={exportLeadsCSV}>Exportera CSV</button>
      </div>

      {error && <div className="card text-red-700">{error}</div>}
      <div className="grid gap-3">
        {loading && <div className="card">Laddar…</div>}
        {!loading && items.length===0 && !error && <div className="card">Inga sparade leads.</div>}
        {items.map(it => (
          <div key={it.id} className="card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="badge">{it.tier}</span>
                <span className="text-sm text-gray-600">Lead #{it.id}</span>
              </div>
              <span className="text-xs text-gray-500">Uppdaterad {new Date(it.updated_at).toLocaleString('sv-SE')}</span>
            </div>
            {it.notes && <p className="mt-1 text-sm">{it.notes}</p>}
          </div>
        ))}
      </div>
    </div>
  )
}

import React, { useState } from 'react'

export default function JobCard({ job, onSaveLead }) {
  const [tier, setTier] = useState('U')
  const [notes, setNotes] = useState('')

  const share = () => {
    const text = `${job.title} – ${job.employer} (${job.city})\n${job.url}`
    if (navigator.share) {
      navigator.share({ title: job.title, text, url: job.url })
    } else {
      const mailto = `mailto:?subject=${encodeURIComponent(job.title)}&body=${encodeURIComponent(text)}`
      window.location.href = mailto
    }
  }

  const copyLink = async () => {
    try { await navigator.clipboard.writeText(job.url); alert('Länk kopierad') } catch {}
  }

  const save = async () => {
    try {
      await onSaveLead(job.id, tier, notes)
      alert('Lead sparat')
    } catch (e) {
      alert(e.message || 'Kunde inte spara')
    }
  }

  const published = new Date(job.published_at).toLocaleDateString('sv-SE')

  return (
    <div className="card">
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold">{job.title}</h3>
            <span className="badge">{job.source}</span>
          </div>
          <div className="text-sm text-gray-600">{job.employer} · {job.city} · {published}</div>
          <p className="mt-2 text-sm line-clamp-3">{job.description?.slice(0, 180)}{job.description?.length>180?'…':''}</p>
          <a className="text-sm underline mt-1 inline-block" href={job.url} target="_blank" rel="noreferrer">Till originalannons →</a>
        </div>
        <div className="w-full md:w-64">
          <label className="block text-sm mb-1">Kundtyp A/B/C</label>
          <select className="select" value={tier} onChange={e => setTier(e.target.value)}>
            {['A','B','C','U'].map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <label className="block text-sm mt-2 mb-1">Anteckningar</label>
          <textarea className="input h-24" value={notes} onChange={e => setNotes(e.target.value)} placeholder="Egna noteringar" />
          <div className="flex gap-2 mt-2">
            <button className="btn" onClick={save}>Spara lead</button>
            <button className="btn" onClick={copyLink}>Kopiera länk</button>
            <button className="btn" onClick={share}>Dela</button>
          </div>
        </div>
      </div>
    </div>
  )
}

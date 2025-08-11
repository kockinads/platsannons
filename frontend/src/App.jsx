import React, { useEffect, useState } from 'react'
import { fetchJobs, saveLead } from './api'
import FilterBar from './components/FilterBar'
import JobCard from './components/JobCard'

export default function App() {
  const [filters, setFilters] = useState({ roles: [], region: '', city: '', hideRecruiters: true })
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true); setError('')
    try {
      const data = await fetchJobs(filters)
      setJobs(data)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [JSON.stringify(filters)])

  const handleSaveLead = async (jobId, tier, notes) => {
    return saveLead({ job_id: jobId, tier, notes })
  }

  return (
    <div className="space-y-4">
      <FilterBar value={filters} onChange={setFilters} onRefresh={load} />
      {loading && <div className="card">Laddar…</div>}
      {error && <div className="card text-red-700">{error}</div>}
      <div className="grid gap-3">
        {jobs.map(j => (
          <JobCard key={j.id} job={j} onSaveLead={handleSaveLead} />
        ))}
        {!loading && jobs.length === 0 && !error && <div className="card">Inga annonser hittades.</div>}
      </div>
    </div>
  )
}

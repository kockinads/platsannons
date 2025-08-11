// Single-URL: relativt API under samma domän
const API_BASE = ''

function authHeaders() {
  const token = localStorage.getItem('access_token') || ''
  const h = { }
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

export async function fetchJobs({ roles = [], region = '', city = '', hideRecruiters = false } = {}) {
  const params = new URLSearchParams()
  roles.forEach(r => params.append('roles', r))
  if (region) params.set('region', region)
  if (city) params.set('city', city)
  if (hideRecruiters) params.set('hide_recruiters', 'true')
  const res = await fetch(`${API_BASE}/api/jobs?${params.toString()}`, { headers: authHeaders() })
  if (res.status === 401) throw new Error('Du är inte inloggad. Gå till /login och skriv åtkomstkoden.')
  if (!res.ok) throw new Error('Kunde inte hämta jobb')
  return res.json()
}

export async function saveLead({ job_id, tier, notes }) {
  const res = await fetch(`${API_BASE}/api/leads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ job_id, tier, notes })
  })
  if (res.status === 401) throw new Error('Du är inte inloggad.')
  if (!res.ok) throw new Error('Kunde inte spara lead')
  return res.json()
}

export async function fetchLeads({ tier = '' } = {}) {
  const url = new URL(`${API_BASE}/api/leads`, window.location.origin)
  if (tier) url.searchParams.set('tier', tier)
  const res = await fetch(url, { headers: authHeaders() })
  if (res.status === 401) throw new Error('Du är inte inloggad.')
  if (!res.ok) throw new Error('Kunde inte hämta leads')
  return res.json()
}

export function exportLeadsCSV() {
  window.open(`/api/leads/export`, '_blank')
}

export function setAccessToken(token) {
  localStorage.setItem('access_token', token)
}

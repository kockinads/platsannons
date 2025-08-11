import React from 'react'

const ROLES = [
  'kock','köksbiträde','diskpersonal','serveringspersonal','bartender','roddare','hovmästare','köksmästare','souschef','1:e kock','1:e servis'
]

const REGIONS = [
  '', 'Stockholms län','Uppsala län','Södermanlands län','Östergötlands län','Jönköpings län','Kronobergs län','Kalmar län','Gotlands län','Blekinge län','Skåne län','Hallands län','Västra Götalands län','Värmlands län','Örebro län','Västmanlands län','Dalarnas län','Gävleborgs län','Västernorrlands län','Jämtlands län','Västerbottens län','Norrbottens län'
]

export default function FilterBar({ value, onChange, onRefresh }) {
  const set = (patch) => onChange({ ...value, ...patch })
  const toggleRole = (r) => {
    const has = value.roles.includes(r)
    set({ roles: has ? value.roles.filter(x => x !== r) : [...value.roles, r] })
  }

  return (
    <div className="card">
      <div className="grid gap-3 md:grid-cols-4">
        <div className="md:col-span-2">
          <label className="block text-sm mb-2">Yrkesroller</label>
          <div className="grid grid-cols-2 gap-2">
            {ROLES.map(r => (
              <label key={r} className="inline-flex items-center gap-2">
                <input type="checkbox" className="checkbox" checked={value.roles.includes(r)} onChange={() => toggleRole(r)} />
                <span>{r}</span>
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-sm mb-2">Län</label>
          <select className="select" value={value.region} onChange={e => set({ region: e.target.value })}>
            {REGIONS.map(r => <option key={r} value={r}>{r || 'Alla län'}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-2">Ort</label>
          <input className="input" placeholder="t.ex. Stockholm" value={value.city} onChange={e => set({ city: e.target.value })} />
        </div>
      </div>
      <div className="flex items-center justify-between mt-3">
        <label className="inline-flex items-center gap-2">
          <input type="checkbox" className="checkbox" checked={value.hideRecruiters} onChange={e => set({ hideRecruiters: e.target.checked })} />
          <span>Dölj annonser från rekryteringsföretag</span>
        </label>
        <button className="btn" onClick={onRefresh}>Uppdatera</button>
      </div>
    </div>
  )
}

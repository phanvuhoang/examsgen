import { useState, useEffect, useRef } from 'react'

export default function KBMultiSelect({ label, endpoint, value, onChange, displayKey, hintKey }) {
  const [items, setItems] = useState([])
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!endpoint) return
    const token = localStorage.getItem('token')
    fetch(endpoint, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => (r.ok ? r.json() : []))
      .then(setItems)
      .catch(() => setItems([]))
  }, [endpoint])

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = items.filter((item) => {
    if (value.includes(item.id)) return false
    if (!search) return true
    const s = search.toLowerCase()
    return (
      (item[displayKey] || '').toLowerCase().includes(s) ||
      (item[hintKey] || '').toLowerCase().includes(s) ||
      (item.content || '').toLowerCase().includes(s)
    )
  })

  const selectedItems = items.filter((item) => value.includes(item.id))

  return (
    <div className="mb-3" ref={ref}>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>

      {/* Selected tags */}
      {selectedItems.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {selectedItems.map((item) => (
            <span
              key={item.id}
              className="inline-flex items-center gap-1 bg-brand-50 text-brand-700 text-xs px-2 py-1 rounded-full border border-brand-200"
            >
              {item[displayKey] || item.content?.slice(0, 30) || `#${item.id}`}
              <button
                type="button"
                onClick={() => onChange(value.filter((id) => id !== item.id))}
                className="hover:text-red-500 font-bold"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Search + dropdown */}
      <div className="relative">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onFocus={() => setOpen(true)}
          placeholder={items.length ? `Search ${items.length} items...` : 'No items yet'}
          className="w-full border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
          disabled={items.length === 0}
        />
        {open && filtered.length > 0 && (
          <div className="absolute z-20 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-48 overflow-y-auto">
            {filtered.slice(0, 20).map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  onChange([...value, item.id])
                  setSearch('')
                }}
                className="w-full text-left px-3 py-2 hover:bg-brand-50 text-sm border-b last:border-0"
              >
                <span className="font-medium">
                  {item[displayKey] || item.content?.slice(0, 50) || `#${item.id}`}
                </span>
                {item[hintKey] && (
                  <span className="text-xs text-gray-400 ml-2">{item[hintKey]}</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

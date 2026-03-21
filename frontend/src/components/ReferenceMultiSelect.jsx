import { useState, useEffect, useRef, useCallback } from 'react'

function debounce(fn, delay) {
  let timer
  return (...args) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}

/**
 * Searchable multi-select for picking reference items.
 * Props:
 *   label: string
 *   placeholder: string
 *   fetchFn: async (query) => Item[]
 *   displayFn: (item) => string
 *   selected: string[] | number[]
 *   selectedItems: {id, label}[]  (for chip labels)
 *   onSelect: (item) => void
 *   onRemove: (id) => void
 */
export default function ReferenceMultiSelect({
  label,
  placeholder,
  fetchFn,
  displayFn,
  selected = [],
  onSelect,
  onRemove,
}) {
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [chipLabels, setChipLabels] = useState({}) // id -> label
  const containerRef = useRef(null)

  const doFetch = useCallback(
    debounce(async (q) => {
      if (!q) { setOptions([]); return }
      setLoading(true)
      try {
        const results = await fetchFn(q)
        setOptions(results || [])
        setOpen(true)
      } catch {
        setOptions([])
      } finally {
        setLoading(false)
      }
    }, 300),
    [fetchFn]
  )

  useEffect(() => {
    doFetch(query)
  }, [query])

  useEffect(() => {
    function handleClick(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function handleSelect(item) {
    const id = item.id ?? item.syllabus_code ?? item.reg_code
    setChipLabels((prev) => ({ ...prev, [id]: displayFn(item) }))
    onSelect(item)
    setQuery('')
    setOptions([])
    setOpen(false)
  }

  return (
    <div className="mb-3" ref={containerRef}>
      {label && <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>}
      {/* Selected chips */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1">
          {selected.map((id) => (
            <span key={id} className="inline-flex items-center gap-1 px-2 py-0.5 bg-brand-100 text-brand-700 text-xs rounded-full">
              <span className="max-w-[200px] truncate">{chipLabels[id] || String(id)}</span>
              <button onClick={() => onRemove(id)} className="hover:text-red-500 ml-0.5">×</button>
            </span>
          ))}
        </div>
      )}
      {/* Search input */}
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => query && setOpen(true)}
          placeholder={placeholder}
          className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand-400"
        />
        {loading && (
          <span className="absolute right-2 top-2 text-gray-400 text-xs">...</span>
        )}
        {/* Dropdown */}
        {open && options.length > 0 && (
          <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded shadow-lg max-h-48 overflow-y-auto">
            {options.map((item, i) => {
              const id = item.id ?? item.syllabus_code ?? item.reg_code
              const isSelected = selected.includes(id) || selected.includes(String(id))
              return (
                <button
                  key={i}
                  onClick={() => !isSelected && handleSelect(item)}
                  className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-50 border-b border-gray-100 last:border-0 ${isSelected ? 'opacity-40 cursor-default' : ''}`}
                >
                  {displayFn(item)}
                </button>
              )
            })}
          </div>
        )}
        {open && !loading && query && options.length === 0 && (
          <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded shadow-lg px-3 py-2 text-xs text-gray-400">
            No matches found
          </div>
        )}
      </div>
    </div>
  )
}

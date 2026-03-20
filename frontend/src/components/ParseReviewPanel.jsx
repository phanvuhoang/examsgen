import { useState } from 'react'
import { api } from '../api'

const SAC_THUE_OPTIONS = ['CIT', 'VAT', 'PIT', 'FCT', 'TP', 'ADMIN']

export default function ParseReviewPanel({ sessionId, onDone }) {
  const [fileType, setFileType] = useState('regulation')
  const [sacThue, setSacThue] = useState('CIT')
  const [filePath, setFilePath] = useState('')
  const [parsing, setParsing] = useState(false)
  const [chunks, setChunks] = useState(null)
  const [selected, setSelected] = useState(new Set())
  const [expanded, setExpanded] = useState(new Set())
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleParse = async () => {
    if (!filePath.trim()) return
    setParsing(true)
    setError('')
    setChunks(null)
    try {
      const result = await api.parseAndMatch(sessionId, {
        file_path: filePath,
        file_type: fileType,
        sac_thue: sacThue,
      })
      setChunks(result.chunks)
      setSelected(new Set(result.chunks.map((_, i) => i)))
    } catch (err) {
      setError('Parse failed: ' + err.message)
    } finally {
      setParsing(false)
    }
  }

  const toggleSelect = (idx) => {
    const next = new Set(selected)
    next.has(idx) ? next.delete(idx) : next.add(idx)
    setSelected(next)
  }

  const toggleAll = () => {
    if (selected.size === chunks.length) setSelected(new Set())
    else setSelected(new Set(chunks.map((_, i) => i)))
  }

  const toggleExpand = (idx) => {
    const next = new Set(expanded)
    next.has(idx) ? next.delete(idx) : next.add(idx)
    setExpanded(next)
  }

  const updateChunk = (idx, field, value) => {
    const updated = [...chunks]
    updated[idx] = { ...updated[idx], [field]: value }
    setChunks(updated)
  }

  const handleSave = async () => {
    const selectedChunks = chunks.filter((_, i) => selected.has(i))
    if (selectedChunks.length === 0) return
    setSaving(true)
    try {
      await api.saveParsedChunks(sessionId, {
        chunks: selectedChunks,
        file_type: fileType,
        sac_thue: sacThue,
        source_file: filePath,
      })
      alert(`Saved ${selectedChunks.length} chunks to Knowledge Base`)
      if (onDone) onDone()
    } catch (err) {
      setError('Save failed: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-white border rounded-xl p-5 mb-4">
      <h3 className="font-semibold mb-4">Parse & Match File</h3>

      {/* Config */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div>
          <label className="block text-xs font-medium mb-1">File Type</label>
          <select value={fileType} onChange={(e) => setFileType(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm">
            <option value="regulation">Regulation</option>
            <option value="syllabus">Syllabus</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium mb-1">Tax Type</label>
          <select value={sacThue} onChange={(e) => setSacThue(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm">
            {SAC_THUE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium mb-1">File Path (relative to data/)</label>
          <input value={filePath} onChange={(e) => setFilePath(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm"
            placeholder="e.g. regulations/CIT/CIT_Law_67.doc" />
        </div>
      </div>

      <button onClick={handleParse} disabled={parsing || !filePath.trim()}
        className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600 disabled:opacity-50 mb-4">
        {parsing ? 'Parsing with AI...' : 'Parse with AI'}
      </button>

      {error && <div className="text-red-600 text-sm mb-3">{error}</div>}

      {/* Review Panel */}
      {chunks && (
        <div>
          <div className="flex items-center justify-between mb-3 border-t pt-3">
            <div className="text-sm font-medium">
              Parse Results: {chunks.length} chunks found
            </div>
            <div className="flex gap-2">
              <button onClick={toggleAll} className="text-xs text-brand-600 hover:underline">
                {selected.size === chunks.length ? 'Deselect All' : 'Select All'}
              </button>
              <button onClick={handleSave} disabled={saving || selected.size === 0}
                className="px-3 py-1 bg-brand-500 text-white text-xs rounded-lg hover:bg-brand-600 disabled:opacity-50">
                {saving ? 'Saving...' : `Save ${selected.size} Selected to KB`}
              </button>
            </div>
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {chunks.map((chunk, i) => (
              <div key={i} className={`border rounded-lg p-3 ${selected.has(i) ? 'border-brand-300 bg-brand-50/30' : 'border-gray-200 opacity-60'}`}>
                <div className="flex items-start gap-2">
                  <input type="checkbox" checked={selected.has(i)}
                    onChange={() => toggleSelect(i)}
                    className="mt-1 accent-brand-500" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <input value={chunk.section_code || ''}
                        onChange={(e) => updateChunk(i, 'section_code', e.target.value)}
                        className="border rounded px-2 py-0.5 text-xs w-28"
                        placeholder="Section code" />
                      <input value={chunk.section_title || ''}
                        onChange={(e) => updateChunk(i, 'section_title', e.target.value)}
                        className="border rounded px-2 py-0.5 text-xs flex-1"
                        placeholder="Section title" />
                    </div>
                    <div className="flex items-center gap-1 mb-1">
                      <span className="text-xs text-gray-400">Tags:</span>
                      <input value={chunk.tags || ''}
                        onChange={(e) => updateChunk(i, 'tags', e.target.value)}
                        className="border rounded px-2 py-0.5 text-xs flex-1"
                        placeholder="comma-separated tags" />
                    </div>
                    {chunk.suggested_syllabus_ids?.length > 0 && (
                      <div className="flex items-center gap-1 text-xs text-blue-600">
                        <span>Matched syllabus IDs:</span>
                        {chunk.suggested_syllabus_ids.map((id) => (
                          <span key={id} className="bg-blue-100 px-1.5 py-0.5 rounded">{id}</span>
                        ))}
                      </div>
                    )}
                    <button onClick={() => toggleExpand(i)}
                      className="text-xs text-gray-400 hover:text-gray-600 mt-1">
                      {expanded.has(i) ? 'Hide content' : 'Preview content'}
                    </button>
                    {expanded.has(i) && (
                      <div className="mt-2 text-xs text-gray-600 bg-gray-50 rounded p-2 max-h-32 overflow-y-auto whitespace-pre-wrap">
                        {chunk.content}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

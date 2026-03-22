import { useState, useEffect } from 'react'
import { api } from '../api'
import RichTextEditor from '../components/RichTextEditor'

// ── Helpers ────────────────────────────────────────────────────────────────────

function useCurrentSession() {
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('currentSessionId') || '')
  useEffect(() => {
    const handler = () => setSessionId(localStorage.getItem('currentSessionId') || '')
    window.addEventListener('storage', handler)
    return () => window.removeEventListener('storage', handler)
  }, [])
  return sessionId
}

function Toast({ message, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 3000)
    return () => clearTimeout(t)
  }, [])
  return (
    <div className="fixed bottom-4 right-4 bg-green-600 text-white px-4 py-2 rounded-lg shadow-lg text-sm z-50">
      {message}
    </div>
  )
}

const TrashIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
  </svg>
)

// ── SYLLABUS TAB ───────────────────────────────────────────────────────────────

function SyllabusTab({ sessionId, taxTypes }) {
  const [taxType, setTaxType] = useState('')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [editId, setEditId] = useState(null)
  const [editRow, setEditRow] = useState({})
  const [showUpload, setShowUpload] = useState(false)
  const [uploadFile, setUploadFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [toast, setToast] = useState('')
  const [selectedIds, setSelectedIds] = useState(new Set())

  const fetchItems = async () => {
    if (!sessionId) return
    setLoading(true)
    try {
      const params = { session_id: sessionId }
      if (taxType) params.tax_type = taxType
      const data = await api.getKBSyllabus(params)
      setItems(data.filter((d) => d.syllabus_code))
      setSelectedIds(new Set())
    } catch { setItems([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchItems() }, [sessionId, taxType])

  const toggleSelect = (id) => {
    setSelectedIds((prev) => { const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next })
  }
  const toggleSelectAll = () => {
    setSelectedIds(selectedIds.size === items.length ? new Set() : new Set(items.map((i) => i.id)))
  }
  const handleBulkDelete = async () => {
    if (!window.confirm(`Delete ${selectedIds.size} items? This cannot be undone.`)) return
    await api.bulkDeleteKBItems('syllabus', [...selectedIds])
    fetchItems()
  }

  const handleUploadPreview = async () => {
    if (!uploadFile || !taxType || !sessionId) { alert('Select tax type and file first'); return }
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('session_id', sessionId)
      fd.append('tax_type', taxType)
      fd.append('file', uploadFile)
      const data = await api.uploadKBSyllabus(fd)
      setPreview(data)
    } catch (err) { alert('Upload failed: ' + err.message) }
    finally { setUploading(false) }
  }

  const handleConfirmImport = async () => {
    if (!preview) return
    setUploading(true)
    try {
      await api.bulkInsertKBSyllabus({ session_id: parseInt(sessionId), tax_type: taxType, rows: preview.rows, replace: true })
      setShowUpload(false)
      setPreview(null)
      setUploadFile(null)
      setToast(`${preview.total} items imported`)
      fetchItems()
    } catch (err) { alert('Import failed: ' + err.message) }
    finally { setUploading(false) }
  }

  const handleSaveEdit = async () => {
    try {
      await api.updateKBSyllabus(editId, {
        sac_thue: taxType || editRow.sac_thue || editRow.tax_type,
        section_code: editRow.syllabus_code,
        section_title: editRow.topic,
        content: editRow.detailed_syllabus,
        tax_type: taxType || editRow.tax_type,
        syllabus_code: editRow.syllabus_code,
        topic: editRow.topic,
        detailed_syllabus: editRow.detailed_syllabus,
        session_id: parseInt(sessionId),
      })
      setEditId(null)
      fetchItems()
    } catch (err) { alert('Save failed: ' + err.message) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this syllabus item?')) return
    try { await api.deleteKBSyllabus(id); fetchItems() } catch { }
  }

  const handleAddManual = async () => {
    try {
      await api.createKBSyllabus({
        sac_thue: taxType || 'CIT', section_code: 'NEW', section_title: '', content: '',
        tax_type: taxType || 'CIT', syllabus_code: 'NEW', topic: '', detailed_syllabus: '',
        session_id: parseInt(sessionId),
      })
      fetchItems()
    } catch (err) { alert('Failed: ' + err.message) }
  }

  const allSelected = items.length > 0 && selectedIds.size === items.length
  const someSelected = selectedIds.size > 0 && selectedIds.size < items.length

  return (
    <div>
      {toast && <Toast message={toast} onClose={() => setToast('')} />}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <select value={taxType} onChange={(e) => setTaxType(e.target.value)}
          className="border rounded px-3 py-1.5 text-sm">
          <option value="">All Tax Types</option>
          {taxTypes.map((t) => <option key={t.code} value={t.code}>{t.code} — {t.name}</option>)}
        </select>
        <button onClick={() => setShowUpload(true)}
          className="px-3 py-1.5 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600">
          Upload CSV/Excel
        </button>
        <button onClick={handleAddManual}
          className="px-3 py-1.5 border text-sm rounded-lg hover:bg-gray-50">
          + Add manually
        </button>
        <span className="text-xs text-gray-500 ml-auto">{items.length} items</span>
      </div>

      {/* Bulk action bar */}
      {selectedIds.size > 0 && (
        <div className="sticky top-0 z-10 mb-3 flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-lg px-4 py-2 shadow-sm">
          <span className="text-sm text-amber-700 font-medium">✓ {selectedIds.size} items selected</span>
          <button onClick={handleBulkDelete}
            className="flex items-center gap-1 px-3 py-1 bg-red-500 text-white text-xs rounded hover:bg-red-600">
            <TrashIcon /> Delete selected
          </button>
          <button onClick={() => setSelectedIds(new Set())} className="text-xs text-gray-500 hover:text-gray-700">✕ Clear</button>
        </div>
      )}

      {/* Upload Modal */}
      {showUpload && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-5 w-full max-w-lg mx-4">
            <h4 className="font-semibold mb-3">Upload Syllabus CSV/Excel</h4>
            <p className="text-xs text-gray-500 mb-3">Required columns: Code, Topics, Detailed Syllabus</p>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium block mb-1">Tax Type</label>
                <select value={taxType} onChange={(e) => setTaxType(e.target.value)}
                  className="w-full border rounded px-3 py-1.5 text-sm">
                  <option value="">Select tax type</option>
                  {taxTypes.map((t) => <option key={t.code} value={t.code}>{t.code} — {t.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium block mb-1">File (CSV or .xlsx)</label>
                <input type="file" accept=".csv,.xlsx,.xls"
                  onChange={(e) => { setUploadFile(e.target.files[0]); setPreview(null) }}
                  className="w-full text-sm" />
              </div>
              {!preview && (
                <button onClick={handleUploadPreview} disabled={uploading}
                  className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg disabled:opacity-50">
                  {uploading ? 'Parsing...' : 'Preview'}
                </button>
              )}
              {preview && (
                <div>
                  <p className="text-xs font-medium mb-2">Preview ({preview.total} rows total):</p>
                  <div className="overflow-x-auto border rounded">
                    <table className="text-xs w-full">
                      <thead className="bg-gray-50">
                        <tr>{['Code', 'Topics', 'Detailed Syllabus'].map((h) => <th key={h} className="px-2 py-1 text-left">{h}</th>)}</tr>
                      </thead>
                      <tbody>{preview.preview.map((r, i) => (
                        <tr key={i} className="border-t">
                          <td className="px-2 py-1 font-mono">{r.code}</td>
                          <td className="px-2 py-1">{r.topics}</td>
                          <td className="px-2 py-1 max-w-xs truncate">{r.detailed_syllabus}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                  <div className="mt-3 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
                    ⚠️ This will replace existing syllabus items for {taxType}.
                  </div>
                  <button onClick={handleConfirmImport} disabled={uploading}
                    className="mt-3 px-4 py-2 bg-green-600 text-white text-sm rounded-lg disabled:opacity-50">
                    {uploading ? 'Importing...' : `Confirm Import (${preview.total} items)`}
                  </button>
                </div>
              )}
            </div>
            <button onClick={() => { setShowUpload(false); setPreview(null); setUploadFile(null) }}
              className="mt-3 text-sm text-gray-500 hover:underline">Cancel</button>
          </div>
        </div>
      )}

      {/* Table */}
      {loading ? <div className="text-center py-8 text-gray-400">Loading...</div> : (
        <div className="overflow-x-auto border rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs">
              <tr>
                <th className="px-2 py-2 w-8">
                  <input type="checkbox" checked={allSelected} ref={(el) => { if (el) el.indeterminate = someSelected }}
                    onChange={toggleSelectAll} className="rounded" />
                </th>
                <th className="px-3 py-2 text-left w-20">Code</th>
                <th className="px-3 py-2 text-left w-40">Topics</th>
                <th className="px-3 py-2 text-left">Detailed Syllabus</th>
                <th className="px-3 py-2 text-left w-24">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map((item) => (
                editId === item.id ? (
                  <tr key={item.id} className="bg-blue-50">
                    <td className="px-2 py-1" />
                    <td className="px-2 py-1"><input value={editRow.syllabus_code || ''} onChange={(e) => setEditRow({ ...editRow, syllabus_code: e.target.value })} className="w-full border rounded px-1 py-0.5 text-xs" /></td>
                    <td className="px-2 py-1"><input value={editRow.topic || ''} onChange={(e) => setEditRow({ ...editRow, topic: e.target.value })} className="w-full border rounded px-1 py-0.5 text-xs" /></td>
                    <td className="px-2 py-1"><textarea value={editRow.detailed_syllabus || ''} onChange={(e) => setEditRow({ ...editRow, detailed_syllabus: e.target.value })} rows={2} className="w-full border rounded px-1 py-0.5 text-xs" /></td>
                    <td className="px-2 py-1">
                      <button onClick={handleSaveEdit} className="text-xs text-green-600 mr-1">Save</button>
                      <button onClick={() => setEditId(null)} className="text-xs text-gray-500">Cancel</button>
                    </td>
                  </tr>
                ) : (
                  <tr key={item.id} className={`hover:bg-gray-50 ${selectedIds.has(item.id) ? 'bg-blue-50' : ''}`}>
                    <td className="px-2 py-2 text-center">
                      <input type="checkbox" checked={selectedIds.has(item.id)} onChange={() => toggleSelect(item.id)} className="rounded" />
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{item.syllabus_code || item.section_code}</td>
                    <td className="px-3 py-2 text-xs text-gray-600">{item.topic || item.section_title}</td>
                    <td className="px-3 py-2 text-xs">{(item.detailed_syllabus || item.content || '').substring(0, 120)}{(item.detailed_syllabus || item.content || '').length > 120 ? '...' : ''}</td>
                    <td className="px-3 py-2 flex items-center gap-2">
                      <button onClick={() => { setEditId(item.id); setEditRow({ syllabus_code: item.syllabus_code || item.section_code, topic: item.topic || item.section_title, detailed_syllabus: item.detailed_syllabus || item.content, ...item }) }} className="text-xs text-brand-600">Edit</button>
                      <button onClick={() => handleDelete(item.id)} className="text-red-400 hover:text-red-600 transition-colors" title="Delete"><TrashIcon /></button>
                    </td>
                  </tr>
                )
              ))}
              {items.length === 0 && <tr><td colSpan={5} className="text-center py-6 text-gray-400 text-sm">No syllabus items. Upload a CSV/Excel file to get started.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── REGULATIONS TAB ─────────────────────────────────────────────────────────────

function RegulationsTab({ sessionId, taxTypes }) {
  const [taxType, setTaxType] = useState('')
  const [files, setFiles] = useState([])
  const [parsedRows, setParsedRows] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [parseStatus, setParseStatus] = useState({}) // fileId -> {jobId, status, parsed, total_chunks, chunk}
  const [editItem, setEditItem] = useState(null)
  const [toast, setToast] = useState('')
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [tagLoading, setTagLoading] = useState(false)
  // Filters
  const [regFileFilter, setRegFileFilter] = useState('')
  const [syllabusFilter, setSyllabusFilter] = useState('')
  const [articleFilter, setArticleFilter] = useState('')
  const [search, setSearch] = useState('')
  const [regFiles, setRegFiles] = useState([])

  const fetchFiles = async () => {
    if (!sessionId) return
    try { setFiles(await api.getSessionFiles(sessionId, 'regulation')) } catch { setFiles([]) }
  }

  const fetchRegFiles = async () => {
    if (!sessionId) return
    try {
      const params = { session_id: sessionId }
      if (taxType) params.tax_type = taxType
      setRegFiles(await api.getRegulationFiles(params))
    } catch { setRegFiles([]) }
  }

  const fetchParsed = async () => {
    if (!sessionId) return
    setLoading(true)
    try {
      const params = { session_id: sessionId }
      if (taxType) params.tax_type = taxType
      if (regFileFilter) params.source_file = regFileFilter
      if (syllabusFilter) params.syllabus_code = syllabusFilter
      if (articleFilter) params.article_no = articleFilter
      if (search) params.search = search
      const data = await api.getRegulationsParsed(params)
      setParsedRows(data.items || [])
      setTotal(data.total || 0)
      setSelectedIds(new Set())
    } catch { setParsedRows([]); setTotal(0) }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchFiles(); fetchRegFiles() }, [sessionId, taxType])
  useEffect(() => { fetchParsed() }, [sessionId, taxType, regFileFilter, syllabusFilter, articleFilter, search])

  const toggleSelect = (id) => {
    setSelectedIds((prev) => { const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next })
  }
  const toggleSelectAll = () => {
    setSelectedIds(selectedIds.size === parsedRows.length ? new Set() : new Set(parsedRows.map((i) => i.id)))
  }
  const handleBulkDelete = async () => {
    if (!window.confirm(`Delete ${selectedIds.size} items? This cannot be undone.`)) return
    await api.bulkDeleteKBItems('regulation-parsed', [...selectedIds])
    fetchParsed()
    fetchRegFiles()
  }

  const handleUploadFile = async (e) => {
    const file = e.target.files[0]
    if (!file || !taxType || !sessionId) { alert('Select tax type first'); return }
    const fd = new FormData()
    fd.append('doc_type', 'regulation')
    fd.append('sac_thue', taxType)
    fd.append('file', file)
    try {
      await api.uploadSessionDoc(sessionId, fd)
      setToast('File uploaded')
      fetchFiles()
    } catch (err) { alert('Upload failed: ' + err.message) }
    e.target.value = ''
  }

  const handleParse = async (file) => {
    const docRef = prompt('Enter document reference (e.g. "Decree 320/2025/ND-CP"):', file.file_name.replace(/\.(docx?|pdf)$/i, ''))
    if (docRef === null) return
    try {
      const { job_id } = await api.parseRegulationDocAsync({
        session_id: parseInt(sessionId),
        tax_type: taxType || file.sac_thue,
        file_path: file.file_path,
        doc_ref: docRef,
      })
      setParseStatus((p) => ({ ...p, [file.id]: { jobId: job_id, status: 'running', parsed: 0, total_chunks: 0, chunk: 0 } }))

      const poll = setInterval(async () => {
        try {
          const job = await api.getParseJob(job_id)
          setParseStatus((p) => ({ ...p, [file.id]: { jobId: job_id, ...job } }))
          if (job.status === 'done' || job.status === 'failed') {
            clearInterval(poll)
            if (job.status === 'done') {
              setToast(`Parsed ${job.parsed} paragraphs`)
              fetchParsed()
              fetchRegFiles()
            }
          }
        } catch { clearInterval(poll) }
      }, 2000)
    } catch (err) { alert('Parse failed: ' + err.message) }
  }

  const handleDeleteFile = async (fileId) => {
    if (!confirm('Delete this file?')) return
    try { await api.deleteSessionFile(sessionId, fileId); fetchFiles() } catch { }
  }

  const handleSaveEdit = async () => {
    try {
      await api.updateParsedRegulation(editItem.id, {
        paragraph_text: editItem.paragraph_text,
        syllabus_codes: editItem.syllabus_codes || [],
        tags: editItem.tags,
      })
      setEditItem(null)
      fetchParsed()
    } catch (err) { alert('Save failed: ' + err.message) }
  }

  const handleDeleteParsed = async (id) => {
    if (!confirm('Delete this paragraph?')) return
    try { await api.deleteParsedRegulation(id); fetchParsed() } catch { }
  }

  const handleTagSyllabus = async () => {
    setTagLoading(true)
    try {
      const res = await api.tagSyllabus(sessionId, taxType || null)
      if (res.tagged > 0) {
        setToast(`Tagged ${res.tagged}/${res.total_items} items`)
        fetchParsed()
      } else {
        setToast(res.message || 'No untagged items found')
      }
    } catch (err) { setToast('Tagging failed: ' + err.message) }
    finally { setTagLoading(false) }
  }

  const untaggedCount = parsedRows.filter((i) => !i.syllabus_codes || i.syllabus_codes.length === 0).length

  const allSelected = parsedRows.length > 0 && selectedIds.size === parsedRows.length
  const someSelected = selectedIds.size > 0 && selectedIds.size < parsedRows.length

  return (
    <div>
      {toast && <Toast message={toast} onClose={() => setToast('')} />}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <select value={taxType} onChange={(e) => { setTaxType(e.target.value); setRegFileFilter(''); setSyllabusFilter('') }}
          className="border rounded px-3 py-1.5 text-sm">
          <option value="">All Tax Types</option>
          {taxTypes.map((t) => <option key={t.code} value={t.code}>{t.code} — {t.name}</option>)}
        </select>
        <label className="px-3 py-1.5 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600 cursor-pointer">
          + Upload File
          <input type="file" accept=".doc,.docx,.pdf,.txt" onChange={handleUploadFile} className="hidden" />
        </label>
        <button
          onClick={handleTagSyllabus}
          disabled={tagLoading || parsedRows.length === 0}
          className="px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg disabled:opacity-50"
        >
          {tagLoading ? 'Tagging...' : `🏷 Tag Syllabus (${untaggedCount} untagged)`}
        </button>
      </div>

      {/* Files */}
      {files.length > 0 && (
        <div className="mb-4 border rounded-lg p-3 space-y-2">
          <p className="text-xs font-medium text-gray-600 mb-1">Uploaded Files:</p>
          {files.map((f) => {
            const ps = parseStatus[f.id]
            return (
              <div key={f.id} className="flex items-center gap-3 text-sm flex-wrap">
                <span className="text-lg">📄</span>
                <span className="flex-1 text-xs">{f.file_name}</span>
                <span className="text-xs text-gray-400">{f.sac_thue}</span>
                {ps && ps.status === 'running' && (
                  <span className="text-xs text-blue-600 animate-pulse">
                    Parsing... {ps.parsed} ¶ (chunk {ps.chunk}/{ps.total_chunks})
                  </span>
                )}
                {ps && ps.status === 'done' && (
                  <span className="text-xs text-green-600">✓ {ps.parsed} paragraphs parsed</span>
                )}
                {ps && ps.status === 'failed' && (
                  <span className="text-xs text-red-500">✗ Parse failed</span>
                )}
                <button onClick={() => handleParse(f)} disabled={ps?.status === 'running'}
                  className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50">
                  {ps?.status === 'running' ? 'Parsing...' : (ps?.status === 'done' ? 'Re-parse' : 'Parse')}
                </button>
                <button onClick={() => handleDeleteFile(f.id)} className="text-xs text-red-500">✕</button>
              </div>
            )
          })}
        </div>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap gap-2 mb-3 items-center">
        <select value={regFileFilter} onChange={(e) => setRegFileFilter(e.target.value)}
          className="border rounded px-3 py-1.5 text-sm min-w-[180px]">
          <option value="">All Regulation Files</option>
          {regFiles.map((f) => (
            <option key={f.source_file} value={f.source_file}>
              {f.doc_ref || f.source_file?.split('/').pop()} ({f.paragraph_count} ¶)
            </option>
          ))}
        </select>
        <div className="relative">
          <input value={syllabusFilter} onChange={(e) => setSyllabusFilter(e.target.value)}
            placeholder="Syllabus code..." className="border rounded px-3 py-1.5 text-sm w-40" />
          {syllabusFilter && (
            <button onClick={() => setSyllabusFilter('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs">✕</button>
          )}
        </div>
        <input value={articleFilter} onChange={(e) => setArticleFilter(e.target.value)}
          placeholder="Article... e.g. 9" className="border rounded px-3 py-1.5 text-sm w-32" />
        <input value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Search text..." className="border rounded px-3 py-1.5 text-sm flex-1 min-w-[140px]" />
        {(regFileFilter || syllabusFilter || articleFilter || search) && (
          <button onClick={() => { setRegFileFilter(''); setSyllabusFilter(''); setArticleFilter(''); setSearch('') }}
            className="text-xs text-gray-500 hover:text-gray-700 underline">Clear filters</button>
        )}
        <span className="text-xs text-gray-400 ml-auto">{total} paragraphs</span>
      </div>

      {/* Bulk action bar */}
      {selectedIds.size > 0 && (
        <div className="sticky top-0 z-10 mb-3 flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-lg px-4 py-2 shadow-sm">
          <span className="text-sm text-amber-700 font-medium">✓ {selectedIds.size} items selected</span>
          <button onClick={handleBulkDelete}
            className="flex items-center gap-1 px-3 py-1 bg-red-500 text-white text-xs rounded hover:bg-red-600">
            <TrashIcon /> Delete selected
          </button>
          <button onClick={() => setSelectedIds(new Set())} className="text-xs text-gray-500 hover:text-gray-700">✕ Clear</button>
        </div>
      )}

      {loading ? <div className="text-center py-6 text-gray-400">Loading...</div> : (
        <div className="overflow-x-auto border rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs">
              <tr>
                <th className="px-2 py-2 w-8">
                  <input type="checkbox" checked={allSelected} ref={(el) => { if (el) el.indeterminate = someSelected }}
                    onChange={toggleSelectAll} className="rounded" />
                </th>
                <th className="px-3 py-2 text-left w-36">RegCode</th>
                <th className="px-3 py-2 text-left w-24">Article</th>
                <th className="px-3 py-2 text-left">Paragraph Text</th>
                <th className="px-3 py-2 text-left w-32">Syllabus Codes</th>
                <th className="px-3 py-2 text-left w-20">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {parsedRows.map((row) => (
                <tr key={row.id} className={`hover:bg-gray-50 ${selectedIds.has(row.id) ? 'bg-blue-50' : ''}`}>
                  <td className="px-2 py-2 text-center">
                    <input type="checkbox" checked={selectedIds.has(row.id)} onChange={() => toggleSelect(row.id)} className="rounded" />
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{row.reg_code}</td>
                  <td className="px-3 py-2 text-xs">{row.article_no}</td>
                  <td className="px-3 py-2 text-xs">{row.paragraph_text?.substring(0, 150)}{row.paragraph_text?.length > 150 ? '...' : ''}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {(row.syllabus_codes || []).map((code) => (
                        <button key={code} onClick={() => setSyllabusFilter(code)}
                          className="px-1.5 py-0.5 bg-blue-50 text-blue-600 text-xs font-mono rounded border border-blue-100 hover:bg-blue-100 cursor-pointer"
                          title="Click to filter by this syllabus code">
                          {code}
                        </button>
                      ))}
                      {(!row.syllabus_codes || row.syllabus_codes.length === 0) && <span className="text-gray-300 text-xs">—</span>}
                    </div>
                  </td>
                  <td className="px-3 py-2 flex items-center gap-2">
                    <button onClick={() => setEditItem({ ...row })} className="text-xs text-brand-600">Edit</button>
                    <button onClick={() => handleDeleteParsed(row.id)} className="text-red-400 hover:text-red-600 transition-colors" title="Delete"><TrashIcon /></button>
                  </td>
                </tr>
              ))}
              {parsedRows.length === 0 && (
                <tr><td colSpan={6} className="text-center py-6 text-gray-400 text-sm">No parsed paragraphs. Upload and parse a regulation file.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Edit Modal */}
      {editItem && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-5 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <h4 className="font-semibold mb-1">Edit Paragraph: <span className="font-mono text-brand-600">{editItem.reg_code}</span></h4>
            <div className="space-y-3 mt-3">
              <div>
                <label className="text-xs font-medium block mb-1">Paragraph Text</label>
                <textarea value={editItem.paragraph_text || ''} rows={6}
                  onChange={(e) => setEditItem({ ...editItem, paragraph_text: e.target.value })}
                  className="w-full border rounded px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="text-xs font-medium block mb-1">Syllabus Codes (comma-separated)</label>
                <input value={(editItem.syllabus_codes || []).join(', ')}
                  onChange={(e) => setEditItem({ ...editItem, syllabus_codes: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
                  className="w-full border rounded px-2 py-1.5 text-sm" placeholder="B2a, B2b, C1a" />
              </div>
              <div>
                <label className="text-xs font-medium block mb-1">Tags</label>
                <input value={editItem.tags || ''} onChange={(e) => setEditItem({ ...editItem, tags: e.target.value })}
                  className="w-full border rounded px-2 py-1.5 text-sm" />
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={handleSaveEdit} className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg">Save</button>
              <button onClick={() => setEditItem(null)} className="px-4 py-2 border text-sm rounded-lg">Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── TAX RATES TAB ───────────────────────────────────────────────────────────────

function TaxRatesTab({ sessionId, taxTypes }) {
  const [taxType, setTaxType] = useState('')
  const [rates, setRates] = useState([])
  const [loading, setLoading] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [editItem, setEditItem] = useState(null)
  const [form, setForm] = useState({ table_name: '', tax_type: '', content: '' })
  const [uploadFile, setUploadFile] = useState(null)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState('')

  const fetchRates = async () => {
    if (!sessionId) return
    setLoading(true)
    try {
      const params = { session_id: sessionId }
      if (taxType) params.tax_type = taxType
      const data = await api.getTaxRates(params)
      setRates(data)
    } catch { setRates([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchRates() }, [sessionId, taxType])

  const openAdd = () => {
    setEditItem(null)
    setForm({ table_name: '', tax_type: taxType || '', content: '' })
    setUploadFile(null)
    setShowModal(true)
  }

  const openEdit = (item) => {
    setEditItem(item)
    setForm({ table_name: item.table_name, tax_type: item.tax_type, content: item.content })
    setShowModal(true)
  }

  const handleSave = async () => {
    if (!form.table_name || !form.tax_type) { alert('Table name and tax type required'); return }
    setSaving(true)
    try {
      if (uploadFile) {
        const fd = new FormData()
        fd.append('session_id', sessionId)
        fd.append('tax_type', form.tax_type)
        fd.append('table_name', form.table_name)
        fd.append('file', uploadFile)
        await api.uploadTaxRates(fd)
      } else if (editItem) {
        await api.updateTaxRate(editItem.id, form)
      } else {
        await api.createTaxRate({ ...form, session_id: parseInt(sessionId) })
      }
      setShowModal(false)
      setToast('Saved')
      fetchRates()
    } catch (err) { alert('Save failed: ' + err.message) }
    finally { setSaving(false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this rate table?')) return
    try { await api.deleteTaxRate(id); fetchRates() } catch { }
  }

  return (
    <div>
      {toast && <Toast message={toast} onClose={() => setToast('')} />}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <select value={taxType} onChange={(e) => setTaxType(e.target.value)}
          className="border rounded px-3 py-1.5 text-sm">
          <option value="">All Tax Types</option>
          {taxTypes.map((t) => <option key={t.code} value={t.code}>{t.code} — {t.name}</option>)}
        </select>
        <button onClick={openAdd}
          className="px-3 py-1.5 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600">
          + Add Rate Table
        </button>
      </div>

      {loading ? <div className="text-center py-6 text-gray-400">Loading...</div> : (
        <div className="space-y-4">
          {rates.map((rate) => (
            <div key={rate.id} className="border rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="font-medium text-sm">{rate.table_name}</span>
                  <span className="ml-2 text-xs bg-gray-100 px-2 py-0.5 rounded">{rate.tax_type}</span>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => openEdit(rate)} className="text-xs text-brand-600 hover:underline">Edit</button>
                  <button onClick={() => handleDelete(rate.id)} className="text-xs text-red-500 hover:underline">✕</button>
                </div>
              </div>
              <div className="text-xs text-gray-600 overflow-x-auto"
                dangerouslySetInnerHTML={{ __html: rate.content.substring(0, 1000) }} />
            </div>
          ))}
          {rates.length === 0 && (
            <div className="text-center py-8 text-gray-400 text-sm border rounded-lg">
              No tax rate tables. Add one to start.
            </div>
          )}
        </div>
      )}

      {/* Add/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-5 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <h4 className="font-semibold mb-3">{editItem ? 'Edit' : 'Add'} Rate Table</h4>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium block mb-1">Table Name</label>
                <input value={form.table_name} onChange={(e) => setForm({ ...form, table_name: e.target.value })}
                  placeholder="e.g. PIT on Employment Income (Progressive Rates)"
                  className="w-full border rounded px-3 py-1.5 text-sm" />
              </div>
              <div>
                <label className="text-xs font-medium block mb-1">Tax Type</label>
                <select value={form.tax_type} onChange={(e) => setForm({ ...form, tax_type: e.target.value })}
                  className="w-full border rounded px-3 py-1.5 text-sm">
                  <option value="">Select</option>
                  {taxTypes.map((t) => <option key={t.code} value={t.code}>{t.code} — {t.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium block mb-1">Upload CSV/Excel (optional)</label>
                <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => setUploadFile(e.target.files[0])}
                  className="w-full text-sm" />
              </div>
              {!uploadFile && (
                <div>
                  <label className="text-xs font-medium block mb-1">Content</label>
                  <div style={{ paddingBottom: 50 }}>
                    <RichTextEditor value={form.content} onChange={(val) => setForm({ ...form, content: val })}
                      placeholder="Paste or type rate table here..." height={200} />
                  </div>
                </div>
              )}
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={handleSave} disabled={saving}
                className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg disabled:opacity-50">
                {saving ? 'Saving...' : 'Save'}
              </button>
              <button onClick={() => setShowModal(false)} className="px-4 py-2 border text-sm rounded-lg">Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main Page ───────────────────────────────────────────────────────────────────

const TABS = ['Syllabus', 'Regulations', 'Tax Rates']

export default function KnowledgeBase() {
  const sessionId = useCurrentSession()
  const [activeTab, setActiveTab] = useState('Syllabus')
  const [taxTypes, setTaxTypes] = useState([])

  useEffect(() => {
    if (!sessionId) return
    api.getSessionSettings(sessionId)
      .then((d) => setTaxTypes(d.tax_types || []))
      .catch(() => setTaxTypes([
        { code: 'CIT', name: 'Corporate Income Tax' },
        { code: 'PIT', name: 'Personal Income Tax' },
        { code: 'VAT', name: 'Value Added Tax' },
        { code: 'FCT', name: 'Foreign Contractor Tax' },
      ]))
  }, [sessionId])

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold">Knowledge Base</h2>
        {!sessionId && <p className="text-sm text-yellow-600">Select a session in the sidebar.</p>}
      </div>

      {/* Tabs */}
      <div className="flex border-b mb-6">
        {TABS.map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab ? 'border-brand-500 text-brand-600' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}>
            {tab}
          </button>
        ))}
      </div>

      {sessionId && (
        <>
          {activeTab === 'Syllabus' && <SyllabusTab sessionId={sessionId} taxTypes={taxTypes} />}
          {activeTab === 'Regulations' && <RegulationsTab sessionId={sessionId} taxTypes={taxTypes} />}
          {activeTab === 'Tax Rates' && <TaxRatesTab sessionId={sessionId} taxTypes={taxTypes} />}
        </>
      )}
    </div>
  )
}

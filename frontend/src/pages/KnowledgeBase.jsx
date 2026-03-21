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

  const fetchItems = async () => {
    if (!sessionId) return
    setLoading(true)
    try {
      const params = { session_id: sessionId }
      if (taxType) params.tax_type = taxType
      const data = await api.getKBSyllabus(params)
      setItems(data.filter((d) => d.syllabus_code))
    } catch { setItems([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchItems() }, [sessionId, taxType])

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
      await api.bulkInsertKBSyllabus({ session_id: parseInt(sessionId), tax_type: taxType, rows: preview.rows })
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
                    <td className="px-2 py-1"><input value={editRow.syllabus_code || ''} onChange={(e) => setEditRow({ ...editRow, syllabus_code: e.target.value })} className="w-full border rounded px-1 py-0.5 text-xs" /></td>
                    <td className="px-2 py-1"><input value={editRow.topic || ''} onChange={(e) => setEditRow({ ...editRow, topic: e.target.value })} className="w-full border rounded px-1 py-0.5 text-xs" /></td>
                    <td className="px-2 py-1"><textarea value={editRow.detailed_syllabus || ''} onChange={(e) => setEditRow({ ...editRow, detailed_syllabus: e.target.value })} rows={2} className="w-full border rounded px-1 py-0.5 text-xs" /></td>
                    <td className="px-2 py-1">
                      <button onClick={handleSaveEdit} className="text-xs text-green-600 mr-1">Save</button>
                      <button onClick={() => setEditId(null)} className="text-xs text-gray-500">Cancel</button>
                    </td>
                  </tr>
                ) : (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-3 py-2 font-mono text-xs">{item.syllabus_code || item.section_code}</td>
                    <td className="px-3 py-2 text-xs text-gray-600">{item.topic || item.section_title}</td>
                    <td className="px-3 py-2 text-xs">{(item.detailed_syllabus || item.content || '').substring(0, 120)}{(item.detailed_syllabus || item.content || '').length > 120 ? '...' : ''}</td>
                    <td className="px-3 py-2">
                      <button onClick={() => { setEditId(item.id); setEditRow({ syllabus_code: item.syllabus_code || item.section_code, topic: item.topic || item.section_title, detailed_syllabus: item.detailed_syllabus || item.content, ...item }) }} className="text-xs text-brand-600 mr-2">Edit</button>
                      <button onClick={() => handleDelete(item.id)} className="text-xs text-red-500">✕</button>
                    </td>
                  </tr>
                )
              ))}
              {items.length === 0 && <tr><td colSpan={4} className="text-center py-6 text-gray-400 text-sm">No syllabus items. Upload a CSV/Excel file to get started.</td></tr>}
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
  const [loading, setLoading] = useState(false)
  const [parsing, setParsing] = useState(null)
  const [editItem, setEditItem] = useState(null)
  const [search, setSearch] = useState('')
  const [toast, setToast] = useState('')

  const fetchFiles = async () => {
    if (!sessionId) return
    try {
      const data = await api.getSessionFiles(sessionId, 'regulation')
      setFiles(data)
    } catch { setFiles([]) }
  }

  const fetchParsed = async () => {
    if (!sessionId) return
    setLoading(true)
    try {
      const params = { session_id: sessionId }
      if (taxType) params.tax_type = taxType
      const data = await api.getParsedRegulations(params)
      setParsedRows(data)
    } catch { setParsedRows([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchFiles(); fetchParsed() }, [sessionId, taxType])

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
    setParsing(file.id)
    try {
      const res = await api.parseRegulationDoc({
        session_id: parseInt(sessionId),
        tax_type: taxType || file.sac_thue,
        file_path: file.file_path,
        doc_ref: docRef,
      })
      setToast(`Parsed ${res.parsed} paragraphs`)
      fetchParsed()
    } catch (err) { alert('Parse failed: ' + err.message) }
    finally { setParsing(null) }
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

  const filteredRows = search
    ? parsedRows.filter((r) => r.reg_code?.includes(search) || r.paragraph_text?.toLowerCase().includes(search.toLowerCase()))
    : parsedRows

  return (
    <div>
      {toast && <Toast message={toast} onClose={() => setToast('')} />}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <select value={taxType} onChange={(e) => setTaxType(e.target.value)}
          className="border rounded px-3 py-1.5 text-sm">
          <option value="">All Tax Types</option>
          {taxTypes.map((t) => <option key={t.code} value={t.code}>{t.code} — {t.name}</option>)}
        </select>
        <label className="px-3 py-1.5 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600 cursor-pointer">
          + Upload File
          <input type="file" accept=".doc,.docx,.pdf,.txt" onChange={handleUploadFile} className="hidden" />
        </label>
      </div>

      {/* Files */}
      {files.length > 0 && (
        <div className="mb-4 border rounded-lg p-3 space-y-2">
          <p className="text-xs font-medium text-gray-600 mb-1">Uploaded Files:</p>
          {files.map((f) => (
            <div key={f.id} className="flex items-center gap-3 text-sm">
              <span className="text-lg">📄</span>
              <span className="flex-1 text-xs">{f.file_name}</span>
              <span className="text-xs text-gray-400">{f.sac_thue}</span>
              <button onClick={() => handleParse(f)} disabled={parsing === f.id}
                className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50">
                {parsing === f.id ? 'Parsing...' : 'Parse'}
              </button>
              <button onClick={() => handleDeleteFile(f.id)} className="text-xs text-red-500">✕</button>
            </div>
          ))}
        </div>
      )}

      {/* Parsed paragraphs */}
      <div className="flex items-center gap-3 mb-3">
        <span className="text-sm font-medium">Parsed Paragraphs ({parsedRows.length})</span>
        <input value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Search..." className="border rounded px-3 py-1 text-sm flex-1 max-w-xs" />
      </div>

      {loading ? <div className="text-center py-6 text-gray-400">Loading...</div> : (
        <div className="overflow-x-auto border rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs">
              <tr>
                <th className="px-3 py-2 text-left w-36">RegCode</th>
                <th className="px-3 py-2 text-left w-24">Article</th>
                <th className="px-3 py-2 text-left">Paragraph Text</th>
                <th className="px-3 py-2 text-left w-28">Syllabus Codes</th>
                <th className="px-3 py-2 text-left w-20">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filteredRows.map((row) => (
                <tr key={row.id} className="hover:bg-gray-50">
                  <td className="px-3 py-2 font-mono text-xs">{row.reg_code}</td>
                  <td className="px-3 py-2 text-xs">{row.article_no}</td>
                  <td className="px-3 py-2 text-xs">{row.paragraph_text?.substring(0, 150)}...</td>
                  <td className="px-3 py-2 text-xs">{(row.syllabus_codes || []).join(', ')}</td>
                  <td className="px-3 py-2">
                    <button onClick={() => setEditItem({ ...row })} className="text-xs text-brand-600 mr-2">Edit</button>
                    <button onClick={() => handleDeleteParsed(row.id)} className="text-xs text-red-500">✕</button>
                  </td>
                </tr>
              ))}
              {filteredRows.length === 0 && (
                <tr><td colSpan={5} className="text-center py-6 text-gray-400 text-sm">No parsed paragraphs. Upload and parse a regulation file.</td></tr>
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

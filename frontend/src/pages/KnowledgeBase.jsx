import { useState, useEffect } from 'react'
import { api } from '../api'
import ParseReviewPanel from '../components/ParseReviewPanel'

const SAC_THUE_OPTIONS = ['CIT', 'VAT', 'PIT', 'FCT', 'TP', 'ADMIN']
const TABS = ['Syllabus', 'Regulations', 'Sample Questions']

export default function KnowledgeBase() {
  const [tab, setTab] = useState(0)
  const [sacThue, setSacThue] = useState('')
  const [search, setSearch] = useState('')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editItem, setEditItem] = useState(null)
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [bankQuestions, setBankQuestions] = useState([])
  const [importForm, setImportForm] = useState({ question_id: '', title: '', exam_tricks: '' })
  const [showParse, setShowParse] = useState(false)
  const [sessions, setSessions] = useState([])
  const [currentSession, setCurrentSession] = useState(null)
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)

  // Load sessions and resolve current
  useEffect(() => {
    api.getSessions().then((data) => {
      setSessions(data)
      const storedId = localStorage.getItem('currentSessionId')
      const match = data.find((s) => String(s.id) === storedId) || data.find((s) => s.is_default)
      if (match) setCurrentSession(match)
    }).catch(() => {})
  }, [])

  const sessionId = currentSession?.id
  const TAB_DOC_TYPE = ['syllabus', 'regulation', 'sample_questions']

  const fetchFiles = async () => {
    if (!sessionId) return
    try {
      setFiles(await api.getSessionFiles(sessionId, TAB_DOC_TYPE[tab]))
    } catch { setFiles([]) }
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file || !sessionId) return
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('doc_type', TAB_DOC_TYPE[tab])
      formData.append('sac_thue', sacThue || 'CIT')
      await api.uploadSessionDoc(sessionId, formData)
      fetchFiles()
    } catch (err) { alert('Upload failed: ' + err.message) }
    finally { setUploading(false); e.target.value = '' }
  }

  const handleDeleteFile = async (fileId) => {
    if (!confirm('Delete this file?')) return
    await api.deleteSessionFile(sessionId, fileId)
    fetchFiles()
  }

  const fetchItems = async () => {
    setLoading(true)
    try {
      const params = {}
      if (sessionId) params.session_id = sessionId
      if (sacThue) params.sac_thue = sacThue
      if (search) params.search = search
      if (tab === 0) {
        setItems(await api.getKBSyllabus(params))
      } else if (tab === 1) {
        setItems(await api.getKBRegulations(params))
      } else {
        setItems(await api.getKBSamples(params))
      }
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (sessionId) { fetchItems(); fetchFiles() } }, [tab, sacThue, search, sessionId])

  const resetForm = () => {
    if (tab === 0) setForm({ sac_thue: 'CIT', section_code: '', section_title: '', content: '', tags: '', session_id: sessionId })
    else if (tab === 1) setForm({ sac_thue: 'CIT', regulation_ref: '', content: '', tags: '', session_id: sessionId })
    else setForm({ question_type: 'MCQ', sac_thue: 'CIT', title: '', content: '', exam_tricks: '', session_id: sessionId })
  }

  const handleAdd = () => {
    setEditItem(null)
    resetForm()
    setShowForm(true)
  }

  const handleEdit = (item) => {
    setEditItem(item)
    if (tab === 0) setForm({ sac_thue: item.sac_thue, section_code: item.section_code || '', section_title: item.section_title || '', content: item.content, tags: item.tags || '', session_id: sessionId })
    else if (tab === 1) setForm({ sac_thue: item.sac_thue, regulation_ref: item.regulation_ref || '', content: item.content, tags: item.tags || '', session_id: sessionId })
    else setForm({ question_type: item.question_type, sac_thue: item.sac_thue, title: item.title || '', content: item.content, exam_tricks: item.exam_tricks || '', session_id: sessionId })
    setShowForm(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      if (tab === 0) {
        if (editItem) await api.updateKBSyllabus(editItem.id, form)
        else await api.createKBSyllabus(form)
      } else if (tab === 1) {
        if (editItem) await api.updateKBRegulation(editItem.id, form)
        else await api.createKBRegulation(form)
      } else {
        if (editItem) await api.updateKBSample(editItem.id, form)
        else await api.createKBSample(form)
      }
      setShowForm(false)
      fetchItems()
    } catch (err) {
      alert('Save failed: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this item?')) return
    try {
      if (tab === 0) await api.deleteKBSyllabus(id)
      else if (tab === 1) await api.deleteKBRegulation(id)
      else await api.deleteKBSample(id)
      fetchItems()
    } catch (err) {
      alert('Delete failed: ' + err.message)
    }
  }

  const handleImportFromBank = async () => {
    if (!importForm.question_id) return
    try {
      await api.importKBSampleFromBank(importForm)
      setShowImport(false)
      setImportForm({ question_id: '', title: '', exam_tricks: '' })
      fetchItems()
    } catch (err) {
      alert('Import failed: ' + err.message)
    }
  }

  const loadBankQuestions = async () => {
    try {
      const qs = await api.getQuestions({ limit: 50 })
      setBankQuestions(Array.isArray(qs) ? qs : qs.questions || [])
    } catch {
      setBankQuestions([])
    }
    setShowImport(true)
  }

  const switchSession = (id) => {
    const match = sessions.find((s) => String(s.id) === id)
    if (match) {
      setCurrentSession(match)
      localStorage.setItem('currentSessionId', id)
    }
  }

  return (
    <div className="max-w-6xl">
      {/* Session header */}
      <div className="flex items-center gap-3 mb-6">
        <h2 className="text-2xl font-bold">Knowledge Base</h2>
        <span className="text-gray-400">—</span>
        <select
          value={sessionId || ''}
          onChange={(e) => switchSession(e.target.value)}
          className="text-sm border rounded-lg px-3 py-1.5 font-medium text-brand-600"
        >
          {sessions.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b">
        {TABS.map((t, i) => (
          <button
            key={t}
            onClick={() => { setTab(i); setShowForm(false); setShowParse(false) }}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === i ? 'border-brand-500 text-brand-600' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          value={sacThue}
          onChange={(e) => setSacThue(e.target.value)}
          className="border rounded-lg px-3 py-2 text-sm"
        >
          <option value="">All Tax Types</option>
          {SAC_THUE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search..."
          className="border rounded-lg px-3 py-2 text-sm flex-1"
        />
        <button onClick={handleAdd} className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600">
          + Add
        </button>
        {(tab === 0 || tab === 1) && sessionId && (
          <button onClick={() => setShowParse(!showParse)}
            className="px-4 py-2 bg-purple-500 text-white text-sm rounded-lg hover:bg-purple-600">
            Parse & Match File
          </button>
        )}
        {tab === 2 && (
          <button onClick={loadBankQuestions} className="px-4 py-2 bg-blue-500 text-white text-sm rounded-lg hover:bg-blue-600">
            Import from Bank
          </button>
        )}
      </div>

      {/* Uploaded Files */}
      {sessionId && (
        <div className="bg-white border rounded-xl p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold text-gray-600">Uploaded Files</h4>
            <label className={`px-3 py-1.5 bg-brand-500 text-white text-xs rounded-lg hover:bg-brand-600 cursor-pointer ${uploading ? 'opacity-50' : ''}`}>
              {uploading ? 'Uploading...' : '+ Upload File'}
              <input type="file" accept=".doc,.docx" onChange={handleUpload} className="hidden" disabled={uploading} />
            </label>
          </div>
          {files.length === 0 ? (
            <p className="text-xs text-gray-400">No files uploaded yet.</p>
          ) : (
            <div className="space-y-1">
              {files.map((f) => (
                <div key={f.id} className="flex items-center justify-between text-sm py-1.5 px-2 rounded hover:bg-gray-50">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400">&#128196;</span>
                    <span className="font-medium text-gray-700">{f.file_name}</span>
                    <span className="bg-gray-100 text-xs px-1.5 py-0.5 rounded">{f.sac_thue}</span>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => { setShowParse(true) }}
                      className="text-xs text-purple-600 hover:underline">Parse</button>
                    <button onClick={() => handleDeleteFile(f.id)}
                      className="text-xs text-red-500 hover:underline">Delete</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Parse & Match Panel */}
      {showParse && sessionId && (
        <ParseReviewPanel sessionId={sessionId} onDone={() => { setShowParse(false); fetchItems() }} />
      )}

      {/* Add/Edit Form */}
      {showForm && (
        <div className="bg-white border rounded-xl p-5 mb-4">
          <h3 className="font-semibold mb-3">{editItem ? 'Edit' : 'Add'} {TABS[tab].replace(' Questions', '')}</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1">Tax Type</label>
              <select value={form.sac_thue || 'CIT'} onChange={(e) => setForm({ ...form, sac_thue: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm">
                {SAC_THUE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            {tab === 0 && (
              <>
                <div>
                  <label className="block text-xs font-medium mb-1">Section Code</label>
                  <input value={form.section_code || ''} onChange={(e) => setForm({ ...form, section_code: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="e.g. Article 9.2" />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium mb-1">Section Title</label>
                  <input value={form.section_title || ''} onChange={(e) => setForm({ ...form, section_title: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm" />
                </div>
              </>
            )}
            {tab === 1 && (
              <div>
                <label className="block text-xs font-medium mb-1">Regulation Ref</label>
                <input value={form.regulation_ref || ''} onChange={(e) => setForm({ ...form, regulation_ref: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="e.g. Article 9, Decree 218" />
              </div>
            )}
            {tab === 2 && (
              <>
                <div>
                  <label className="block text-xs font-medium mb-1">Question Type</label>
                  <select value={form.question_type || 'MCQ'} onChange={(e) => setForm({ ...form, question_type: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm">
                    <option value="MCQ">MCQ</option>
                    <option value="SCENARIO_10">Scenario</option>
                    <option value="LONGFORM_15">Long-form</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1">Title</label>
                  <input value={form.title || ''} onChange={(e) => setForm({ ...form, title: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm" />
                </div>
              </>
            )}
            <div className="col-span-2">
              <label className="block text-xs font-medium mb-1">Content</label>
              <textarea value={form.content || ''} onChange={(e) => setForm({ ...form, content: e.target.value })}
                rows={5} className="w-full border rounded-lg px-3 py-2 text-sm resize-y" />
            </div>
            {(tab === 0 || tab === 1) && (
              <div className="col-span-2">
                <label className="block text-xs font-medium mb-1">Tags (comma-separated)</label>
                <input value={form.tags || ''} onChange={(e) => setForm({ ...form, tags: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="e.g. deductible, expenses, CIT" />
              </div>
            )}
            {tab === 2 && (
              <div className="col-span-2">
                <label className="block text-xs font-medium mb-1">Exam Tricks</label>
                <input value={form.exam_tricks || ''} onChange={(e) => setForm({ ...form, exam_tricks: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="Key tricks tested in this question" />
              </div>
            )}
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={handleSave} disabled={saving}
              className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600 disabled:opacity-50">
              {saving ? 'Saving...' : 'Save'}
            </button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 border text-sm rounded-lg hover:bg-gray-50">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Import from Bank modal */}
      {showImport && (
        <div className="bg-white border rounded-xl p-5 mb-4">
          <h3 className="font-semibold mb-3">Import from Question Bank</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium mb-1">Select Question</label>
              <select value={importForm.question_id} onChange={(e) => setImportForm({ ...importForm, question_id: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm">
                <option value="">-- Select --</option>
                {bankQuestions.map((q) => (
                  <option key={q.id} value={q.id}>#{q.id} {q.question_type} - {q.sac_thue} ({new Date(q.created_at).toLocaleDateString()})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Title</label>
              <input value={importForm.title} onChange={(e) => setImportForm({ ...importForm, title: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="Short descriptive title" />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Exam Tricks</label>
              <input value={importForm.exam_tricks} onChange={(e) => setImportForm({ ...importForm, exam_tricks: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="Key tricks tested" />
            </div>
            <div className="flex gap-2">
              <button onClick={handleImportFromBank} className="px-4 py-2 bg-blue-500 text-white text-sm rounded-lg hover:bg-blue-600">
                Import
              </button>
              <button onClick={() => setShowImport(false)} className="px-4 py-2 border text-sm rounded-lg hover:bg-gray-50">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="text-center py-8 text-gray-400">Loading...</div>
      ) : items.length === 0 ? (
        <div className="text-center py-8 text-gray-400">No items yet. Click "+ Add" to create one, or use "Parse & Match File" to import from data files.</div>
      ) : (
        <div className="bg-white rounded-xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-gray-500">ID</th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Tax</th>
                {tab === 0 && <th className="text-left px-4 py-2 font-medium text-gray-500">Section</th>}
                {tab === 0 && <th className="text-left px-4 py-2 font-medium text-gray-500">Title</th>}
                {tab === 1 && <th className="text-left px-4 py-2 font-medium text-gray-500">Ref</th>}
                {tab === 2 && <th className="text-left px-4 py-2 font-medium text-gray-500">Type</th>}
                {tab === 2 && <th className="text-left px-4 py-2 font-medium text-gray-500">Title</th>}
                <th className="text-left px-4 py-2 font-medium text-gray-500">
                  {tab === 2 ? 'Tricks' : 'Tags'}
                </th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Content</th>
                <th className="text-right px-4 py-2 font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-400">{item.id}</td>
                  <td className="px-4 py-2">
                    <span className="bg-gray-100 text-xs px-2 py-0.5 rounded">{item.sac_thue}</span>
                  </td>
                  {tab === 0 && <td className="px-4 py-2 text-xs">{item.section_code || '-'}</td>}
                  {tab === 0 && <td className="px-4 py-2 text-xs">{item.section_title || '-'}</td>}
                  {tab === 1 && <td className="px-4 py-2 text-xs">{item.regulation_ref || '-'}</td>}
                  {tab === 2 && <td className="px-4 py-2"><span className="bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded">{item.question_type}</span></td>}
                  {tab === 2 && <td className="px-4 py-2 text-xs">{item.title || '-'}</td>}
                  <td className="px-4 py-2">
                    <div className="flex flex-wrap gap-1">
                      {(tab === 2 ? (item.exam_tricks || '') : (item.tags || '')).split(',').filter(Boolean).map((t, i) => (
                        <span key={i} className="bg-gray-100 text-gray-600 text-xs px-1.5 py-0.5 rounded">{t.trim()}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-500 max-w-xs truncate">{item.content?.slice(0, 80)}...</td>
                  <td className="px-4 py-2 text-right">
                    <button onClick={() => handleEdit(item)} className="text-brand-600 hover:underline text-xs mr-2">Edit</button>
                    <button onClick={() => handleDelete(item.id)} className="text-red-500 hover:underline text-xs">Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

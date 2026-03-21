import { useState, useEffect } from 'react'
import { api } from '../api'
import RichTextEditor from '../components/RichTextEditor'

const QUESTION_TYPES = ['MCQ', 'SCENARIO', 'LONGFORM']
const MCQ_SUBTYPES = ['MCQ-1', 'MCQ-N', 'MCQ-FIB']
const TAX_TYPES_DEFAULT = ['CIT', 'PIT', 'VAT', 'FCT', 'TAX-ADMIN', 'TP']

function useCurrentSession() {
  const [sessionId] = useState(() => localStorage.getItem('currentSessionId') || '')
  return sessionId
}

function Modal({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-5 w-full max-w-3xl mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h4 className="font-semibold text-base">{title}</h4>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}

function SampleForm({ initial, taxTypes, sessions, sessionId, onSave, onCancel }) {
  const [form, setForm] = useState({
    question_type: 'MCQ', question_subtype: '', tax_type: 'CIT',
    title: '', content: '', answer: '', marks: '', exam_ref: '',
    syllabus_codes: [], reg_codes: [], tags: '',
    exam_session_id: sessionId ? parseInt(sessionId) : null,
    ...initial,
  })
  const [saving, setSaving] = useState(false)
  const [suggestions, setSuggestions] = useState(null)
  const [suggestLoading, setSuggestLoading] = useState(false)
  const [savedCodes, setSavedCodes] = useState(false)
  const [savedItemId, setSavedItemId] = useState(initial?.id || null)

  const handleSave = async () => {
    if (!form.content.trim()) { alert('Question content is required'); return }
    setSaving(true)
    try {
      const payload = {
        ...form,
        marks: form.marks ? parseInt(form.marks) : null,
        syllabus_codes: typeof form.syllabus_codes === 'string'
          ? form.syllabus_codes.split(',').map((s) => s.trim()).filter(Boolean)
          : form.syllabus_codes || [],
        reg_codes: typeof form.reg_codes === 'string'
          ? form.reg_codes.split(',').map((s) => s.trim()).filter(Boolean)
          : form.reg_codes || [],
        question_subtype: form.question_type === 'MCQ' ? form.question_subtype : null,
      }
      const saved = await onSave(payload)
      const itemId = saved?.id || initial?.id
      if (itemId) {
        setSavedItemId(itemId)
        setSuggestions(null)
        setSavedCodes(false)
        setSuggestLoading(true)
        api.suggestCodes({
          content: form.content + ' ' + (form.answer || ''),
          tax_type: form.tax_type,
          session_id: sessionId,
          question_type: form.question_type,
        }).then((s) => { setSuggestions(s); setSuggestLoading(false) })
          .catch(() => setSuggestLoading(false))
      }
    } catch (err) { alert('Save failed: ' + err.message) }
    finally { setSaving(false) }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="text-xs font-medium block mb-1">Question Type</label>
          <select value={form.question_type} onChange={(e) => setForm({ ...form, question_type: e.target.value, question_subtype: '' })}
            className="w-full border rounded px-3 py-1.5 text-sm">
            {QUESTION_TYPES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </div>
        {form.question_type === 'MCQ' && (
          <div>
            <label className="text-xs font-medium block mb-1">MCQ Subtype</label>
            <select value={form.question_subtype} onChange={(e) => setForm({ ...form, question_subtype: e.target.value })}
              className="w-full border rounded px-3 py-1.5 text-sm">
              <option value="">None</option>
              {MCQ_SUBTYPES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
        )}
        <div>
          <label className="text-xs font-medium block mb-1">Tax Type</label>
          <select value={form.tax_type} onChange={(e) => setForm({ ...form, tax_type: e.target.value })}
            className="w-full border rounded px-3 py-1.5 text-sm">
            {taxTypes.map((t) => <option key={typeof t === 'string' ? t : t.code} value={typeof t === 'string' ? t : t.code}>{typeof t === 'string' ? t : `${t.code} — ${t.name}`}</option>)}
          </select>
        </div>
      </div>
      <div>
        <label className="text-xs font-medium block mb-1">Title</label>
        <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
          className="w-full border rounded px-3 py-1.5 text-sm" placeholder="Short title for this question" />
      </div>
      <div>
        <label className="text-xs font-medium block mb-1">Question Content</label>
        <div style={{ paddingBottom: 50 }}>
          <RichTextEditor value={form.content} onChange={(val) => setForm({ ...form, content: val })}
            placeholder="Question text..." height={200} />
        </div>
      </div>
      <div>
        <label className="text-xs font-medium block mb-1">Answer / Model Answer</label>
        <div style={{ paddingBottom: 50 }}>
          <RichTextEditor value={form.answer} onChange={(val) => setForm({ ...form, answer: val })}
            placeholder="Model answer..." height={150} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium block mb-1">Marks</label>
          <input type="number" value={form.marks} onChange={(e) => setForm({ ...form, marks: e.target.value })}
            className="w-full border rounded px-3 py-1.5 text-sm" placeholder="2" />
        </div>
        <div>
          <label className="text-xs font-medium block mb-1">Exam Reference</label>
          <input value={form.exam_ref} onChange={(e) => setForm({ ...form, exam_ref: e.target.value })}
            className="w-full border rounded px-3 py-1.5 text-sm" placeholder="ACCA TX(VNM) June 2024" />
        </div>
        <div>
          <label className="text-xs font-medium block mb-1">Syllabus Codes (comma-separated)</label>
          <input value={Array.isArray(form.syllabus_codes) ? form.syllabus_codes.join(', ') : form.syllabus_codes}
            onChange={(e) => setForm({ ...form, syllabus_codes: e.target.value })}
            className="w-full border rounded px-3 py-1.5 text-sm" placeholder="B2a, B2c" />
        </div>
        <div>
          <label className="text-xs font-medium block mb-1">RegCodes (comma-separated)</label>
          <input value={Array.isArray(form.reg_codes) ? form.reg_codes.join(', ') : form.reg_codes}
            onChange={(e) => setForm({ ...form, reg_codes: e.target.value })}
            className="w-full border rounded px-3 py-1.5 text-sm" placeholder="CIT-ND320-Art9-P1" />
        </div>
      </div>
      <div>
        <label className="text-xs font-medium block mb-1">Tags</label>
        <input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })}
          className="w-full border rounded px-3 py-1.5 text-sm" placeholder="salary, deductible, CIT" />
      </div>
      <div>
        <label className="text-xs font-medium block mb-1">Exam Session</label>
        <select
          value={form.exam_session_id || ''}
          onChange={(e) => setForm({ ...form, exam_session_id: e.target.value ? parseInt(e.target.value) : null })}
          className="w-full border rounded px-3 py-1.5 text-sm">
          <option value="">— None (global) —</option>
          {sessions.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>
      <div className="flex gap-2 pt-2">
        <button onClick={handleSave} disabled={saving}
          className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600 disabled:opacity-50">
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button onClick={onCancel} className="px-4 py-2 border text-sm rounded-lg hover:bg-gray-50">Cancel</button>
      </div>

      {/* Suggestion panel — shows after save */}
      {(suggestLoading || suggestions) && (
        <div className="mt-4 border rounded-xl overflow-hidden">
          <div className="bg-amber-50 px-4 py-2 border-b flex items-center gap-2">
            <span className="text-sm font-semibold text-amber-700">🏷️ Suggested Tags</span>
            {suggestLoading && <span className="text-xs text-gray-400 ml-auto animate-pulse">Analysing...</span>}
          </div>
          {!suggestLoading && suggestions && (
            <div className="p-3 space-y-2">
              {suggestions.syllabus_codes?.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {suggestions.syllabus_codes.map((s) => (
                    <span key={s.code} className="px-2 py-0.5 bg-blue-50 border border-blue-200 rounded text-xs font-mono text-blue-700">{s.code}</span>
                  ))}
                </div>
              )}
              {suggestions.reg_codes?.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {suggestions.reg_codes.map((r) => (
                    <span key={r.reg_code} className="px-2 py-0.5 bg-green-50 border border-green-200 rounded text-xs font-mono text-green-700">{r.reg_code}</span>
                  ))}
                </div>
              )}
              {(suggestions.syllabus_codes?.length > 0 || suggestions.reg_codes?.length > 0) && !savedCodes && savedItemId && (
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={async () => {
                      await api.updateSampleQuestionCodes(savedItemId, {
                        syllabus_codes: suggestions.syllabus_codes.map((s) => s.code),
                        reg_codes: suggestions.reg_codes.map((r) => r.reg_code),
                      })
                      setSavedCodes(true)
                    }}
                    className="px-3 py-1 bg-[#028a39] text-white rounded text-xs hover:bg-[#027a32]"
                  >
                    ✓ Save tags
                  </button>
                  <button onClick={() => setSuggestions(null)} className="px-3 py-1 text-gray-500 text-xs hover:text-gray-700">Dismiss</button>
                </div>
              )}
              {savedCodes && <p className="text-xs text-green-600">✓ Tags saved</p>}
              {suggestions.syllabus_codes?.length === 0 && suggestions.reg_codes?.length === 0 && (
                <p className="text-xs text-gray-400">No matching references found.</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function SampleQuestions() {
  const sessionId = useCurrentSession()
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ question_type: '', tax_type: '', subtype: '', search: '', exam_session_id: '' })
  const [taxTypes, setTaxTypes] = useState(TAX_TYPES_DEFAULT)
  const [sessions, setSessions] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [editItem, setEditItem] = useState(null)
  const [viewItem, setViewItem] = useState(null)

  useEffect(() => {
    api.getSessions().then(setSessions).catch(() => {})
  }, [])

  useEffect(() => {
    if (!sessionId) return
    api.getSessionSettings(sessionId)
      .then((d) => { if (d.tax_types?.length) setTaxTypes(d.tax_types) })
      .catch(() => {})
  }, [sessionId])

  const fetchItems = async () => {
    setLoading(true)
    try {
      const params = {}
      if (filters.question_type) params.question_type = filters.question_type
      if (filters.tax_type) params.tax_type = filters.tax_type
      if (filters.subtype) params.subtype = filters.subtype
      if (filters.search) params.search = filters.search
      if (filters.exam_session_id) params.exam_session_id = filters.exam_session_id
      const data = await api.getSampleQuestions(params)
      setItems(data.items || [])
      setTotal(data.total || 0)
    } catch { setItems([]); setTotal(0) }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchItems() }, [filters])

  const handleCreate = async (payload) => {
    const saved = await api.createSampleQuestion(payload)
    fetchItems()
    return saved
  }

  const handleUpdate = async (payload) => {
    await api.updateSampleQuestion(editItem.id, payload)
    fetchItems()
    return { id: editItem.id }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this sample question?')) return
    try { await api.deleteSampleQuestion(id); fetchItems() } catch { }
  }

  const typeLabel = (item) => {
    let label = item.question_type
    if (item.question_subtype) label += ` • ${item.question_subtype}`
    return label
  }

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Sample Questions</h2>
        <button onClick={() => setShowAdd(true)}
          className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600">
          + Add Sample
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-5 flex-wrap">
        <select value={filters.exam_session_id} onChange={(e) => setFilters({ ...filters, exam_session_id: e.target.value })}
          className="border rounded px-3 py-1.5 text-sm">
          <option value="">All Sessions</option>
          {sessions.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <select value={filters.question_type} onChange={(e) => setFilters({ ...filters, question_type: e.target.value })}
          className="border rounded px-3 py-1.5 text-sm">
          <option value="">All Types</option>
          {QUESTION_TYPES.map((t) => <option key={t}>{t}</option>)}
        </select>
        <select value={filters.tax_type} onChange={(e) => setFilters({ ...filters, tax_type: e.target.value })}
          className="border rounded px-3 py-1.5 text-sm">
          <option value="">All Tax Types</option>
          {taxTypes.map((t) => (
            <option key={typeof t === 'string' ? t : t.code} value={typeof t === 'string' ? t : t.code}>
              {typeof t === 'string' ? t : `${t.code} — ${t.name}`}
            </option>
          ))}
        </select>
        {filters.question_type === 'MCQ' && (
          <select value={filters.subtype} onChange={(e) => setFilters({ ...filters, subtype: e.target.value })}
            className="border rounded px-3 py-1.5 text-sm">
            <option value="">All Subtypes</option>
            {MCQ_SUBTYPES.map((t) => <option key={t}>{t}</option>)}
          </select>
        )}
        <input value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          placeholder="Search..." className="border rounded px-3 py-1.5 text-sm flex-1 min-w-32" />
        <span className="text-xs text-gray-400 self-center">{total} results</span>
      </div>

      {/* List */}
      {loading ? (
        <div className="text-center py-8 text-gray-400">Loading...</div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="bg-white border rounded-xl p-4 hover:shadow-sm transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-xs font-semibold text-brand-700 bg-brand-50 px-2 py-0.5 rounded">{typeLabel(item)}</span>
                    <span className="text-xs text-gray-500">{item.tax_type}</span>
                    {item.marks && <span className="text-xs text-gray-400">{item.marks} marks</span>}
                    {item.exam_ref && <span className="text-xs text-gray-400">• {item.exam_ref}</span>}
                  </div>
                  <p className="text-sm font-medium mb-1">{item.title || '(No title)'}</p>
                  <div className="text-xs text-gray-500 line-clamp-2"
                    dangerouslySetInnerHTML={{ __html: (item.content || '').replace(/<[^>]+>/g, ' ').substring(0, 200) }} />
                  {((item.syllabus_codes || []).length > 0 || (item.reg_codes || []).length > 0 || item.exam_session_id) && (
                    <div className="flex gap-2 mt-1 flex-wrap">
                      {(item.syllabus_codes || []).map((c) => (
                        <span key={c} className="text-xs bg-gray-100 px-1.5 py-0.5 rounded font-mono">{c}</span>
                      ))}
                      {(item.reg_codes || []).slice(0, 2).map((c) => (
                        <span key={c} className="text-xs bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded font-mono">{c}</span>
                      ))}
                      {item.exam_session_id && (
                        <span className="inline-flex items-center px-2 py-0.5 bg-purple-50 text-purple-600 text-xs rounded border border-purple-100">
                          {sessions.find((s) => s.id === item.exam_session_id)?.name || `Session ${item.exam_session_id}`}
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex gap-2 ml-4 shrink-0">
                  <button onClick={() => setViewItem(item)} className="text-xs text-gray-500 hover:text-gray-700 border rounded px-2 py-1">View</button>
                  <button onClick={() => setEditItem(item)} className="text-xs text-brand-600 hover:underline">Edit</button>
                  <button onClick={() => handleDelete(item.id)} className="text-xs text-red-500 hover:underline">Delete</button>
                </div>
              </div>
            </div>
          ))}
          {items.length === 0 && (
            <div className="text-center py-10 text-gray-400 border-2 border-dashed rounded-xl">
              No sample questions yet. Add your first one!
            </div>
          )}
        </div>
      )}

      {/* Add Modal */}
      {showAdd && (
        <Modal title="Add Sample Question" onClose={() => setShowAdd(false)}>
          <SampleForm taxTypes={taxTypes} sessions={sessions} sessionId={sessionId} onSave={handleCreate} onCancel={() => setShowAdd(false)} />
        </Modal>
      )}

      {/* Edit Modal */}
      {editItem && (
        <Modal title="Edit Sample Question" onClose={() => setEditItem(null)}>
          <SampleForm initial={editItem} taxTypes={taxTypes} sessions={sessions} sessionId={sessionId} onSave={handleUpdate} onCancel={() => setEditItem(null)} />
        </Modal>
      )}

      {/* View Modal */}
      {viewItem && (
        <Modal title={viewItem.title || 'Sample Question'} onClose={() => setViewItem(null)}>
          <div className="space-y-4">
            <div className="flex gap-2 flex-wrap text-xs">
              <span className="bg-brand-100 text-brand-700 px-2 py-0.5 rounded font-medium">{typeLabel(viewItem)}</span>
              <span className="bg-gray-100 px-2 py-0.5 rounded">{viewItem.tax_type}</span>
              {viewItem.marks && <span className="bg-gray-100 px-2 py-0.5 rounded">{viewItem.marks} marks</span>}
              {viewItem.exam_ref && <span className="text-gray-500">{viewItem.exam_ref}</span>}
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">Question:</p>
              <div className="prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: viewItem.content }} />
            </div>
            {viewItem.answer && (
              <div className="border-t pt-4">
                <p className="text-xs font-medium text-gray-500 mb-1">Answer:</p>
                <div className="prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: viewItem.answer }} />
              </div>
            )}
            {((viewItem.syllabus_codes || []).length > 0 || (viewItem.reg_codes || []).length > 0) && (
              <div className="border-t pt-3 flex gap-2 flex-wrap text-xs">
                {(viewItem.syllabus_codes || []).map((c) => <span key={c} className="bg-gray-100 px-2 py-0.5 rounded font-mono">{c}</span>)}
                {(viewItem.reg_codes || []).map((c) => <span key={c} className="bg-blue-50 text-blue-600 px-2 py-0.5 rounded font-mono">{c}</span>)}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}

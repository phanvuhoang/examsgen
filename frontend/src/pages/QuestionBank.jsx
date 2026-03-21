import { useState, useEffect } from 'react'
import { api } from '../api'

const TYPE_OPTIONS = [
  { value: '', label: 'All Types' },
  { value: 'MCQ', label: 'MCQ' },
  { value: 'SCENARIO_10', label: 'Scenario (10 marks)' },
  { value: 'LONGFORM_15', label: 'Long-form (15 marks)' },
]
const SAC_THUE_OPTIONS = ['', 'CIT', 'VAT', 'PIT', 'FCT', 'TP', 'ADMIN']

export default function QuestionBank() {
  const [questions, setQuestions] = useState([])
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState({ question_type: '', sac_thue: '', starred: '', session_id: '', syllabus_code: '' })
  const [selected, setSelected] = useState(new Set())
  const [viewing, setViewing] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sessions, setSessions] = useState([])

  useEffect(() => {
    api.getSessions().then(setSessions).catch(() => {})
  }, [])

  const load = async () => {
    setLoading(true)
    try {
      const params = {}
      if (filters.question_type) params.question_type = filters.question_type
      if (filters.sac_thue) params.sac_thue = filters.sac_thue
      if (filters.starred === 'true') params.starred = true
      if (filters.session_id) params.session_id = filters.session_id
      if (filters.syllabus_code) params.syllabus_code = filters.syllabus_code
      const data = await api.getQuestions(params)
      setQuestions(data.questions)
      setTotal(data.total)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [filters])

  const handleStar = async (id) => {
    await api.toggleStar(id)
    load()
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this question?')) return
    await api.deleteQuestion(id)
    setViewing(null)
    load()
  }

  const handleExport = async () => {
    const ids = [...selected]
    if (ids.length === 0) return alert('Select questions to export')
    try {
      const blob = await api.exportWord(ids)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `ExamsGen_Export.docx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      alert('Export failed: ' + err.message)
    }
  }

  const viewQuestion = async (id) => {
    const data = await api.getQuestion(id)
    setViewing(data)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Question Bank</h2>
        <div className="flex gap-2">
          <span className="text-sm text-gray-500 self-center">{total} questions</span>
          {selected.size > 0 && (
            <button onClick={handleExport}
              className="bg-blue-500 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-600">
              Export {selected.size} Selected
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-5">
        <select value={filters.session_id}
          onChange={(e) => setFilters({ ...filters, session_id: e.target.value })}
          className="border rounded-lg px-3 py-2 text-sm">
          <option value="">All Sessions</option>
          {sessions.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <select value={filters.question_type}
          onChange={(e) => setFilters({ ...filters, question_type: e.target.value })}
          className="border rounded-lg px-3 py-2 text-sm">
          {TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select value={filters.sac_thue}
          onChange={(e) => setFilters({ ...filters, sac_thue: e.target.value })}
          className="border rounded-lg px-3 py-2 text-sm">
          {SAC_THUE_OPTIONS.map((s) => <option key={s} value={s}>{s || 'All Tax Types'}</option>)}
        </select>
        <select value={filters.starred}
          onChange={(e) => setFilters({ ...filters, starred: e.target.value })}
          className="border rounded-lg px-3 py-2 text-sm">
          <option value="">All</option>
          <option value="true">Starred Only</option>
        </select>
        <input
          value={filters.syllabus_code}
          onChange={(e) => setFilters({ ...filters, syllabus_code: e.target.value })}
          placeholder="Syllabus code... e.g. B2a"
          className="border rounded-lg px-3 py-2 text-sm w-40"
        />
      </div>

      {/* Questions list */}
      {loading ? (
        <p className="text-gray-400">Loading...</p>
      ) : questions.length === 0 ? (
        <p className="text-gray-400">No questions found.</p>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border divide-y">
          {questions.map((q) => (
            <div key={q.id} className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50">
              <input
                type="checkbox"
                checked={selected.has(q.id)}
                onChange={(e) => {
                  const next = new Set(selected)
                  e.target.checked ? next.add(q.id) : next.delete(q.id)
                  setSelected(next)
                }}
                className="rounded"
              />
              <div className="flex-1 cursor-pointer" onClick={() => viewQuestion(q.id)}>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                    q.question_type === 'MCQ' ? 'bg-blue-100 text-blue-700' :
                    q.question_type === 'SCENARIO_10' ? 'bg-purple-100 text-purple-700' :
                    'bg-orange-100 text-orange-700'
                  }`}>{q.question_number || q.question_type}</span>
                  <span className="text-sm font-medium">{q.sac_thue}</span>
                  <span className="text-xs text-gray-400">{q.exam_session}</span>
                  {q.syllabus_codes?.map((c) => (
                    <span key={c} className="px-1.5 py-0.5 bg-blue-50 text-blue-600 text-xs font-mono rounded border border-blue-100">{c}</span>
                  ))}
                  {q.reg_codes?.map((c) => (
                    <span key={c} className="px-1.5 py-0.5 bg-green-50 text-green-600 text-xs font-mono rounded border border-green-100">{c}</span>
                  ))}
                  {q.exam_session_id && (
                    <span className="px-2 py-0.5 bg-purple-50 text-purple-600 text-xs rounded border border-purple-100">
                      {sessions.find((s) => s.id === q.exam_session_id)?.name || `Session ${q.exam_session_id}`}
                    </span>
                  )}
                </div>
              </div>
              <button onClick={() => handleStar(q.id)} className="text-lg">
                {q.is_starred ? <span className="text-yellow-500">&#9733;</span> : <span className="text-gray-300">&#9734;</span>}
              </button>
              <span className="text-xs text-gray-400 w-20 text-right">
                {q.created_at ? new Date(q.created_at).toLocaleDateString() : ''}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Question Detail Modal */}
      {viewing && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setViewing(null)}>
          <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[85vh] overflow-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">
                {viewing.question_number || viewing.question_type} — {viewing.sac_thue}
              </h3>
              <div className="flex gap-2">
                <button onClick={() => handleDelete(viewing.id)}
                  className="text-red-500 hover:text-red-700 text-sm">Delete</button>
                <button onClick={() => setViewing(null)}
                  className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
              </div>
            </div>
            <div className="text-xs text-gray-500 mb-4 flex gap-4">
              <span>Model: {viewing.model_used}</span>
              <span>Provider: {viewing.provider_used}</span>
              <span>{viewing.created_at ? new Date(viewing.created_at).toLocaleString() : ''}</span>
            </div>
            <div className="question-html" dangerouslySetInnerHTML={{ __html: viewing.content_html }} />
          </div>
        </div>
      )}
    </div>
  )
}

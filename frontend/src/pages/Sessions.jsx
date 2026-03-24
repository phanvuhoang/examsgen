import { useState, useEffect } from 'react'
import { api } from '../api'

function VariableRow({ variable, onUpdate, onDelete }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    label: variable.label,
    value: variable.value,
    unit: variable.unit || '',
    description: variable.description || '',
  })

  if (editing) {
    return (
      <div className="border rounded-lg p-3 bg-white space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })}
            className="col-span-2 border rounded px-2 py-1 text-xs" placeholder="Label" />
          <input value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })}
            className="border rounded px-2 py-1 text-xs" placeholder="Value" />
          <input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })}
            className="border rounded px-2 py-1 text-xs" placeholder="Unit" />
        </div>
        <div className="flex gap-2">
          <button onClick={async () => { await onUpdate(form); setEditing(false) }}
            className="text-xs px-3 py-1 bg-brand-500 text-white rounded">Save</button>
          <button onClick={() => setEditing(false)} className="text-xs px-3 py-1 border rounded">Cancel</button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-3 border rounded-lg px-3 py-2 bg-white text-xs">
      <div className="flex-1 min-w-0">
        <span className="font-medium text-gray-700">{variable.label}</span>
        <span className="ml-2 font-mono text-brand-600">{variable.value}</span>
        {variable.unit && <span className="ml-1 text-gray-400">{variable.unit}</span>}
      </div>
      <button onClick={() => setEditing(true)} className="text-gray-400 hover:text-gray-700 px-1">✎</button>
      <button onClick={onDelete} className="text-red-400 hover:text-red-600 px-1">✕</button>
    </div>
  )
}

export default function Sessions() {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editSession, setEditSession] = useState(null)
  const [form, setForm] = useState({ name: '', exam_date: '', assumed_date: '' })
  const [carryFromId, setCarryFromId] = useState('')
  const [saving, setSaving] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const [variables, setVariables] = useState([])
  const [newVar, setNewVar] = useState({ key: '', label: '', value: '', unit: '', description: '' })
  const [addingVar, setAddingVar] = useState(false)

  const fetchSessions = async () => {
    try {
      const data = await api.getSessions()
      setSessions(data)
    } catch { setSessions([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchSessions() }, [])

  useEffect(() => {
    if (editSession?.id) {
      api.getSessionVariables(editSession.id).then(setVariables).catch(() => setVariables([]))
    } else {
      setVariables([])
    }
  }, [editSession])

  const handleNew = () => {
    setEditSession(null)
    setForm({ name: '', exam_date: '', assumed_date: '' })
    setCarryFromId('')
    setShowForm(true)
  }

  const handleEdit = (s) => {
    setEditSession(s)
    setForm({ name: s.name, exam_date: s.exam_date || '', assumed_date: s.assumed_date || '' })
    setShowForm(true)
  }

  const handleSave = async () => {
    if (!form.name.trim()) { alert('Session name is required'); return }
    setSaving(true)
    try {
      if (editSession) {
        await api.updateSession(editSession.id, form)
      } else {
        const res = await api.createSession(form)
        if (carryFromId) {
          await api.carryForward(res.id, parseInt(carryFromId))
        }
      }
      setShowForm(false)
      fetchSessions()
    } catch (err) { alert('Save failed: ' + err.message) }
    finally { setSaving(false) }
  }

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm) return
    try {
      await api.deleteSession(deleteConfirm.id)
      if (localStorage.getItem('currentSessionId') === String(deleteConfirm.id)) {
        localStorage.removeItem('currentSessionId')
      }
      setDeleteConfirm(null)
      fetchSessions()
    } catch (err) { alert('Delete failed: ' + err.message) }
  }

  if (loading) return <div className="text-center py-8 text-gray-400">Loading...</div>

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Exam Sessions</h2>
        <button onClick={handleNew}
          className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600">
          + New Session
        </button>
      </div>

      {/* Create/Edit Form */}
      {showForm && (
        <div className="bg-white border rounded-xl p-5 mb-6">
          <h3 className="font-semibold mb-4">{editSession ? 'Edit' : 'New'} Session</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs font-medium mb-1">Session Name *</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="e.g. June 2026"
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Exam Date (short)</label>
              <input
                value={form.exam_date}
                onChange={(e) => setForm({ ...form, exam_date: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="e.g. Jun2026"
              />
              <p className="text-xs text-gray-400 mt-1">Used in prompt as exam session label</p>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Assumed Date (for scenarios)</label>
              <input
                value={form.assumed_date}
                onChange={(e) => setForm({ ...form, assumed_date: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="e.g. 1 June 2026"
              />
              <p className="text-xs text-gray-400 mt-1">Used in scenario questions: "Assume today is..."</p>
            </div>
            {!editSession && sessions.length > 0 && (
              <div className="col-span-2">
                <label className="block text-xs font-medium mb-1">Carry Forward Files From</label>
                <select
                  value={carryFromId}
                  onChange={(e) => setCarryFromId(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                >
                  <option value="">— No carry forward —</option>
                  {sessions.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
                <p className="text-xs text-gray-400 mt-1">Copies all uploaded files from the selected session</p>
              </div>
            )}
            {editSession && (
              <div className="col-span-2 border-t pt-4">
                <div className="flex items-center justify-between mb-3">
                  <label className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                    Global Variables
                  </label>
                  <button
                    type="button"
                    onClick={() => setAddingVar(true)}
                    className="text-xs px-2 py-1 bg-brand-50 text-brand-600 border border-brand-200 rounded hover:bg-brand-100"
                  >
                    + Add Variable
                  </button>
                </div>
                <div className="space-y-2">
                  {variables.map((v) => (
                    <VariableRow
                      key={v.id}
                      variable={v}
                      onUpdate={async (data) => {
                        await api.updateSessionVariable(editSession.id, v.id, data)
                        api.getSessionVariables(editSession.id).then(setVariables)
                      }}
                      onDelete={async () => {
                        await api.deleteSessionVariable(editSession.id, v.id)
                        setVariables(prev => prev.filter(x => x.id !== v.id))
                      }}
                    />
                  ))}
                  {addingVar && (
                    <div className="border rounded-lg p-3 bg-gray-50 space-y-2">
                      <div className="grid grid-cols-2 gap-2">
                        <input placeholder="Key (e.g. exchange_rate_usd_vnd)" value={newVar.key}
                          onChange={(e) => setNewVar({ ...newVar, key: e.target.value })}
                          className="col-span-2 border rounded px-2 py-1 text-xs" />
                        <input placeholder="Label (e.g. Exchange Rate 1 USD = ? VND)" value={newVar.label}
                          onChange={(e) => setNewVar({ ...newVar, label: e.target.value })}
                          className="col-span-2 border rounded px-2 py-1 text-xs" />
                        <input placeholder="Value (e.g. 25,450)" value={newVar.value}
                          onChange={(e) => setNewVar({ ...newVar, value: e.target.value })}
                          className="border rounded px-2 py-1 text-xs" />
                        <input placeholder="Unit (e.g. VND)" value={newVar.unit}
                          onChange={(e) => setNewVar({ ...newVar, unit: e.target.value })}
                          className="border rounded px-2 py-1 text-xs" />
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={async () => {
                            await api.createSessionVariable(editSession.id, newVar)
                            api.getSessionVariables(editSession.id).then(setVariables)
                            setNewVar({ key: '', label: '', value: '', unit: '', description: '' })
                            setAddingVar(false)
                          }}
                          className="text-xs px-3 py-1 bg-brand-500 text-white rounded hover:bg-brand-600"
                        >Save</button>
                        <button onClick={() => setAddingVar(false)}
                          className="text-xs px-3 py-1 border rounded hover:bg-gray-100">Cancel</button>
                      </div>
                    </div>
                  )}
                </div>
                <p className="text-xs text-gray-400 mt-2">
                  Variables are injected into every prompt for this session (exchange rates, salary caps, etc.)
                </p>
              </div>
            )}
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={handleSave} disabled={saving}
              className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600 disabled:opacity-50">
              {saving ? 'Saving...' : 'Save'}
            </button>
            <button onClick={() => setShowForm(false)}
              className="px-4 py-2 border text-sm rounded-lg hover:bg-gray-50">Cancel</button>
          </div>
        </div>
      )}

      {/* Session Cards */}
      <div className="space-y-3">
        {sessions.map((s) => (
          <div key={s.id} className={`bg-white rounded-xl border p-4 ${s.is_default ? 'ring-2 ring-brand-500' : ''}`}>
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold">{s.name}</h3>
                  {s.is_default && (
                    <span className="text-xs bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full">Active</span>
                  )}
                </div>
                <div className="text-xs text-gray-500 mt-1 flex gap-3">
                  {s.exam_date && <span>Exam: <strong>{s.exam_date}</strong></span>}
                  {s.assumed_date && <span>Scenario date: <strong>{s.assumed_date}</strong></span>}
                  <span>{s.file_count || 0} files</span>
                  <span>{s.question_count || 0} questions</span>
                </div>
              </div>
              <div className="flex gap-2 flex-wrap shrink-0">
                {!s.is_default && (
                  <button
                    onClick={() => api.setDefaultSession(s.id).then(() => {
                      window.dispatchEvent(new Event('storage'))
                      fetchSessions()
                    })}
                    className="text-xs text-gray-500 hover:text-brand-600 border rounded px-2 py-1"
                  >
                    Set Active
                  </button>
                )}
                <button onClick={() => handleEdit(s)}
                  className="text-xs text-brand-600 hover:underline border rounded px-2 py-1">
                  Edit
                </button>
                <button onClick={() => setDeleteConfirm(s)}
                  className="text-xs text-red-500 hover:underline border rounded px-2 py-1">
                  Delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Delete modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4">
            <h3 className="font-semibold mb-2">Delete "{deleteConfirm.name}"?</h3>
            <p className="text-sm text-gray-600 mb-1">This will permanently delete:</p>
            <ul className="text-sm text-gray-700 mb-3 list-disc list-inside">
              <li>All uploaded files</li>
              <li>All generated questions</li>
            </ul>
            <p className="text-xs text-red-600 font-medium mb-4">This cannot be undone.</p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 border text-sm rounded-lg hover:bg-gray-50">Cancel</button>
              <button onClick={handleDeleteConfirm}
                className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

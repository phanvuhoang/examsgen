import { useState, useEffect, useRef } from 'react'
import { api } from '../api'

const TAX_TYPES = ['CIT', 'VAT', 'PIT', 'FCT', 'TP', 'TaxAdmin']
const EXAM_TYPES = ['MCQ', 'Scenario', 'Longform', 'ALL']

const FILE_TABS = [
  { key: 'regulation', label: 'Regulations', desc: 'Tax law documents (.docx/.doc)' },
  { key: 'syllabus', label: 'Syllabus', desc: 'ACCA TX(VNM) syllabus files (.xlsx/.docx)' },
  { key: 'rates', label: 'Tax Rates', desc: 'Tax rate tables (.xlsx/.docx)' },
  { key: 'sample', label: 'Sample Questions', desc: 'Past exam sample questions (.docx)' },
]

function FileRow({ file, sessionId, onDelete, onToggle }) {
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async () => {
    if (!confirm(`Delete "${file.display_name || file.file_name}"?`)) return
    setDeleting(true)
    try {
      await api.deleteSessionFile(sessionId, file.id)
      onDelete(file.id)
    } catch (err) {
      alert('Delete failed: ' + err.message)
    } finally {
      setDeleting(false)
    }
  }

  const handleToggle = async () => {
    try {
      const res = await api.toggleSessionFile(sessionId, file.id)
      onToggle(file.id, res.is_active)
    } catch (err) {
      alert('Toggle failed: ' + err.message)
    }
  }

  const sizeKB = file.file_size ? Math.round(file.file_size / 1024) : null

  return (
    <div className={`flex items-center gap-3 px-4 py-3 hover:bg-gray-50 ${!file.is_active ? 'opacity-50' : ''}`}>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{file.display_name || file.file_name}</div>
        <div className="text-xs text-gray-400 flex gap-2 mt-0.5">
          <span className="font-mono bg-gray-100 px-1 rounded">{file.tax_type || 'ALL'}</span>
          {file.exam_type && file.exam_type !== 'ALL' && (
            <span className="font-mono bg-blue-50 text-blue-600 px-1 rounded">{file.exam_type}</span>
          )}
          {sizeKB && <span>{sizeKB} KB</span>}
          <span className="text-gray-300">{file.file_name}</span>
        </div>
      </div>
      <button
        onClick={handleToggle}
        title={file.is_active ? 'Deactivate' : 'Activate'}
        className={`text-xs px-2 py-1 rounded border transition-colors ${
          file.is_active
            ? 'bg-green-50 border-green-200 text-green-700 hover:bg-green-100'
            : 'bg-gray-50 border-gray-200 text-gray-500 hover:bg-gray-100'
        }`}
      >
        {file.is_active ? 'Active' : 'Inactive'}
      </button>
      <button
        onClick={handleDelete}
        disabled={deleting}
        className="text-red-400 hover:text-red-600 text-sm disabled:opacity-40 px-1"
      >
        {deleting ? '...' : '✕'}
      </button>
    </div>
  )
}

function UploadButton({ sessionId, fileType, onUploaded }) {
  const [uploading, setUploading] = useState(false)
  const [taxType, setTaxType] = useState('CIT')
  const [examType, setExamType] = useState('ALL')
  const [displayName, setDisplayName] = useState('')
  const [showForm, setShowForm] = useState(false)
  const fileRef = useRef(null)

  const handleFileChange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setDisplayName(file.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '))
    setShowForm(true)
  }

  const handleUpload = async () => {
    const file = fileRef.current?.files[0]
    if (!file) return
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('file_type', fileType)
      fd.append('tax_type', taxType)
      fd.append('exam_type', examType)
      fd.append('display_name', displayName || file.name)
      await api.uploadSessionFile(sessionId, fd)
      setShowForm(false)
      setDisplayName('')
      if (fileRef.current) fileRef.current.value = ''
      onUploaded()
    } catch (err) {
      alert('Upload failed: ' + err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div>
      <label className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-500 hover:bg-brand-600 text-white text-sm rounded cursor-pointer">
        + Upload
        <input
          ref={fileRef}
          type="file"
          accept=".docx,.doc,.xlsx,.xls,.pdf"
          className="hidden"
          onChange={handleFileChange}
        />
      </label>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl p-5 max-w-md w-full space-y-3">
            <h4 className="font-semibold">Upload {fileType} file</h4>

            <div>
              <label className="block text-xs font-medium mb-1">Display Name</label>
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="e.g. CIT Law 67/2025"
              />
            </div>

            <div>
              <label className="block text-xs font-medium mb-1">Tax Type</label>
              <select value={taxType} onChange={(e) => setTaxType(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm">
                {TAX_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                <option value="ALL">ALL (all tax types)</option>
              </select>
            </div>

            {fileType === 'sample' && (
              <div>
                <label className="block text-xs font-medium mb-1">Exam Type</label>
                <select value={examType} onChange={(e) => setExamType(e.target.value)}
                  className="w-full border rounded px-3 py-2 text-sm">
                  {EXAM_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            )}

            <div className="flex gap-2 pt-2">
              <button
                onClick={handleUpload}
                disabled={uploading}
                className="px-4 py-2 bg-brand-500 text-white text-sm rounded-lg hover:bg-brand-600 disabled:opacity-50"
              >
                {uploading ? 'Uploading...' : 'Upload'}
              </button>
              <button
                onClick={() => { setShowForm(false); if (fileRef.current) fileRef.current.value = '' }}
                className="px-4 py-2 border text-sm rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Documents() {
  const [sessions, setSessions] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [activeTab, setActiveTab] = useState('regulation')
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)

  // Load sessions
  useEffect(() => {
    api.getSessions().then((data) => {
      setSessions(data)
      const stored = localStorage.getItem('currentSessionId')
      const match = data.find((s) => String(s.id) === stored) || data.find((s) => s.is_default)
      if (match) setSessionId(match.id)
    }).catch(() => {})
  }, [])

  // Load files when session or tab changes
  useEffect(() => {
    if (!sessionId) return
    setLoading(true)
    api.getSessionFiles(sessionId, activeTab)
      .then(setFiles)
      .catch(() => setFiles([]))
      .finally(() => setLoading(false))
  }, [sessionId, activeTab])

  const handleDelete = (fileId) => {
    setFiles((prev) => prev.filter((f) => f.id !== fileId))
  }

  const handleToggle = (fileId, isActive) => {
    setFiles((prev) => prev.map((f) => f.id === fileId ? { ...f, is_active: isActive } : f))
  }

  const handleUploaded = () => {
    if (!sessionId) return
    api.getSessionFiles(sessionId, activeTab)
      .then(setFiles)
      .catch(() => {})
  }

  // Group regulation files by tax type for display
  const filesByTaxType = files.reduce((acc, f) => {
    const key = f.tax_type || 'ALL'
    if (!acc[key]) acc[key] = []
    acc[key].push(f)
    return acc
  }, {})

  const currentTab = FILE_TABS.find((t) => t.key === activeTab)

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Documents</h2>
        {sessions.length > 0 && (
          <select
            value={sessionId || ''}
            onChange={(e) => setSessionId(parseInt(e.target.value))}
            className="border rounded-lg px-3 py-2 text-sm"
          >
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>{s.name}{s.is_default ? ' (active)' : ''}</option>
            ))}
          </select>
        )}
      </div>

      {!sessionId ? (
        <div className="text-gray-400 text-center py-12">Select a session to manage documents.</div>
      ) : (
        <>
          {/* Tabs */}
          <div className="flex gap-1 mb-5 border-b">
            {FILE_TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
                  activeTab === tab.key
                    ? 'border-brand-500 text-brand-700'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab header + upload */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm text-gray-500">{currentTab?.desc}</p>
              <p className="text-xs text-gray-400 mt-0.5">{files.length} file{files.length !== 1 ? 's' : ''}</p>
            </div>
            <UploadButton
              sessionId={sessionId}
              fileType={activeTab}
              onUploaded={handleUploaded}
            />
          </div>

          {/* File list */}
          {loading ? (
            <div className="text-gray-400 text-sm py-8 text-center">Loading...</div>
          ) : files.length === 0 ? (
            <div className="text-gray-400 text-sm py-12 text-center border-2 border-dashed rounded-xl">
              No {currentTab?.label.toLowerCase()} files uploaded yet.
              <br />
              <span className="text-xs">Use the Upload button above to add files.</span>
            </div>
          ) : activeTab === 'regulation' ? (
            // Regulations: group by tax type
            <div className="bg-white rounded-xl border divide-y">
              {TAX_TYPES.filter((tt) => filesByTaxType[tt]?.length > 0).map((tt) => (
                <div key={tt}>
                  <div className="px-4 py-2 bg-gray-50 text-xs font-semibold text-gray-600 uppercase tracking-wide">
                    {tt} ({filesByTaxType[tt].length})
                  </div>
                  <div className="divide-y">
                    {filesByTaxType[tt].map((f) => (
                      <FileRow key={f.id} file={f} sessionId={sessionId} onDelete={handleDelete} onToggle={handleToggle} />
                    ))}
                  </div>
                </div>
              ))}
              {filesByTaxType['ALL']?.length > 0 && (
                <div>
                  <div className="px-4 py-2 bg-gray-50 text-xs font-semibold text-gray-600 uppercase tracking-wide">
                    ALL ({filesByTaxType['ALL'].length})
                  </div>
                  <div className="divide-y">
                    {filesByTaxType['ALL'].map((f) => (
                      <FileRow key={f.id} file={f} sessionId={sessionId} onDelete={handleDelete} onToggle={handleToggle} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            // Other tabs: flat list
            <div className="bg-white rounded-xl border divide-y">
              {files.map((f) => (
                <FileRow key={f.id} file={f} sessionId={sessionId} onDelete={handleDelete} onToggle={handleToggle} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

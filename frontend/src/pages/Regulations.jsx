import { useState, useEffect } from 'react'
import { api } from '../api'

const TABS = ['CIT', 'VAT', 'PIT', 'FCT', 'TP', 'ADMIN', 'SHARED']

export default function Regulations() {
  const [activeTab, setActiveTab] = useState('CIT')
  const [regulations, setRegulations] = useState([])
  const [loading, setLoading] = useState(true)
  const [preview, setPreview] = useState(null)
  const [uploading, setUploading] = useState(false)

  // Upload form state
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadName, setUploadName] = useState('')
  const [uploadLoai, setUploadLoai] = useState('LAW')

  const load = async () => {
    setLoading(true)
    try {
      const data = await api.getRegulations(activeTab)
      setRegulations(data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [activeTab])

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!uploadFile) return
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', uploadFile)
      form.append('sac_thue', activeTab)
      form.append('ten_van_ban', uploadName || uploadFile.name)
      form.append('loai', uploadLoai)
      form.append('ngon_ngu', 'ENG')
      await api.uploadRegulation(form)
      setUploadFile(null)
      setUploadName('')
      load()
    } catch (err) {
      alert('Upload failed: ' + err.message)
    } finally {
      setUploading(false)
    }
  }

  const handleToggle = async (id) => {
    await api.toggleRegulation(id)
    load()
  }

  const handlePreview = async (id) => {
    try {
      const data = await api.getRegulationText(id)
      setPreview(data)
    } catch (err) {
      alert('Preview failed: ' + err.message)
    }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Regulations</h2>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 rounded-lg p-1 w-fit">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab ? 'bg-white shadow text-brand-600' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Upload */}
      <form onSubmit={handleUpload} className="bg-white rounded-xl border p-4 mb-6">
        <h3 className="text-sm font-semibold mb-3">Upload New Document</h3>
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">File (.doc / .docx)</label>
            <input
              type="file"
              accept=".doc,.docx"
              onChange={(e) => setUploadFile(e.target.files[0])}
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div className="w-48">
            <label className="block text-xs text-gray-500 mb-1">Name (optional)</label>
            <input value={uploadName} onChange={(e) => setUploadName(e.target.value)}
              placeholder="Document name"
              className="w-full border rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="w-32">
            <label className="block text-xs text-gray-500 mb-1">Type</label>
            <select value={uploadLoai} onChange={(e) => setUploadLoai(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm">
              <option value="LAW">Law</option>
              <option value="DECREE">Decree</option>
              <option value="CIRCULAR">Circular</option>
              <option value="TAXRATES">Tax Rates</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={!uploadFile || uploading}
            className="bg-brand-500 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-brand-600 disabled:opacity-50"
          >
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
        </div>
      </form>

      {/* List */}
      {loading ? (
        <p className="text-gray-400">Loading...</p>
      ) : regulations.length === 0 ? (
        <p className="text-gray-400">No regulations for {activeTab}.</p>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border divide-y">
          {regulations.map((reg) => (
            <div key={reg.id} className="flex items-center justify-between px-4 py-3">
              <div>
                <p className="text-sm font-medium">{reg.ten_van_ban || reg.file_name}</p>
                <div className="flex gap-3 text-xs text-gray-400 mt-1">
                  <span className="px-2 py-0.5 bg-gray-100 rounded">{reg.loai}</span>
                  <span>{reg.ngon_ngu}</span>
                  <span>{reg.file_name}</span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button onClick={() => handlePreview(reg.id)}
                  className="text-brand-500 hover:text-brand-700 text-sm">Preview</button>
                <button
                  onClick={() => handleToggle(reg.id)}
                  className={`px-3 py-1 rounded-full text-xs font-medium ${
                    reg.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                  }`}
                >
                  {reg.is_active ? 'Active' : 'Inactive'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Preview Modal */}
      {preview && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setPreview(null)}>
          <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[85vh] overflow-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold">{preview.name}</h3>
              <button onClick={() => setPreview(null)} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
            </div>
            <pre className="whitespace-pre-wrap text-sm text-gray-700 bg-gray-50 p-4 rounded-lg max-h-[60vh] overflow-auto">
              {preview.text}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

import { useState } from 'react'
import { api } from '../api'

export default function Settings() {
  const [status, setStatus] = useState(null)

  const checkHealth = async () => {
    try {
      const data = await api.health()
      setStatus({ ok: true, message: `Service: ${data.service} — Status: ${data.status}` })
    } catch (err) {
      setStatus({ ok: false, message: err.message })
    }
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-bold mb-6">Settings</h2>

      {/* API Health */}
      <div className="bg-white rounded-xl border p-5 mb-6">
        <h3 className="font-semibold mb-3">System Health</h3>
        <button
          onClick={checkHealth}
          className="bg-brand-500 text-white px-4 py-2 rounded-lg text-sm hover:bg-brand-600"
        >
          Check Health
        </button>
        {status && (
          <p className={`mt-3 text-sm ${status.ok ? 'text-green-600' : 'text-red-600'}`}>
            {status.message}
          </p>
        )}
      </div>

      {/* Info */}
      <div className="bg-white rounded-xl border p-5 mb-6">
        <h3 className="font-semibold mb-3">Configuration</h3>
        <p className="text-sm text-gray-500 mb-4">
          API keys and database settings are configured via environment variables on the server.
          Update them in the <code className="bg-gray-100 px-1 rounded">.env</code> file and restart the container.
        </p>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between py-2 border-b">
            <span className="text-gray-500">Primary AI</span>
            <span className="font-medium">Claudible (OpenAI-compatible)</span>
          </div>
          <div className="flex justify-between py-2 border-b">
            <span className="text-gray-500">Fallback AI</span>
            <span className="font-medium">Anthropic Direct</span>
          </div>
          <div className="flex justify-between py-2 border-b">
            <span className="text-gray-500">Secondary Fallback</span>
            <span className="font-medium">OpenAI</span>
          </div>
          <div className="flex justify-between py-2 border-b">
            <span className="text-gray-500">Strong Model</span>
            <span className="font-medium">claude-opus-4.6 (Part 2 & 3)</span>
          </div>
          <div className="flex justify-between py-2">
            <span className="text-gray-500">Fast Model</span>
            <span className="font-medium">claude-sonnet-4.6 (MCQ)</span>
          </div>
        </div>
      </div>

      {/* About */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="font-semibold mb-3">About</h3>
        <p className="text-sm text-gray-500">
          ExamsGen generates ACCA TX(VNM) exam-standard questions using AI.
          It reads official Vietnamese tax regulations and syllabus documents,
          then produces questions matching the style, difficulty, and format of real ACCA past exam papers.
        </p>
      </div>
    </div>
  )
}

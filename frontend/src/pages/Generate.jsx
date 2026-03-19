import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'

const SAC_THUE_OPTIONS = ['CIT', 'VAT', 'PIT', 'FCT', 'TP', 'ADMIN']
const QUESTION_MAP = {
  Q1: 'CIT', Q2: 'PIT', Q3: 'FCT', Q4: 'VAT', Q5: 'CIT', Q6: 'PIT',
}

export default function Generate() {
  const [searchParams] = useSearchParams()
  const [type, setType] = useState(searchParams.get('type') || '')
  const [sac_thue, setSacThue] = useState(searchParams.get('sac_thue') || 'CIT')
  const [questionNumber, setQuestionNumber] = useState(searchParams.get('question_number') || 'Q1')
  const [count, setCount] = useState(5)
  const [topics, setTopics] = useState('')
  const [examSession, setExamSession] = useState('Jun2026')
  const [industry, setIndustry] = useState('')
  const [difficulty, setDifficulty] = useState('standard')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const t = searchParams.get('type')
    if (t) setType(t)
    const st = searchParams.get('sac_thue')
    if (st) setSacThue(st)
    const qn = searchParams.get('question_number')
    if (qn) {
      setQuestionNumber(qn)
      if (QUESTION_MAP[qn]) setSacThue(QUESTION_MAP[qn])
    }
  }, [searchParams])

  const handleGenerate = async () => {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      let data
      if (type === 'mcq') {
        data = await api.generateMCQ({
          sac_thue,
          count,
          exam_session: examSession,
          topics: topics ? topics.split(',').map((t) => t.trim()) : null,
          difficulty,
        })
      } else if (type === 'scenario') {
        data = await api.generateScenario({
          question_number: questionNumber,
          sac_thue: QUESTION_MAP[questionNumber] || sac_thue,
          marks: 10,
          exam_session: examSession,
          scenario_industry: industry || null,
        })
      } else if (type === 'longform') {
        data = await api.generateLongform({
          question_number: questionNumber,
          sac_thue: QUESTION_MAP[questionNumber] || sac_thue,
          marks: 15,
          exam_session: examSession,
        })
      }
      setResult(data)
    } catch (err) {
      setError(err.message || 'Generation failed')
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async () => {
    if (!result?.id) return
    try {
      const blob = await api.exportWord([result.id])
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `ExamsGen_${result.id}.docx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError('Export failed: ' + err.message)
    }
  }

  return (
    <div className="max-w-4xl">
      <h2 className="text-2xl font-bold mb-6">Generate Questions</h2>

      {/* Step 1: Type Selection */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase mb-3">Step 1: Question Type</h3>
        <div className="grid grid-cols-3 gap-3">
          {[
            { key: 'mcq', title: 'Part 1: MCQ', desc: '2 marks each, multiple choice' },
            { key: 'scenario', title: 'Part 2: Scenario', desc: '10 marks, Q1-Q4' },
            { key: 'longform', title: 'Part 3: Long-form', desc: '15 marks, Q5-Q6' },
          ].map(({ key, title, desc }) => (
            <button
              key={key}
              onClick={() => {
                setType(key)
                if (key === 'scenario') setQuestionNumber('Q1')
                if (key === 'longform') setQuestionNumber('Q5')
              }}
              className={`p-4 rounded-xl border-2 text-left transition-all ${
                type === key ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <p className="font-semibold">{title}</p>
              <p className="text-xs text-gray-500 mt-1">{desc}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Step 2: Configuration */}
      {type && (
        <div className="mb-6 bg-white rounded-xl border p-5">
          <h3 className="text-sm font-semibold text-gray-500 uppercase mb-4">Step 2: Configure</h3>
          <div className="grid grid-cols-2 gap-4">
            {type === 'mcq' && (
              <>
                <div>
                  <label className="block text-sm font-medium mb-1">Tax Type</label>
                  <select value={sac_thue} onChange={(e) => setSacThue(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2">
                    {SAC_THUE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Number of MCQs</label>
                  <input type="number" min={1} max={10} value={count}
                    onChange={(e) => setCount(parseInt(e.target.value) || 1)}
                    className="w-full border rounded-lg px-3 py-2" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Topics (comma-separated, optional)</label>
                  <input value={topics} onChange={(e) => setTopics(e.target.value)}
                    placeholder="e.g. deductible expenses, depreciation"
                    className="w-full border rounded-lg px-3 py-2" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Difficulty</label>
                  <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2">
                    <option value="standard">Standard</option>
                    <option value="hard">Hard</option>
                  </select>
                </div>
              </>
            )}

            {type === 'scenario' && (
              <>
                <div>
                  <label className="block text-sm font-medium mb-1">Question Number</label>
                  <select value={questionNumber} onChange={(e) => {
                    setQuestionNumber(e.target.value)
                    setSacThue(QUESTION_MAP[e.target.value])
                  }} className="w-full border rounded-lg px-3 py-2">
                    <option value="Q1">Q1 — CIT</option>
                    <option value="Q2">Q2 — PIT</option>
                    <option value="Q3">Q3 — FCT</option>
                    <option value="Q4">Q4 — VAT</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Industry (optional)</label>
                  <input value={industry} onChange={(e) => setIndustry(e.target.value)}
                    placeholder="e.g. manufacturing, services"
                    className="w-full border rounded-lg px-3 py-2" />
                </div>
              </>
            )}

            {type === 'longform' && (
              <div>
                <label className="block text-sm font-medium mb-1">Question Number</label>
                <select value={questionNumber} onChange={(e) => {
                  setQuestionNumber(e.target.value)
                  setSacThue(QUESTION_MAP[e.target.value])
                }} className="w-full border rounded-lg px-3 py-2">
                  <option value="Q5">Q5 — CIT (15 marks)</option>
                  <option value="Q6">Q6 — PIT (15 marks)</option>
                </select>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium mb-1">Exam Session</label>
              <input value={examSession} onChange={(e) => setExamSession(e.target.value)}
                className="w-full border rounded-lg px-3 py-2" />
            </div>
          </div>

          <button
            onClick={handleGenerate}
            disabled={loading}
            className="mt-5 bg-brand-500 text-white px-8 py-3 rounded-lg font-medium hover:bg-brand-600 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {loading && (
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            {loading ? 'Generating...' : 'Generate'}
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 mb-6">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="bg-white rounded-xl border p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Generated Question</h3>
            <div className="flex gap-2">
              <button onClick={handleExport}
                className="px-4 py-2 bg-blue-500 text-white text-sm rounded-lg hover:bg-blue-600">
                Export Word
              </button>
              <button onClick={handleGenerate}
                className="px-4 py-2 border text-sm rounded-lg hover:bg-gray-50">
                Regenerate
              </button>
            </div>
          </div>

          {/* Meta */}
          <div className="flex gap-4 text-xs text-gray-500 mb-4">
            <span>Model: {result.model_used}</span>
            <span>Provider: {result.provider_used}</span>
            <span>Tokens: {result.prompt_tokens + result.completion_tokens}</span>
            <span>Time: {(result.duration_ms / 1000).toFixed(1)}s</span>
          </div>

          {/* Rendered HTML */}
          <div
            className="question-html"
            dangerouslySetInnerHTML={{ __html: result.content_html }}
          />
        </div>
      )}
    </div>
  )
}

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
  const [count, setCount] = useState(3)
  const [topics, setTopics] = useState('')
  const [examSession, setExamSession] = useState('Jun2026')
  const [industry, setIndustry] = useState('')
  const [difficulty, setDifficulty] = useState('standard')
  const [modelTier, setModelTier] = useState('fast')
  const [provider, setProvider] = useState('')
  const [syllabusCodes, setSyllabusCodes] = useState('')  // simple text input e.g. "CIT-2d, CIT-2n"
  const [customInstructions, setCustomInstructions] = useState('')
  const [showCustom, setShowCustom] = useState(false)
  const [referenceId, setReferenceId] = useState('')
  const [referenceOptions, setReferenceOptions] = useState([])
  const [samplePreviews, setSamplePreviews] = useState([])

  const [sessions, setSessions] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [chatHistory, setChatHistory] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [currentContent, setCurrentContent] = useState(null)

  // Load sessions
  useEffect(() => {
    api.getSessions().then((data) => {
      setSessions(data)
      const stored = localStorage.getItem('currentSessionId')
      const match = data.find((s) => String(s.id) === stored) || data.find((s) => s.is_default)
      if (match) {
        setSessionId(match.id)
        if (match.exam_date) setExamSession(match.exam_date)
      }
    }).catch(() => {})
  }, [])

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

  useEffect(() => {
    if (type && sac_thue) {
      api.getQuestionsForReference({ type, sac_thue })
        .then(setReferenceOptions)
        .catch(() => setReferenceOptions([]))
    }
  }, [type, sac_thue])

  useEffect(() => {
    if (!sessionId || !type || !sac_thue) return
    const examTypeMap = { mcq: 'MCQ', scenario: 'Scenario', longform: 'Longform' }
    api.getSamplePreviews({ session_id: sessionId, sac_thue, exam_type: examTypeMap[type] || 'MCQ' })
      .then(setSamplePreviews)
      .catch(() => setSamplePreviews([]))
  }, [sessionId, type, sac_thue])

  const parseSyllabusCodes = () => {
    if (!syllabusCodes.trim()) return null
    return syllabusCodes.split(',').map((s) => s.trim()).filter(Boolean)
  }

  const handleGenerate = async () => {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const commonFields = {
        session_id: sessionId || null,
        provider: provider || null,
        syllabus_codes: parseSyllabusCodes(),
        custom_instructions: customInstructions || null,
        reference_question_id: referenceId ? parseInt(referenceId) : null,
      }
      let data
      if (type === 'mcq') {
        data = await api.generateMCQ({
          sac_thue,
          count,
          exam_session: examSession,
          topics: topics ? topics.split(',').map((t) => t.trim()) : null,
          difficulty,
          model_tier: modelTier,
          ...commonFields,
        })
      } else if (type === 'scenario') {
        data = await api.generateScenario({
          question_number: questionNumber,
          sac_thue: QUESTION_MAP[questionNumber] || sac_thue,
          marks: 10,
          exam_session: examSession,
          scenario_industry: industry || null,
          model_tier: modelTier,
          ...commonFields,
        })
      } else if (type === 'longform') {
        data = await api.generateLongform({
          question_number: questionNumber,
          sac_thue: QUESTION_MAP[questionNumber] || sac_thue,
          marks: 15,
          exam_session: examSession,
          model_tier: modelTier,
          ...commonFields,
        })
      }
      setResult(data)
      setCurrentContent(data.content_json)
      setChatHistory([{ role: 'assistant', content: 'Question ready! Ask me to adjust anything — in English or Vietnamese.' }])
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

  const currentSession = sessions.find((s) => s.id === sessionId)

  return (
    <div className="max-w-4xl">
      <h2 className="text-2xl font-bold mb-6">Generate Questions</h2>

      {/* Session selector */}
      <div className="flex items-center gap-3 bg-gray-50 rounded-lg px-4 py-2 mb-5 border">
        <span className="text-sm text-gray-500 shrink-0">Session:</span>
        <select
          value={sessionId || ''}
          onChange={(e) => {
            const id = parseInt(e.target.value)
            setSessionId(id)
            const s = sessions.find((x) => x.id === id)
            if (s?.exam_date) setExamSession(s.exam_date)
          }}
          className="text-sm border-0 bg-transparent flex-1 focus:outline-none"
        >
          <option value="">— Select session —</option>
          {sessions.map((s) => (
            <option key={s.id} value={s.id}>{s.name}{s.is_default ? ' (active)' : ''}</option>
          ))}
        </select>
        {currentSession && (
          <span className="text-xs text-gray-400 shrink-0">
            {currentSession.file_count || 0} files loaded
          </span>
        )}
      </div>

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
              <label className="block text-sm font-medium mb-1">AI Provider + Model</label>
              <select value={`${provider || 'auto'}|${modelTier}`} onChange={(e) => {
                const [p, t] = e.target.value.split('|')
                setProvider(p === 'auto' ? '' : p)
                setModelTier(t)
              }} className="w-full border rounded-lg px-3 py-2">
                <option value="auto|fast">Auto — Sonnet (fast)</option>
                <option value="auto|strong">Auto — Opus (best)</option>
                <option value="claudible|fast">Claudible — Sonnet</option>
                <option value="claudible|strong">Claudible — Opus</option>
                <option value="anthropic|fast">Anthropic — Sonnet</option>
                <option value="anthropic|strong">Anthropic — Opus</option>
                <option value="openai|fast">OpenAI — Fast</option>
                <option value="openai|strong">OpenAI — Strong</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Syllabus Codes (optional)</label>
              <input
                value={syllabusCodes}
                onChange={(e) => setSyllabusCodes(e.target.value)}
                placeholder="e.g. CIT-2d, CIT-2n"
                className="w-full border rounded-lg px-3 py-2"
              />
              <p className="text-xs text-gray-400 mt-1">
                Comma-separated. Question(s) will target these specific syllabus items.
              </p>
            </div>
          </div>

          {/* Custom Instructions */}
          <div className="border-t pt-4 mt-4">
            <button
              type="button"
              onClick={() => setShowCustom(!showCustom)}
              className="flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900"
            >
              <span>{showCustom ? '▼' : '▶'}</span>
              Custom Instructions (optional)
            </button>

            {showCustom && (
              <div className="mt-3 space-y-3">
                {referenceOptions.length > 0 && (
                  <div>
                    <label className="block text-sm font-medium mb-2">Based on question from bank</label>
                    <div className="space-y-2 max-h-48 overflow-y-auto border rounded-lg p-2 bg-gray-50">
                      <div
                        onClick={() => setReferenceId('')}
                        className={`cursor-pointer rounded-lg px-3 py-2 text-sm border transition-all ${
                          referenceId === '' ? 'border-brand-500 bg-brand-50' : 'border-transparent hover:bg-white hover:border-gray-200'
                        }`}
                      >
                        <span className="text-gray-400 italic">— None —</span>
                      </div>
                      {referenceOptions.map((q) => (
                        <div
                          key={q.id}
                          onClick={() => setReferenceId(String(q.id))}
                          className={`cursor-pointer rounded-lg px-3 py-2 text-sm border transition-all ${
                            referenceId === String(q.id)
                              ? 'border-brand-500 bg-brand-50'
                              : 'border-transparent hover:bg-white hover:border-gray-200'
                          }`}
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <span className="bg-blue-100 text-blue-700 text-xs font-semibold px-2 py-0.5 rounded">
                              {q.question_type?.replace('_10', '').replace('_15', '')}
                            </span>
                            <span className="bg-green-100 text-green-700 text-xs font-semibold px-2 py-0.5 rounded">
                              {q.sac_thue}
                            </span>
                            <span className="text-xs text-gray-400 ml-auto">{q.created_at}</span>
                          </div>
                          {q.snippet && (
                            <p className="text-xs text-gray-600 truncate">{q.snippet}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {samplePreviews.length > 0 && (
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Sample Examples in Knowledge Base
                      <span className="text-xs text-gray-400 font-normal ml-2">
                        ({sac_thue} · {type?.toUpperCase()})
                      </span>
                    </label>
                    <div className="space-y-2">
                      {samplePreviews.map((s, i) => (
                        <div key={i} className="border rounded-lg p-3 bg-gray-50 text-xs">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-semibold text-gray-700">{s.name}</span>
                            <span className="bg-orange-100 text-orange-700 font-semibold px-2 py-0.5 rounded">
                              {s.exam_type}
                            </span>
                          </div>
                          {s.preview && (
                            <p className="text-gray-500 leading-relaxed whitespace-pre-wrap font-mono text-[11px] max-h-24 overflow-y-auto">
                              {s.preview}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      These examples are automatically used as style references when generating.
                    </p>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium mb-1">Paste a sample or describe what you want</label>
                  <textarea
                    value={customInstructions}
                    onChange={(e) => setCustomInstructions(e.target.value)}
                    rows={5}
                    className="w-full border rounded-lg px-3 py-2 text-sm resize-y"
                    placeholder="Paste a complete Q&A to replicate its style, or describe in English/Vietnamese..."
                  />
                </div>
              </div>
            )}
          </div>

          <button
            onClick={handleGenerate}
            disabled={loading || !sessionId}
            className="mt-5 bg-brand-500 text-white px-8 py-3 rounded-lg font-medium hover:bg-brand-600 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {loading && (
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            {loading ? 'Generating...' : sessionId ? 'Generate' : 'Select a session first'}
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
              <button onClick={() => { setChatHistory([]); setCurrentContent(null); handleGenerate() }}
                className="px-4 py-2 border text-sm rounded-lg hover:bg-gray-50">
                Regenerate
              </button>
            </div>
          </div>
          <div className="flex gap-4 text-xs text-gray-500 mb-4">
            <span>Model: {result.model_used}</span>
            <span>Provider: {result.provider_used}</span>
            <span>Tokens: {result.prompt_tokens + result.completion_tokens}</span>
            <span>Time: {(result.duration_ms / 1000).toFixed(1)}s</span>
          </div>
          <div className="question-html" dangerouslySetInnerHTML={{ __html: result.content_html }} />
        </div>
      )}

      {/* Refine Chat */}
      {result && (
        <RefineChat
          chatHistory={chatHistory}
          setChatHistory={setChatHistory}
          chatInput={chatInput}
          setChatInput={setChatInput}
          chatLoading={chatLoading}
          setChatLoading={setChatLoading}
          currentContent={currentContent}
          setCurrentContent={setCurrentContent}
          setResult={setResult}
          modelTier={modelTier}
          provider={provider}
          sac_thue={sac_thue}
          type={type}
        />
      )}
    </div>
  )
}

function RefineChat({ chatHistory, setChatHistory, chatInput, setChatInput, chatLoading, setChatLoading, currentContent, setCurrentContent, setResult, modelTier, provider, sac_thue, type }) {
  useEffect(() => {
    const el = document.getElementById('chat-scroll')
    if (el) el.scrollTop = el.scrollHeight
  }, [chatHistory, chatLoading])

  const handleRefine = async () => {
    if (!chatInput.trim() || chatLoading) return
    const userMsg = { role: 'user', content: chatInput }
    setChatHistory((prev) => [...prev, userMsg])
    setChatInput('')
    setChatLoading(true)
    try {
      const data = await api.refineQuestion({
        current_content: currentContent,
        conversation_history: chatHistory,
        user_message: chatInput,
        model_tier: modelTier,
        provider: provider || null,
        sac_thue,
        question_type: type === 'mcq' ? 'MCQ' : type === 'scenario' ? 'SCENARIO_10' : 'LONGFORM_15',
      })
      setResult((prev) => ({ ...prev, content_json: data.content, content_html: data.content_html }))
      setCurrentContent(data.content)
      setChatHistory((prev) => [...prev, { role: 'assistant', content: data.assistant_message }])
    } catch {
      setChatHistory((prev) => [...prev, { role: 'assistant', content: 'Refinement failed. Please try again.' }])
    } finally {
      setChatLoading(false)
    }
  }

  return (
    <div className="mt-6 border rounded-xl overflow-hidden shadow-sm">
      <div className="bg-gray-50 px-4 py-2 border-b flex items-center gap-2">
        <span className="text-sm font-semibold text-gray-700">Refine this question</span>
        <span className="text-xs text-gray-400">English or Vietnamese</span>
      </div>
      <div className="p-4 space-y-3 max-h-72 overflow-y-auto" id="chat-scroll">
        {chatHistory.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] px-3 py-2 rounded-lg text-sm leading-relaxed ${
              msg.role === 'user' ? 'bg-[#028a39] text-white' : 'bg-gray-100 text-gray-700'
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
        {chatLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 text-gray-500 px-3 py-2 rounded-lg text-sm animate-pulse">
              Updating question...
            </div>
          </div>
        )}
      </div>
      <div className="border-t p-3 flex gap-2">
        <input
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleRefine()}
          placeholder="E.g: Make harder, add loss carry-forward..."
          className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#028a39]"
          disabled={chatLoading}
        />
        <button
          onClick={handleRefine}
          disabled={chatLoading || !chatInput.trim()}
          className="px-4 py-2 bg-[#028a39] text-white rounded-lg text-sm font-medium hover:bg-[#027a32] disabled:opacity-40 transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  )
}

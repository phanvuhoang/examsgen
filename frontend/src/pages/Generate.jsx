import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import ReferenceMultiSelect from '../components/ReferenceMultiSelect'

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
  const [showCustom, setShowCustom] = useState(false)
  const [referenceId, setReferenceId] = useState('')
  const [customInstructions, setCustomInstructions] = useState('')
  const [referenceOptions, setReferenceOptions] = useState([])
  // v2: Reference Materials
  const [mcqSubtype, setMcqSubtype] = useState('')
  const [selectedSyllabusCodes, setSelectedSyllabusCodes] = useState([])
  const [syllabusChipLabels, setSyllabusChipLabels] = useState({})
  const [selectedRegCodes, setSelectedRegCodes] = useState([])
  const [regChipLabels, setRegChipLabels] = useState({})
  const [selectedSampleIds, setSelectedSampleIds] = useState([])
  const [sampleChipLabels, setSampleChipLabels] = useState({})
  const [selectedQbIds, setSelectedQbIds] = useState([])
  const [qbChipLabels, setQbChipLabels] = useState({})

  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [chatHistory, setChatHistory] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [currentContent, setCurrentContent] = useState(null)
  const [currentSession, setCurrentSession] = useState(null)

  // Load current session
  useEffect(() => {
    api.getSessions().then((data) => {
      const storedId = localStorage.getItem('currentSessionId')
      const match = data.find((s) => String(s.id) === storedId) || data.find((s) => s.is_default)
      if (match) setCurrentSession(match)
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

  const handleGenerate = async () => {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const kbFields = {
        session_id: currentSession?.id || null,
        provider: provider || null,
        // v2 Reference Materials
        mcq_subtype: mcqSubtype || null,
        syllabus_codes: selectedSyllabusCodes.length ? selectedSyllabusCodes : null,
        reg_codes: selectedRegCodes.length ? selectedRegCodes : null,
        sample_question_ids: selectedSampleIds.length ? selectedSampleIds : null,
        question_bank_ids: selectedQbIds.length ? selectedQbIds : null,
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
          reference_question_id: referenceId ? parseInt(referenceId) : null,
          custom_instructions: customInstructions || null,
          ...kbFields,
        })
      } else if (type === 'scenario') {
        data = await api.generateScenario({
          question_number: questionNumber,
          sac_thue: QUESTION_MAP[questionNumber] || sac_thue,
          marks: 10,
          exam_session: examSession,
          scenario_industry: industry || null,
          model_tier: modelTier,
          reference_question_id: referenceId ? parseInt(referenceId) : null,
          custom_instructions: customInstructions || null,
          ...kbFields,
        })
      } else if (type === 'longform') {
        data = await api.generateLongform({
          question_number: questionNumber,
          sac_thue: QUESTION_MAP[questionNumber] || sac_thue,
          marks: 15,
          exam_session: examSession,
          model_tier: modelTier,
          reference_question_id: referenceId ? parseInt(referenceId) : null,
          custom_instructions: customInstructions || null,
          ...kbFields,
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

  return (
    <div className="max-w-4xl">
      <h2 className="text-2xl font-bold mb-6">Generate Questions</h2>

      {/* Session info bar */}
      {currentSession && (
        <div className="text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2 mb-4 flex gap-4">
          <span>Session: <strong>{currentSession.name}</strong></span>
          <span>Reg cutoff: <strong>{currentSession.regulations_cutoff}</strong></span>
          <span>Fiscal year: <strong>{currentSession.fiscal_year_end}</strong></span>
          <span>Tax year: <strong>{currentSession.tax_year}</strong></span>
        </div>
      )}

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

            {type !== 'mcq' && (
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
            )}
          </div>

          {/* Custom Instructions */}
          <div className="border-t pt-4 mt-4">
            <button
              type="button"
              onClick={() => setShowCustom(!showCustom)}
              className="flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900"
            >
              <span>{showCustom ? '\u25BC' : '\u25B6'}</span>
              Custom Instructions (optional)
            </button>

            {showCustom && (
              <div className="mt-3 space-y-4">
                {/* Section A: Pick from bank */}
                {referenceOptions.length > 0 && (
                  <div>
                    <label className="block text-sm font-medium mb-1">
                      Base on question from bank
                    </label>
                    <select
                      value={referenceId}
                      onChange={(e) => setReferenceId(e.target.value)}
                      className="w-full border rounded-lg px-3 py-2 text-sm"
                    >
                      <option value="">— None —</option>
                      {referenceOptions.map((q) => (
                        <option key={q.id} value={q.id}>{q.label}</option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Section B: Paste or describe */}
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Paste a sample or describe what you want
                  </label>
                  <textarea
                    value={customInstructions}
                    onChange={(e) => setCustomInstructions(e.target.value)}
                    rows={6}
                    className="w-full border rounded-lg px-3 py-2 text-sm resize-y"
                    placeholder={"Paste a complete Q&A to replicate its style...\n\nOR describe in English/Vietnamese:\n'Write a Q1 CIT scenario about a manufacturing company with issues on deductible expenses, depreciation of a leased machine, and a tax loss carry-forward from prior year.'"}
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    Supports English and Vietnamese. Paste a question to replicate, or describe in your own words.
                  </p>
                </div>

                {/* Reference Materials */}
                <div className="border-t pt-4 mt-2">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                    Reference Materials
                  </p>

                  {/* MCQ Subtype */}
                  {type === 'mcq' && (
                    <div className="mb-3">
                      <label className="text-xs font-medium block mb-1">MCQ Format</label>
                      <select value={mcqSubtype} onChange={(e) => setMcqSubtype(e.target.value)}
                        className="border rounded px-3 py-1.5 text-sm w-48">
                        <option value="">Auto (mixed)</option>
                        <option value="MCQ-1">Single correct answer</option>
                        <option value="MCQ-N">Multiple correct answers</option>
                        <option value="MCQ-FIB">Fill in the blank</option>
                      </select>
                    </div>
                  )}

                  <ReferenceMultiSelect
                    label="Syllabus items to focus on"
                    placeholder="Search by code or topic... e.g. B2a, deductible"
                    fetchFn={(q) => api.searchKBSyllabus({ session_id: currentSession?.id, tax_type: sac_thue, q })}
                    displayFn={(item) => `[${item.syllabus_code}] ${(item.detailed_syllabus || item.topic || '').substring(0, 80)}`}
                    selected={selectedSyllabusCodes}
                    onSelect={(item) => {
                      const code = item.syllabus_code
                      if (!selectedSyllabusCodes.includes(code)) {
                        setSelectedSyllabusCodes((p) => [...p, code])
                        setSyllabusChipLabels((p) => ({ ...p, [code]: `[${code}] ${(item.detailed_syllabus || item.topic || '').substring(0, 60)}` }))
                      }
                    }}
                    onRemove={(code) => setSelectedSyllabusCodes((p) => p.filter((c) => c !== code))}
                  />

                  <ReferenceMultiSelect
                    label="Regulation paragraphs to cite"
                    placeholder="Search by RegCode or text... e.g. CIT-ND320, salary"
                    fetchFn={(q) => api.searchParsedRegulations({ session_id: currentSession?.id, tax_type: sac_thue, q })}
                    displayFn={(item) => `[${item.reg_code}] ${(item.paragraph_text || '').substring(0, 80)}`}
                    selected={selectedRegCodes}
                    onSelect={(item) => {
                      const code = item.reg_code
                      if (!selectedRegCodes.includes(code)) {
                        setSelectedRegCodes((p) => [...p, code])
                        setRegChipLabels((p) => ({ ...p, [code]: `[${code}] ${(item.paragraph_text || '').substring(0, 60)}` }))
                      }
                    }}
                    onRemove={(code) => setSelectedRegCodes((p) => p.filter((c) => c !== code))}
                  />

                  <ReferenceMultiSelect
                    label="Style references (past exam samples)"
                    placeholder="Search by title or content..."
                    fetchFn={(q) => api.searchSampleQuestions({ question_type: type.toUpperCase(), tax_type: sac_thue, q })}
                    displayFn={(item) => `[${item.question_type}•${item.tax_type}] ${item.title || item.id}`}
                    selected={selectedSampleIds}
                    onSelect={(item) => {
                      if (!selectedSampleIds.includes(item.id)) {
                        setSelectedSampleIds((p) => [...p, item.id])
                        setSampleChipLabels((p) => ({ ...p, [item.id]: `[${item.question_type}•${item.tax_type}] ${item.title || item.id}` }))
                      }
                    }}
                    onRemove={(id) => setSelectedSampleIds((p) => p.filter((i) => i !== id))}
                  />

                  <ReferenceMultiSelect
                    label="Question bank references"
                    placeholder="Search from generated questions..."
                    fetchFn={(q) => api.searchQuestions({ question_type: type.toUpperCase(), sac_thue, q })}
                    displayFn={(item) => `[${item.question_type}•${item.sac_thue}] ${item.question_number || item.id} (${item.created_at?.substring(0, 10)})`}
                    selected={selectedQbIds}
                    onSelect={(item) => {
                      if (!selectedQbIds.includes(item.id)) {
                        setSelectedQbIds((p) => [...p, item.id])
                        setQbChipLabels((p) => ({ ...p, [item.id]: `[${item.question_type}•${item.sac_thue}] ${item.question_number || item.id}` }))
                      }
                    }}
                    onRemove={(id) => setSelectedQbIds((p) => p.filter((i) => i !== id))}
                  />
                </div>
              </div>
            )}
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
              <button onClick={() => { setChatHistory([]); setCurrentContent(null); handleGenerate() }}
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
              msg.role === 'user'
                ? 'bg-[#028a39] text-white'
                : 'bg-gray-100 text-gray-700'
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

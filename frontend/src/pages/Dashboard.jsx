import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

const QUICK_ACTIONS = [
  { label: 'MCQ — CIT', type: 'mcq', sac_thue: 'CIT' },
  { label: 'MCQ — VAT', type: 'mcq', sac_thue: 'VAT' },
  { label: 'MCQ — PIT', type: 'mcq', sac_thue: 'PIT' },
  { label: 'Q1 — CIT', type: 'scenario', question_number: 'Q1', sac_thue: 'CIT' },
  { label: 'Q2 — PIT', type: 'scenario', question_number: 'Q2', sac_thue: 'PIT' },
  { label: 'Q3 — FCT', type: 'scenario', question_number: 'Q3', sac_thue: 'FCT' },
  { label: 'Q4 — VAT', type: 'scenario', question_number: 'Q4', sac_thue: 'VAT' },
  { label: 'Q5 — CIT', type: 'longform', question_number: 'Q5', sac_thue: 'CIT' },
  { label: 'Q6 — PIT', type: 'longform', question_number: 'Q6', sac_thue: 'PIT' },
]

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState({ total: 0, mcq: 0, scenario: 0, longform: 0 })
  const [recent, setRecent] = useState([])

  useEffect(() => {
    api.getQuestions({ limit: 10 }).then((data) => {
      setRecent(data.questions)
      const mcq = data.questions.filter((q) => q.question_type === 'MCQ').length
      const scenario = data.questions.filter((q) => q.question_type === 'SCENARIO_10').length
      const longform = data.questions.filter((q) => q.question_type === 'LONGFORM_15').length
      setStats({ total: data.total, mcq, scenario, longform })
    }).catch(() => {})
  }, [])

  const handleQuickAction = (action) => {
    const params = new URLSearchParams(action)
    navigate(`/generate?${params}`)
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Total Questions', value: stats.total, color: 'bg-brand-500' },
          { label: 'MCQ (Part 1)', value: stats.mcq, color: 'bg-blue-500' },
          { label: 'Scenario (Part 2)', value: stats.scenario, color: 'bg-purple-500' },
          { label: 'Long-form (Part 3)', value: stats.longform, color: 'bg-orange-500' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl shadow-sm p-5 border">
            <p className="text-gray-500 text-sm">{label}</p>
            <p className="text-3xl font-bold mt-1">{value}</p>
            <div className={`h-1 w-12 ${color} rounded mt-3`} />
          </div>
        ))}
      </div>

      {/* Quick Generate */}
      <h3 className="text-lg font-semibold mb-3">Quick Generate</h3>
      <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 mb-8">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.label}
            onClick={() => handleQuickAction(action)}
            className="bg-white border border-gray-200 hover:border-brand-500 hover:bg-brand-50 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors"
          >
            {action.label}
          </button>
        ))}
      </div>

      {/* Recent */}
      <h3 className="text-lg font-semibold mb-3">Recent Questions</h3>
      {recent.length === 0 ? (
        <p className="text-gray-400 text-sm">No questions generated yet.</p>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border divide-y">
          {recent.map((q) => (
            <div
              key={q.id}
              className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 cursor-pointer"
              onClick={() => navigate(`/bank?highlight=${q.id}`)}
            >
              <div className="flex items-center gap-3">
                <span className={`text-xs font-semibold px-2 py-1 rounded ${
                  q.question_type === 'MCQ' ? 'bg-blue-100 text-blue-700' :
                  q.question_type === 'SCENARIO_10' ? 'bg-purple-100 text-purple-700' :
                  'bg-orange-100 text-orange-700'
                }`}>
                  {q.question_number || q.question_type}
                </span>
                <span className="text-sm font-medium">{q.sac_thue}</span>
                {q.is_starred && <span className="text-yellow-500">&#9733;</span>}
              </div>
              <span className="text-xs text-gray-400">
                {q.created_at ? new Date(q.created_at).toLocaleDateString() : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

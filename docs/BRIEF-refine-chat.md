# BRIEF: Conversational Question Refinement

## Feature Overview

After generating a question, the user can **chat with AI** to refine it — changing difficulty, adding/removing issues, tweaking scenarios, adjusting marks, etc. The AI remembers the current question and the conversation history, so the user can make incremental changes naturally in English or Vietnamese.

---

## User Experience

```
[Generate page — after question appears]

┌─────────────────────────────────────────┐
│  Generated Question Preview             │
│  Q1 CIT — ABC Manufacturing JSC...      │
│  (a) Calculate CIT liability...  [3m]   │
│  (b) Deductible expenses...     [4m]    │
│  (c) Transfer pricing adj...    [3m]    │
│                                         │
│  [Save] [Export] [Regenerate]           │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  ✏️ Refine this question                │
│                                         │
│  AI: Question generated! Want me to     │
│  adjust anything?                       │
│                                         │
│  You: Make it harder, add a tax loss    │
│  carry-forward from prior year          │
│                                         │
│  AI: Updated! Added VND 2.4B loss       │
│  carry-forward issue in part (b)...     │
│                                         │
│  You: Đổi công ty sang ngành sản xuất  │
│  thực phẩm, doanh thu khoảng 50 tỷ     │
│                                         │
│  AI: Updated! Changed to food           │
│  manufacturing company...               │
│                                         │
│  [Type your instruction...]  [Send]     │
└─────────────────────────────────────────┘
```

The question preview updates in real-time as AI refines it. User can save any version.

---

## Backend Implementation

### New endpoint: POST /api/generate/refine

```python
class RefineRequest(BaseModel):
    question_id: Optional[int] = None        # if already saved
    current_content: dict                     # current question JSON (from frontend state)
    conversation_history: List[dict]          # list of {role, content} messages so far
    user_message: str                         # new instruction from user
    model_tier: str = "fast"                 # sonnet is enough for refinement
    sac_thue: str
    question_type: str                        # MCQ | SCENARIO_10 | LONGFORM_15
```

### Handler logic

```python
@router.post("/refine")
def refine_question(req: RefineRequest):
    # Build messages array for AI
    system = """You are a senior ACCA TX(VNM) examiner refining an exam question.
You will receive the current question and the user's refinement request.
Return the COMPLETE updated question in the SAME JSON format as the input.
Do not change what wasn't asked to change.
You can respond in English or Vietnamese depending on the user's language."""

    # Format current question as readable text for the AI
    current_q_text = format_question_as_text(req.current_content)

    # Build conversation
    messages = [
        {
            "role": "user",
            "content": f"Here is the current question:\n\n{current_q_text}\n\nHere is the full JSON:\n{json.dumps(req.current_content, ensure_ascii=False)}"
        },
        {
            "role": "assistant", 
            "content": "I have the question. What would you like me to change?"
        }
    ]

    # Add conversation history
    for msg in req.conversation_history:
        messages.append(msg)

    # Add new user message
    messages.append({
        "role": "user",
        "content": req.user_message + "\n\nReturn the complete updated question JSON."
    })

    result = call_ai(messages=messages, model_tier=req.model_tier, system_prompt=system)
    updated_content = parse_ai_json(result["content"])

    return {
        "content": updated_content,
        "content_html": render_question_html(updated_content),
        "model_used": result["model"],
        "provider_used": result["provider"],
        "assistant_message": extract_assistant_note(result["content"])  # any explanation AI gave
    }
```

### Helper: extract_assistant_note

Sometimes AI will say something like "I've updated part (b) to include..." before the JSON. Extract this as a friendly message to show in the chat.

```python
def extract_assistant_note(raw_content: str) -> str:
    """Extract any text before the JSON block as a chat message."""
    raw = raw_content.strip()
    # Find where JSON starts
    json_start = raw.find('{')
    if json_start > 10:
        return raw[:json_start].strip()
    return "Done! Question updated."
```

---

## Frontend Implementation

### State additions (Generate.jsx)

```javascript
const [chatHistory, setChatHistory] = useState([])
const [chatInput, setChatInput] = useState('')
const [chatLoading, setChatLoading] = useState(false)
const [currentContent, setCurrentContent] = useState(null)  // tracks latest JSON
```

When question is first generated:
```javascript
setCurrentContent(result.content_json)
setChatHistory([{
  role: 'assistant',
  content: 'Question generated! Want me to adjust anything? You can ask in English or Vietnamese.'
}])
```

### Chat send handler

```javascript
const handleRefine = async () => {
  if (!chatInput.trim()) return
  
  const userMsg = { role: 'user', content: chatInput }
  const newHistory = [...chatHistory, userMsg]
  setChatHistory(newHistory)
  setChatInput('')
  setChatLoading(true)
  
  try {
    const data = await api.refineQuestion({
      current_content: currentContent,
      conversation_history: chatHistory.filter(m => m.role !== 'assistant' || chatHistory.indexOf(m) > 0),
      user_message: chatInput,
      model_tier: modelTier,
      sac_thue,
      question_type: type === 'mcq' ? 'MCQ' : type === 'scenario' ? 'SCENARIO_10' : 'LONGFORM_15'
    })
    
    // Update question preview
    setResult(prev => ({ ...prev, content_json: data.content, content_html: data.content_html }))
    setCurrentContent(data.content)
    
    // Add AI reply to chat
    setChatHistory(prev => [...prev, {
      role: 'assistant',
      content: data.assistant_message
    }])
  } catch (err) {
    setChatHistory(prev => [...prev, {
      role: 'assistant',
      content: '❌ Sorry, refinement failed. Please try again.'
    }])
  } finally {
    setChatLoading(false)
  }
}
```

### Chat UI (add below question preview, visible only after generation)

```jsx
{result && (
  <div className="mt-4 border rounded-lg overflow-hidden">
    <div className="bg-gray-50 px-4 py-2 border-b flex items-center gap-2">
      <span className="text-sm font-medium text-gray-700">✏️ Refine this question</span>
      <span className="text-xs text-gray-400">Ask in English or Vietnamese</span>
    </div>
    
    {/* Chat messages */}
    <div className="p-4 space-y-3 max-h-64 overflow-y-auto">
      {chatHistory.map((msg, i) => (
        <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className={`max-w-[80%] px-3 py-2 rounded-lg text-sm ${
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
          <div className="bg-gray-100 text-gray-500 px-3 py-2 rounded-lg text-sm">
            Updating question...
          </div>
        </div>
      )}
    </div>
    
    {/* Input */}
    <div className="border-t p-3 flex gap-2">
      <input
        value={chatInput}
        onChange={(e) => setChatInput(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleRefine()}
        placeholder="E.g. Make harder, add loss carry-forward... or: Thêm vấn đề về chuyển giá"
        className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#028a39]"
        disabled={chatLoading}
      />
      <button
        onClick={handleRefine}
        disabled={chatLoading || !chatInput.trim()}
        className="px-4 py-2 bg-[#028a39] text-white rounded-lg text-sm hover:bg-[#027a32] disabled:opacity-50"
      >
        Send
      </button>
    </div>
  </div>
)}
```

### api.js addition

```javascript
refineQuestion: async (data) => {
  const res = await fetch('/api/generate/refine', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data)
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
```

---

## Notes

- **Model:** Use `fast` (Sonnet) by default for refinement — it's fast enough and saves cost
- **History limit:** Keep last 10 exchanges max to avoid context overflow
- **"Save" button:** When user saves, save the LATEST `currentContent` (not the original generated version)
- **Reset chat:** When user clicks "Regenerate", reset chatHistory and currentContent
- **No backend storage for chat:** History lives in frontend state only — no need to persist chat sessions

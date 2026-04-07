# BRIEF: examsgen — Add OpenRouter + DeepSeek, Remove Claudible Sonnet/Opus

**Repo:** github.com/phanvuhoang/examsgen  
**Date:** 2026-04-07  
**Instruction:** Read this brief carefully and implement exactly. Delete this file after implementing. Push to GitHub.

---

## Overview

Add OpenRouter and DeepSeek providers to examsgen. Remove Claudible Sonnet 4.6 and Opus 4.6 (keep Haiku 4.5 only). No functional changes to generation logic — only config + AI provider + frontend model dropdown.

---

## 1. `backend/config.py` — Add new vars

Add after the existing OpenAI block:

```python
# AI — DeepSeek direct
DEEPSEEK_API_KEY   = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL     = os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner")

# AI — OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL1  = os.getenv("OPENROUTER_MODEL1", "")
OPENROUTER_MODEL2  = os.getenv("OPENROUTER_MODEL2", "")
OPENROUTER_MODEL3  = os.getenv("OPENROUTER_MODEL3", "")
```

Also **remove** these lines (Claudible fast/strong — keep HAIKU only):
```python
CLAUDIBLE_MODEL_FAST   = os.getenv("CLAUDIBLE_MODEL_FAST",   "claude-sonnet-4.6")
CLAUDIBLE_MODEL_STRONG = os.getenv("CLAUDIBLE_MODEL_STRONG", "claude-opus-4.6")
```

---

## 2. `backend/ai_provider.py` — Full rewrite of provider section

### Imports — update config imports:

```python
from backend.config import (
    CLAUDIBLE_BASE_URL, CLAUDIBLE_API_KEY, CLAUDIBLE_MODEL_HAIKU,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL_HAIKU, ANTHROPIC_MODEL_FAST, ANTHROPIC_MODEL_STRONG,
    OPENAI_API_KEY, OPENAI_MODEL_FAST, OPENAI_MODEL_STRONG,
    DEEPSEEK_API_KEY, DEEPSEEK_MODEL,
    OPENROUTER_API_KEY, OPENROUTER_MODEL1, OPENROUTER_MODEL2, OPENROUTER_MODEL3,
)
```

### Update `_get_providers()`:

```python
def _get_providers(model_tier: str, provider: str = None):
    claudible = ("claudible", CLAUDIBLE_BASE_URL, CLAUDIBLE_API_KEY,
                 CLAUDIBLE_MODEL_HAIKU) if CLAUDIBLE_API_KEY else None

    anthropic = ("anthropic", "https://api.anthropic.com/v1", ANTHROPIC_API_KEY,
                 ANTHROPIC_TIERS.get(model_tier, ANTHROPIC_MODEL_FAST)) if ANTHROPIC_API_KEY else None

    openai = ("openai", "https://api.openai.com/v1", OPENAI_API_KEY,
              OPENAI_TIERS.get(model_tier, OPENAI_MODEL_FAST)) if OPENAI_API_KEY else None

    deepseek = ("deepseek", "https://api.deepseek.com/v1", DEEPSEEK_API_KEY,
                DEEPSEEK_MODEL) if DEEPSEEK_API_KEY else None

    # OpenRouter entries — only include if key + model both set
    openrouter_entries = []
    for i, model_id in enumerate([OPENROUTER_MODEL1, OPENROUTER_MODEL2, OPENROUTER_MODEL3], 1):
        if OPENROUTER_API_KEY and model_id:
            openrouter_entries.append(
                (f"openrouter{i}", "https://openrouter.ai/api/v1", OPENROUTER_API_KEY, model_id)
            )

    if provider == "claudible":
        return [claudible] if claudible else []
    if provider == "anthropic":
        return [anthropic] if anthropic else []
    if provider == "openai":
        return [openai] if openai else []
    if provider == "deepseek":
        return [deepseek] if deepseek else []
    if provider and provider.startswith("openrouter"):
        # e.g. "openrouter1", "openrouter2", "openrouter3"
        idx = int(provider.replace("openrouter", "")) - 1
        if 0 <= idx < len(openrouter_entries):
            return [openrouter_entries[idx]]
        return []

    # Default: no provider specified → fallback chain
    return [p for p in [claudible, anthropic] if p]
```

### Also update CLAUDIBLE_TIERS (remove fast/strong):
```python
CLAUDIBLE_TIERS = {
    "haiku":  CLAUDIBLE_MODEL_HAIKU,
    "fast":   CLAUDIBLE_MODEL_HAIKU,   # fallback to haiku
    "strong": CLAUDIBLE_MODEL_HAIKU,   # fallback to haiku
}
```

### OpenRouter / DeepSeek in call_ai() — add handling:

In the `for provider_name, base_url, api_key, model in providers:` loop, add handling for deepseek and openrouter providers. They use standard OpenAI-compatible API (no special message conversion needed — use messages as-is, use `max_tokens` param):

```python
# For deepseek and openrouter: use standard OpenAI format
send_messages = messages
if provider_name == "openai":
    # convert system → developer role
    send_messages = []
    for m in messages:
        if m["role"] == "system":
            send_messages.append({"role": "developer", "content": m["content"]})
        else:
            send_messages.append(m)

tok_param = "max_completion_tokens" if provider_name == "openai" else "max_tokens"
```

(The existing logic already handles this correctly — deepseek/openrouter will use `max_tokens` since they're not "openai" provider_name.)

---

## 3. `frontend/src/pages/Generate.jsx`

### Update model dropdown — replace the current `<select>` options block:

```jsx
<select value={`${provider || 'anthropic'}|${modelTier}`} onChange={(e) => {
  const [prov, tier] = e.target.value.split('|')
  setProvider(prov)
  setModelTier(tier)
}}>
  <optgroup label="Anthropic">
    <option value="anthropic|haiku">Anthropic — Haiku 4.5 ⭐ Default (nhanh/rẻ)</option>
    <option value="anthropic|fast">Anthropic — Sonnet 4.6</option>
    <option value="anthropic|strong">Anthropic — Opus 4.6 (mạnh nhất)</option>
  </optgroup>
  <optgroup label="Claudible (Free)">
    <option value="claudible|haiku">Claudible — Haiku 4.5 (free)</option>
  </optgroup>
  <optgroup label="DeepSeek">
    <option value="deepseek|strong">DeepSeek — R1 Reasoner ⭐ (tư duy sâu)</option>
  </optgroup>
  <optgroup label="OpenAI">
    <option value="openai|fast">OpenAI — GPT-4o Mini</option>
    <option value="openai|strong">OpenAI — GPT-4o</option>
  </optgroup>
  {(openrouterModels.length > 0) && (
    <optgroup label="OpenRouter">
      {openrouterModels.map((m, i) => (
        <option key={i} value={`openrouter${i+1}|strong`}>{m.label}</option>
      ))}
    </optgroup>
  )}
</select>
```

### Add `openrouterModels` state — fetch from backend `/api/config/models`:

Add near top of Generate component:
```jsx
const [openrouterModels, setOpenrouterModels] = useState([])

useEffect(() => {
  fetch('/api/config/models')
    .then(r => r.json())
    .then(d => setOpenrouterModels(d.openrouter_models || []))
    .catch(() => {})
}, [])
```

---

## 4. New backend endpoint: `GET /api/config/models`

Add to `main.py` (or a new `routes/config.py`):

```python
@app.get("/api/config/models")
def get_model_config():
    """Return available OpenRouter models (only those with env var set)."""
    from backend.config import OPENROUTER_API_KEY, OPENROUTER_MODEL1, OPENROUTER_MODEL2, OPENROUTER_MODEL3
    openrouter_models = []
    for i, model_id in enumerate([OPENROUTER_MODEL1, OPENROUTER_MODEL2, OPENROUTER_MODEL3], 1):
        if OPENROUTER_API_KEY and model_id:
            openrouter_models.append({"id": f"openrouter{i}", "model": model_id, "label": model_id.split("/")[-1]})
    return {"openrouter_models": openrouter_models}
```

---

## 5. Summary of env vars anh cần add vào Coolify

Anh chỉ cần add những env vars nào muốn dùng:

| Env var | Giá trị ví dụ | Bắt buộc? |
|---|---|---|
| `DEEPSEEK_API_KEY` | `sk-xxx` | Nếu dùng DeepSeek |
| `OPENROUTER_API_KEY` | `sk-or-xxx` | Nếu dùng OpenRouter |
| `OPENROUTER_MODEL1` | `qwen/qwen3-235b-a22b-2507` | Tùy chọn |
| `OPENROUTER_MODEL2` | `google/gemini-2.5-flash` | Tùy chọn |
| `OPENROUTER_MODEL3` | `google/gemini-3-flash-preview` | Tùy chọn |

Model có sẵn không → không hiện trong dropdown.

---

## Done checklist
- [ ] `backend/config.py` updated
- [ ] `backend/ai_provider.py` updated  
- [ ] `frontend/src/pages/Generate.jsx` updated
- [ ] `/api/config/models` endpoint added
- [ ] This brief file deleted
- [ ] Pushed to GitHub

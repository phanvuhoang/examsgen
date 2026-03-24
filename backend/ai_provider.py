import requests
import time
import json
import logging

from backend.config import (
    CLAUDIBLE_BASE_URL, CLAUDIBLE_API_KEY,
    CLAUDIBLE_MODEL_HAIKU, CLAUDIBLE_MODEL_FAST, CLAUDIBLE_MODEL_STRONG,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL_HAIKU, ANTHROPIC_MODEL_FAST, ANTHROPIC_MODEL_STRONG,
    OPENAI_API_KEY,
    OPENAI_MODEL_GPT5, OPENAI_MODEL_GPT5_MINI, OPENAI_MODEL_GPT5_NANO, OPENAI_MODEL_GPT4O_MINI,
)

logger = logging.getLogger(__name__)

# Map UI tier strings → model names
CLAUDIBLE_TIERS = {
    "haiku":  CLAUDIBLE_MODEL_HAIKU,
    "fast":   CLAUDIBLE_MODEL_FAST,
    "strong": CLAUDIBLE_MODEL_STRONG,
}
ANTHROPIC_TIERS = {
    "haiku":  ANTHROPIC_MODEL_HAIKU,
    "fast":   ANTHROPIC_MODEL_FAST,
    "strong": ANTHROPIC_MODEL_STRONG,
}
# OpenAI: tier string IS the model name for explicit selection
OPENAI_MODELS = {
    "gpt-5":      OPENAI_MODEL_GPT5,
    "gpt-5-mini": OPENAI_MODEL_GPT5_MINI,
    "gpt-5-nano": OPENAI_MODEL_GPT5_NANO,
    "gpt-4o-mini":OPENAI_MODEL_GPT4O_MINI,
}


def _get_providers(model_tier: str, provider: str = None):
    """Return list of (name, base_url, api_key, model) for the requested provider+tier."""
    # OpenAI explicit model (tier = model name like 'gpt-5')
    if provider == "openai" and model_tier in OPENAI_MODELS:
        if OPENAI_API_KEY:
            return [("openai", "https://api.openai.com/v1", OPENAI_API_KEY, OPENAI_MODELS[model_tier])]
        return []

    claudible = ("claudible", CLAUDIBLE_BASE_URL, CLAUDIBLE_API_KEY,
                 CLAUDIBLE_TIERS.get(model_tier, CLAUDIBLE_MODEL_FAST)) if CLAUDIBLE_API_KEY else None
    anthropic = ("anthropic", "https://api.anthropic.com/v1", ANTHROPIC_API_KEY,
                 ANTHROPIC_TIERS.get(model_tier, ANTHROPIC_MODEL_FAST)) if ANTHROPIC_API_KEY else None

    if provider == "claudible":
        return [claudible] if claudible else []
    if provider == "anthropic":
        return [anthropic] if anthropic else []

    # No specific provider — try claudible first, then anthropic
    return [p for p in [claudible, anthropic] if p]


MAX_TOKENS_BY_TIER = {
    "haiku":  6000,
    "fast":   6000,
    "strong": 8000,
    # OpenAI models
    "gpt-5":       8000,
    "gpt-5-mini":  6000,
    "gpt-5-nano":  6000,
    "gpt-4o-mini": 6000,
}


def call_ai(prompt: str = None, model_tier: str = "strong", system_prompt: str = None, messages: list = None, provider: str = None) -> dict:
    """Call AI with fallback chain. Returns dict with content, model, provider, tokens.

    Can be called with either:
    - prompt (str): Single user message
    - messages (list): Full conversation history [{role, content}, ...]
    - provider (str): If specified, use only that provider (no fallback)
    """
    providers = _get_providers(model_tier, provider=provider)
    if not providers:
        raise Exception("No AI providers configured — set at least one API key")

    if messages is None:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
    else:
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

    last_error = None
    for provider_name, base_url, api_key, model in providers:
        for attempt in range(3):
            try:
                logger.info(f"Calling {provider_name} model={model} attempt={attempt + 1}")
                response = requests.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": MAX_TOKENS_BY_TIER.get(model_tier, 3000),
                        "temperature": 0.7,
                    },
                    timeout=300,
                )
                if response.status_code == 200:
                    data = response.json()
                    usage = data.get("usage", {})
                    return {
                        "content": data["choices"][0]["message"]["content"],
                        "model": model,
                        "provider": provider_name,
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                    }
                elif response.status_code in [503, 429]:
                    logger.warning(f"{provider_name} returned {response.status_code}, retrying...")
                    time.sleep(5 * (attempt + 1))
                    continue
                else:
                    logger.error(f"{provider_name} returned {response.status_code}: {response.text[:200]}")
                    last_error = f"{provider_name}: HTTP {response.status_code}"
                    break
            except requests.exceptions.Timeout:
                logger.warning(f"{provider_name} timeout, attempt {attempt + 1}")
                last_error = f"{provider_name}: timeout"
                continue
            except Exception as e:
                logger.error(f"{provider_name} error: {e}")
                last_error = str(e)
                break

    raise Exception(f"All AI providers failed. Last error: {last_error}")


def parse_ai_json(content: str) -> dict:
    """Parse JSON from AI response, handling markdown code blocks and truncation."""
    content = content.strip()

    # Strip markdown code fences
    if content.startswith("```"):
        lines = content.split("\n")
        lines = lines[1:]  # remove opening ```json
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    content = content.strip()

    # Try direct parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object boundaries
    start = content.find('{')
    if start == -1:
        raise ValueError("No JSON object found in AI response")

    # Try progressively shorter substrings to handle truncation
    text = content[start:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # AI truncated mid-JSON — try to close it gracefully
    # Find last complete question entry and close the JSON
    # Try closing with common endings
    for suffix in [']}', ']}]}', '"}]}]}', '"]}]}', '}]}]}']:
        try:
            return json.loads(text + suffix)
        except:
            pass

    # Last resort: find last valid JSON subset
    for i in range(len(text), max(len(text)//2, 100), -1):
        try:
            candidate = text[:i]
            # Try to close open brackets
            open_braces = candidate.count('{') - candidate.count('}')
            open_brackets = candidate.count('[') - candidate.count(']')
            closed = candidate + (']' * open_brackets) + ('}' * open_braces)
            return json.loads(closed)
        except:
            continue

    raise ValueError(f"Cannot parse AI response as JSON. First 200 chars: {content[:200]}")


import re


def parse_ai_json_list(content: str) -> list:
    """Parse JSON array from AI response, handling markdown code blocks and truncation."""
    content = content.strip()

    # Strip markdown code fences
    if content.startswith("```"):
        lines = content.split("\n")
        lines = lines[1:]  # remove opening ```json
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    content = content.strip()

    # Try direct parse first
    try:
        result = json.loads(content)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Try to find JSON array boundaries
    start = content.find('[')
    if start == -1:
        raise ValueError("No JSON array found in AI response")

    text = content[start:]
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Try closing with common endings
    for suffix in [']', '}]', '"}]', '"}}]']:
        try:
            result = json.loads(text + suffix)
            if isinstance(result, list):
                return result
        except Exception:
            pass

    # Last resort: find last valid JSON subset
    for i in range(len(text), max(len(text) // 2, 100), -1):
        try:
            candidate = text[:i]
            open_braces = candidate.count('{') - candidate.count('}')
            open_brackets = candidate.count('[') - candidate.count(']')
            closed = candidate + ('}' * open_braces) + (']' * open_brackets)
            result = json.loads(closed)
            if isinstance(result, list):
                return result
        except Exception:
            continue

    raise ValueError(f"Cannot parse AI response as JSON array. First 200 chars: {content[:200]}")

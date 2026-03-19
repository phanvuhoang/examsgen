import requests
import time
import json
import logging

from backend.config import (
    CLAUDIBLE_BASE_URL, CLAUDIBLE_API_KEY,
    CLAUDIBLE_MODEL_STRONG, CLAUDIBLE_MODEL_FAST,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL_STRONG, ANTHROPIC_MODEL_FAST,
    OPENAI_API_KEY, OPENAI_MODEL,
)

logger = logging.getLogger(__name__)


def _get_providers(model_tier: str):
    """Return ordered list of (name, base_url, api_key, model) tuples."""
    providers = []
    if CLAUDIBLE_API_KEY:
        providers.append((
            "claudible",
            CLAUDIBLE_BASE_URL,
            CLAUDIBLE_API_KEY,
            CLAUDIBLE_MODEL_STRONG if model_tier == "strong" else CLAUDIBLE_MODEL_FAST,
        ))
    if ANTHROPIC_API_KEY:
        providers.append((
            "anthropic",
            "https://api.anthropic.com/v1",
            ANTHROPIC_API_KEY,
            ANTHROPIC_MODEL_STRONG if model_tier == "strong" else ANTHROPIC_MODEL_FAST,
        ))
    if OPENAI_API_KEY:
        providers.append((
            "openai",
            "https://api.openai.com/v1",
            OPENAI_API_KEY,
            OPENAI_MODEL,
        ))
    return providers


def call_ai(prompt: str, model_tier: str = "strong", system_prompt: str = None) -> dict:
    """Call AI with fallback chain. Returns dict with content, model, provider, tokens."""
    providers = _get_providers(model_tier)
    if not providers:
        raise Exception("No AI providers configured — set at least one API key")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

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
                        "max_tokens": 8000,
                        "temperature": 0.7,
                    },
                    timeout=120,
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

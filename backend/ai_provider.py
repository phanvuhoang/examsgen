import requests
import time
import json
import logging

from backend.config import (
    CLAUDIBLE_BASE_URL, CLAUDIBLE_API_KEY,
    CLAUDIBLE_MODEL_STRONG, CLAUDIBLE_MODEL_FAST,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL_STRONG, ANTHROPIC_MODEL_FAST,
    OPENAI_API_KEY, OPENAI_MODEL, OPENAI_FAST_MODEL, OPENAI_STRONG_MODEL,
)

logger = logging.getLogger(__name__)


def _get_providers(model_tier: str, provider: str = None):
    """Return ordered list of (name, base_url, api_key, model) tuples.
    If provider is specified, return only that provider (no fallback chain).
    """
    all_providers = []
    if CLAUDIBLE_API_KEY:
        all_providers.append((
            "claudible",
            CLAUDIBLE_BASE_URL,
            CLAUDIBLE_API_KEY,
            CLAUDIBLE_MODEL_STRONG if model_tier == "strong" else CLAUDIBLE_MODEL_FAST,
        ))
    if ANTHROPIC_API_KEY:
        all_providers.append((
            "anthropic",
            "https://api.anthropic.com/v1",
            ANTHROPIC_API_KEY,
            ANTHROPIC_MODEL_STRONG if model_tier == "strong" else ANTHROPIC_MODEL_FAST,
        ))
    if OPENAI_API_KEY:
        all_providers.append((
            "openai",
            "https://api.openai.com/v1",
            OPENAI_API_KEY,
            OPENAI_STRONG_MODEL if model_tier == "strong" else OPENAI_FAST_MODEL,
        ))

    if provider:
        filtered = [p for p in all_providers if p[0] == provider]
        return filtered if filtered else all_providers

    return all_providers


MAX_TOKENS_BY_TIER = {
    "fast": 6000,    # MCQ — needs room for full working steps (3 MCQ × ~1800 tokens)
    "strong": 8000,  # Scenario/Longform — longer output
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

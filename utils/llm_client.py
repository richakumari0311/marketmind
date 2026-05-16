import os
import re
import time
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "local")
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds between retries

if PROVIDER == "anthropic":
    import anthropic
    _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
else:
    from openai import OpenAI
    _client = OpenAI(
        base_url=os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1"),
        api_key="ollama",
        timeout=120.0,  # 2 min max per call
    )

MODEL = (
    os.getenv("LOCAL_MODEL", "llama3.2")
    if PROVIDER == "local"
    else "claude-sonnet-4-20250514"
)


def chat(messages: list[dict], system: str = None) -> str:
    """
    Unified chat call with automatic retry on failure.
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if PROVIDER == "anthropic":
                response = _client.messages.create(
                    model=MODEL,
                    max_tokens=1024,
                    system=system or "You are a helpful marketing assistant.",
                    messages=messages,
                )
                return response.content[0].text

            else:
                all_messages = []
                if system:
                    all_messages.append({"role": "system", "content": system})
                all_messages.extend(messages)

                response = _client.chat.completions.create(
                    model=MODEL,
                    messages=all_messages,
                )
                return response.choices[0].message.content

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                print(f"  [RETRY {attempt}/{MAX_RETRIES}] chat() failed: {e}")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  [FAIL] chat() failed after {MAX_RETRIES} attempts: {e}")

    raise RuntimeError(f"chat() failed after {MAX_RETRIES} retries: {last_error}")


def strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        text = match.group(1)
    return text


def clean_json_response(text: str) -> str:
    text = strip_fences(text)
    result = []
    in_string = False
    escape_next = False

    for char in text:
        if escape_next:
            result.append(char)
            escape_next = False
            continue
        if char == "\\" and in_string:
            result.append(char)
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            result.append(char)
            continue
        if in_string:
            if char == "\n":
                result.append("\\n")
            elif char == "\r":
                result.append("\\r")
            elif char == "\t":
                result.append("\\t")
            else:
                result.append(char)
        else:
            result.append(char)

    return "".join(result)


def parse_json_robust(text: str, context: str = "") -> dict:
    """
    Three-stage JSON parser:
      1. Clean + json.loads
      2. json_repair
      3. Model retry
    """
    import json
    from json_repair import repair_json

    # Stage 1 -- clean and parse
    cleaned = clean_json_response(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Stage 2 -- json_repair
    try:
        repaired = repair_json(cleaned, return_objects=True)
        if isinstance(repaired, dict) and repaired:
            print(f"  [INFO] {context} JSON repaired automatically")
            return repaired
    except Exception:
        pass

    # Stage 3 -- ask model to fix it
    print(f"  [WARN] {context} JSON broken, asking model to fix...")
    fix_prompt = f"""The following text should be valid JSON but has syntax errors.
Return ONLY the corrected valid JSON object. No explanation, no markdown.

Broken JSON:
{text[:2000]}
"""
    try:
        retry_response = chat(
            messages=[{"role": "user", "content": fix_prompt}],
            system="You are a JSON repair tool. Return only valid JSON, nothing else."
        )
        cleaned_retry = clean_json_response(retry_response)

        try:
            result = json.loads(cleaned_retry)
            print(f"  [OK] {context} fixed by model retry")
            return result
        except json.JSONDecodeError:
            pass

        repaired_retry = repair_json(cleaned_retry, return_objects=True)
        if isinstance(repaired_retry, dict) and repaired_retry:
            print(f"  [OK] {context} fixed by repair+retry")
            return repaired_retry

    except Exception as e:
        print(f"  [WARN] {context} model retry also failed: {e}")

    raise ValueError(
        f"{context} JSON could not be parsed after all attempts.\nRaw: {text[:300]}"
    )


def safe_decode(text: str) -> str:
    """
    Safely handle unicode escape sequences in content strings.
    Replaces the fragile .encode().decode('unicode_escape') pattern
    which crashes on non-latin characters and certain byte sequences.
    """
    if not text:
        return ""
    # Only decode \uXXXX sequences, leave everything else untouched
    def replace_unicode(match):
        try:
            return chr(int(match.group(1), 16))
        except (ValueError, OverflowError):
            return match.group(0)
    return re.sub(r"\\u([0-9a-fA-F]{4})", replace_unicode, text)


def extract_text_from_raw(raw: str) -> str:
    """
    Last resort: pull readable strings out of broken JSON.
    """
    skip_keys = {
        "type", "title", "channel", "cta", "word_count",
        "meta", "content", "blog", "email", "linkedin"
    }
    tokens = re.findall(r'"((?:[^"\\]|\\.)*)"', raw)
    paragraphs = []
    for token in tokens:
        token = token.strip()
        if token.lower() in skip_keys:
            continue
        if len(token) < 20:
            continue
        if token.replace("-", "").replace("_", "").isalpha() and " " not in token:
            continue
        paragraphs.append(token)
    return "\n\n".join(paragraphs)
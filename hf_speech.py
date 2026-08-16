"""
Hugging Face automatic speech recognition (Whisper).

Uses huggingface_hub.InferenceClient with provider fallbacks. Browser recordings
are usually WebM/Opus or MP4/AAC depending on the device.
"""

from __future__ import annotations

import os
import time
from typing import Any, List, Optional, Tuple

HF_SPEECH_MODEL = os.environ.get("HF_SPEECH_MODEL", "openai/whisper-large-v3-turbo").strip()

# Providers that commonly host Whisper for InferenceClient.
_ASR_PROVIDERS: List[Optional[str]] = [
    os.environ.get("HF_SPEECH_PROVIDER", "").strip() or None,
    "fal-ai",
    "hf-inference",
    "auto",
    None,
]
# De-dupe while preserving order.
_seen_prov = set()
ASR_PROVIDER_CHAIN: List[Optional[str]] = []
for p in _ASR_PROVIDERS:
    key = p or "__default__"
    if key in _seen_prov:
        continue
    _seen_prov.add(key)
    ASR_PROVIDER_CHAIN.append(p)


def get_hf_token() -> str:
    """Retrieve HF Token from environment or system_settings database table."""
    token = (
        os.environ.get("HF_API_TOKEN_FOR_VOICE", "").strip()
        or os.environ.get("HF_API_TOKEN", "").strip()
        or os.environ.get("HF_TOKEN", "").strip()
    )
    if token:
        return token
    try:
        import db
        val = db.get_system_setting("hf_api_token", "")
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    except Exception:
        pass
    return ""


def is_configured() -> bool:
    """Return True if HF API token is configured."""
    return bool(get_hf_token())


def _extract_text(out: Any) -> str:
    if out is None:
        return ""
    text = getattr(out, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    if isinstance(out, dict):
        t = out.get("text")
        if isinstance(t, str) and t.strip():
            return t.strip()
    chunks = getattr(out, "chunks", None)
    if chunks:
        parts: List[str] = []
        for ch in chunks:
            if isinstance(ch, dict):
                piece = ch.get("text") or ""
            else:
                piece = getattr(ch, "text", "") or ""
            if piece:
                parts.append(str(piece))
        joined = " ".join(parts).strip()
        if joined:
            return joined
    return ""


def transcribe_upload_bytes(data: bytes, content_type: str, language: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (transcript_text, error_message). On success error_message is None.
    """
    if not data:
        return None, "Empty audio recording."
    if len(data) < 200:
        return None, "Recording was too short. Please speak for at least 2–3 seconds."

    token = get_hf_token()
    if not token:
        return (
            None,
            "Hugging Face API token is not configured yet. Set HF_API_TOKEN in Railway or Admin Settings.",
        )

    try:
        from huggingface_hub import InferenceClient
        from huggingface_hub.errors import HfHubHTTPError
    except ImportError:
        return (
            None,
            "Server is missing the huggingface_hub package; redeploy with updated requirements.txt.",
        )

    _ = content_type
    model_id = HF_SPEECH_MODEL or "openai/whisper-large-v3-turbo"
    last_err: Optional[str] = None

    for provider in ASR_PROVIDER_CHAIN:
        for attempt in range(2):
            try:
                kwargs = {"token": token}
                if provider:
                    kwargs["provider"] = provider
                client = InferenceClient(**kwargs)
                out = client.automatic_speech_recognition(audio=data, model=model_id)
                text = _extract_text(out)
                if text:
                    return text, None
                last_err = "Transcription returned no text."
                break
            except HfHubHTTPError as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None) or 0
                detail = str(exc).strip() or getattr(exc, "message", "") or "HTTP error"
                if status == 503 or "503" in detail or "loading" in detail.lower():
                    time.sleep(min(4.0, 1.5 * (attempt + 1)))
                    last_err = "Transcription service is warming up; try again in a moment."
                    continue
                last_err = f"Transcription failed ({provider or 'default'}): {detail}"[:650]
                break
            except Exception as exc:
                last_err = f"Transcription error ({provider or 'default'}): {exc}"[:650]
                break

    return None, last_err or "Transcription service temporarily unavailable."



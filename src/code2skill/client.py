"""Small OpenAI-compatible client plus an offline scripted client."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Mapping, Optional

from .config import ModelConfig
from .security import validate_model_url

Messages = List[Dict[str, str]]


def parse_json_object(content: str) -> Dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline >= 0:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Model did not return a JSON object")
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Model response must be a JSON object")
    return value


class OpenAICompatibleClient:
    def __init__(self, config: ModelConfig) -> None:
        resolved_base_url = config.resolved_base_url()
        validate_model_url(resolved_base_url, config.allow_public_url)
        self.config = config
        base = resolved_base_url.rstrip("/")
        self.endpoint = (
            base if base.endswith("/chat/completions") else base + "/chat/completions"
        )

    def _request(self, messages: Messages, max_tokens: int, json_mode: bool) -> str:
        body: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.config.api_key():
            headers["Authorization"] = "Bearer " + self.config.api_key()
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        last_error: Optional[BaseException] = None
        for attempt in range(self.config.max_retries + 1):
            try:
                with urllib.request.urlopen(
                    request, timeout=self.config.timeout_seconds
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                return str(payload["choices"][0]["message"]["content"])
            except (
                urllib.error.URLError,
                TimeoutError,
                KeyError,
                IndexError,
                json.JSONDecodeError,
            ) as exc:
                last_error = exc
                if attempt < self.config.max_retries:
                    time.sleep(min(4.0, 0.5 * (2**attempt)))
        raise RuntimeError(f"Model request failed after retries: {last_error}")

    def complete_json(
        self, stage: str, data_id: str, messages: Messages
    ) -> Dict[str, Any]:
        del stage, data_id
        return parse_json_object(
            self._request(messages, self.config.max_json_tokens, True)
        )

    def complete_text(self, stage: str, data_id: str, messages: Messages) -> str:
        del stage, data_id
        return self._request(messages, self.config.max_code_tokens, False)


class ScriptedClient:
    """Deterministic test/demo client; responders are keyed by pipeline stage."""

    def __init__(self, responders: Mapping[str, Any]) -> None:
        self.responders = dict(responders)
        self.calls: List[Dict[str, Any]] = []

    def _response(self, stage: str, data_id: str, messages: Messages) -> Any:
        self.calls.append({"stage": stage, "data_id": data_id, "messages": messages})
        if stage not in self.responders:
            raise KeyError(f"No scripted response for {stage}")
        responder = self.responders[stage]
        return responder(stage, data_id, messages) if callable(responder) else responder

    def complete_json(
        self, stage: str, data_id: str, messages: Messages
    ) -> Dict[str, Any]:
        response = self._response(stage, data_id, messages)
        if not isinstance(response, dict):
            raise TypeError(f"Scripted {stage} response must be a dict")
        return dict(response)

    def complete_text(self, stage: str, data_id: str, messages: Messages) -> str:
        return str(self._response(stage, data_id, messages))

"""Minimal OpenAI-compatible Chat Completions transport; keys never enter records."""
from __future__ import annotations

import base64
import io
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def content(text: str, images: list[Path], *, vision: bool) -> list[dict]:
    blocks = [{"type": "text", "text": text}]
    if vision:
        from PIL import Image
        for path in images:
            with Image.open(path) as image:
                image.thumbnail((2000, 2000))
                buf = io.BytesIO()
                image.convert("RGB").save(buf, format="PNG")
            data = base64.b64encode(buf.getvalue()).decode()
            blocks.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}})
    return blocks


class ChatProvider:
    def __init__(self, *, model: str, base_url: str, api_key_env: str,
                 timeout: int, max_tokens: int, temperature: float):
        self.model, self.base_url = model, base_url.rstrip("/")
        self.key = os.environ.get(api_key_env)
        if not self.key:
            raise ValueError(f"Missing environment variable {api_key_env}")
        self.timeout, self.max_tokens, self.temperature = timeout, max_tokens, temperature

    def __call__(self, messages: list[dict]) -> dict:
        body = {"model": self.model, "messages": messages, "max_tokens": self.max_tokens,
                "temperature": self.temperature, "stream": False}
        request = urllib.request.Request(self.base_url + "/chat/completions",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json",
                                                     "Authorization": "Bearer " + self.key})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            # Do not persist arbitrary provider error bodies, which may echo credentials.
            raise RuntimeError(f"Provider HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError("Provider connection failed or timed out") from None
        choice = payload["choices"][0]
        message = choice["message"]
        if not isinstance(message.get("content"), str):
            raise RuntimeError("Provider returned no text content")
        usage = payload.get("usage", {})
        # Without measured completion tokens the output budget cannot be enforced.
        if not isinstance(usage.get("completion_tokens"), int):
            raise RuntimeError("Provider did not report completion_tokens")
        return {"message": {k: v for k, v in message.items()
                            if k in ("role", "content", "reasoning_content")},
                "usage": usage, "model": payload.get("model"),
                "finish_reason": choice.get("finish_reason")}

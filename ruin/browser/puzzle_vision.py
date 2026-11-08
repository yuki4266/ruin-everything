"""Read a cropped visual challenge with a local Ollama vision model."""

import base64
import json
import os
from http.client import HTTPConnection


def visual_answer(png, instruction, schema):
    model = os.environ.get("RUIN_VISION_MODEL", "qwen3-vl:2b-instruct")
    if "cloud" in model.lower():
        raise ValueError("Select a local Ollama vision model for visual challenges.")
    connection = HTTPConnection("127.0.0.1", 11434, timeout=45)
    try:
        payload = {
            "model": model,
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0, "num_predict": 256, "num_ctx": 4096},
            "messages": [
                {"role": "user", "content": instruction, "images": [base64.b64encode(png).decode("ascii")]}
            ],
        }
        connection.request("POST", "/api/chat", json.dumps(payload), {"Content-Type": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"Local vision model {model} unavailable (HTTP {response.status}).")
        return json.loads(json.loads(response.read(65536))["message"]["content"])
    finally:
        connection.close()

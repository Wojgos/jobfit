"""Prompts carry their input as a JSON block after a marker, so every provider gets the
same structured data and the offline fake can read it back without parsing prose."""

import json
from typing import Any

DATA_MARKER = "\nDATA:\n"


def build_prompt(instruction: str, data: dict[str, Any]) -> str:
    return instruction.strip() + DATA_MARKER + json.dumps(data, ensure_ascii=False, indent=2)


def read_data(prompt: str) -> dict[str, Any]:
    _, _, payload = prompt.partition(DATA_MARKER)
    if not payload:
        return {}
    data: dict[str, Any] = json.loads(payload)
    return data

"""Helpers for structured LLM output — JSON parsing from LLM text responses."""

import json
import re
from typing import TypeVar, Type
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def _extract_json(text: str) -> str:
    """Extract the outermost JSON array or object from text.

    Handles:
    - ```json ... ``` blocks
    - leading/trailing text
    - nested brackets
    """
    # Try markdown code blocks first
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1).strip()

    # Find outermost bracket: pick whichever appears first in the text
    pos_obj = text.find("{")
    pos_arr = text.find("[")
    if pos_obj < 0 and pos_arr < 0:
        return text

    # Determine which comes first
    if pos_arr >= 0 and (pos_obj < 0 or pos_arr < pos_obj):
        bracket, close = "[", "]"
    else:
        bracket, close = "{", "}"

    start = text.find(bracket)
    depth = 0
    for i in range(start, len(text)):
        if text[i] == bracket:
            depth += 1
        elif text[i] == close:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text


def parse_json(text: str, model: Type[T]) -> T | list[T]:
    """Extract and parse JSON from LLM text response into Pydantic model(s).

    On failure returns default model() for objects, [] for arrays (heuristic).
    """
    import logging
    log = logging.getLogger("json_output")

    if not text or not text.strip():
        return model()
    try:
        cleaned = _extract_json(text)
        if not cleaned or not cleaned.strip():
            return model()
        data = json.loads(cleaned)
        if isinstance(data, list):
            parsed = []
            for item in data:
                try:
                    parsed.append(model(**item))
                except (TypeError, ValueError):
                    continue
            if not parsed:
                # Last resort: if JSON parsed but Pydantic rejected all items,
                # try to salvage by passing items as dicts directly
                log.warning("parse_json: %d items parsed from JSON but none validated as %s",
                            len(data), model.__name__)
                for item in data:
                    if isinstance(item, dict) and item.get("name") and item.get("days"):
                        # Force-create a valid object
                        try:
                            parsed.append(model(**{k: item.get(k, "" if isinstance(v, str) else []) for k, v in model.model_fields.items()}))
                        except:
                            pass
                if not parsed:
                    return [model()]
            return parsed
        return model(**data)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        log.warning("parse_json failed: %s, text[:100]=%s", e, repr(text[:100]))
        return model()


def json_prompt(instructions: str, schema: str) -> str:
    """Append JSON output instructions to a prompt."""
    return instructions + f"""

IMPORTANT: Respond with valid JSON only. No markdown, no explanation, no extra text.
Schema:
{schema}

Output only the JSON."""


def json_schema_of(model: Type[BaseModel]) -> str:
    """Generate a human-readable schema from a Pydantic model."""
    schema = model.model_json_schema()
    props = schema.get("properties", {})
    lines = ["JSON object with fields:"]
    for name, prop in props.items():
        typ = prop.get("type", "string")
        desc = prop.get("description", "")
        lines.append(f"  {name} ({typ}): {desc}")
    return "\n".join(lines)


def list_schema_of(model: Type[BaseModel]) -> str:
    """Schema for a list of models."""
    return f"Array of JSON objects. Each object:\n{json_schema_of(model)}"

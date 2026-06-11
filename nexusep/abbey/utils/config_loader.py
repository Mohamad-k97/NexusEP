"""
ABBEY config loader.

Loads JSONC config files:
- strips // and /* */ comments safely
- parses JSON
- validates required top-level sections
"""

import json
from pathlib import Path
from typing import Any, Union


REQUIRED_TOP_LEVEL_SECTIONS = [
    "hunger",
    "fatigue",
    "sleep_pressure",
    "sickness",
    "dirty_clothes",
    "action_friction",
    "perception",
    "circadian",
    "actions",
    "idle_movement_profiles",
]


def strip_jsonc_comments(text: str) -> str:
    """
    Strip // and /* */ comments from JSONC text without removing content
    inside quoted strings.
    """

    result = []
    i = 0
    in_string = False
    escape = False

    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""

        if in_string:
            result.append(char)

            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False

            i += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            i += 1
            continue

        # Line comment
        if char == "/" and next_char == "/":
            i += 2
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue

        # Block comment
        if char == "/" and next_char == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue

        result.append(char)
        i += 1

    return "".join(result)


def validate_abbey_config(config: dict[str, Any]) -> None:
    """
    Validate required ABBEY config structure.
    """

    missing = [
        section
        for section in REQUIRED_TOP_LEVEL_SECTIONS
        if section not in config
    ]

    if missing:
        raise KeyError(
            "Missing required ABBEY config sections: "
            + ", ".join(missing)
        )

    if "_meta" not in config["actions"]:
        raise KeyError("Missing actions['_meta'] section in ABBEY config.")

    action_names = [
        name
        for name in config["actions"]
        if not name.startswith("_")
    ]

    if not action_names:
        raise ValueError("ABBEY config must define at least one action.")

    required_action_fields = [
        "category",
        "execution_type",
        "duration_minutes",
        "power_w",
        "activity_intensity",
        "effort",
        "requires_home",
        "requires_awake",
        "blocks_actor",
        "background_process",
        "can_continue_without_actor",
        "can_be_interrupted",
        "system_effects",
        "person_effects",
    ]

    for action_name in action_names:
        action_cfg = config["actions"][action_name]

        missing_fields = [
            field
            for field in required_action_fields
            if field not in action_cfg
        ]

        if missing_fields:
            raise KeyError(
                f"Action '{action_name}' is missing fields: "
                + ", ".join(missing_fields)
            )


def load_jsonc(path: Union[str, Path]) -> dict[str, Any]:
    """
    Load ABBEY JSONC config file.
    """

    path = Path(path)
    import os
    if not path.exists():
        raise FileNotFoundError(f"ABBEY config file not found: {path}")

    text = path.read_text(encoding="utf-8")
    clean_text = strip_jsonc_comments(text)

    try:
        config = json.loads(clean_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSONC after comment stripping: {path}\n"
            f"{exc}"
        ) from exc

    validate_abbey_config(config)

    return config
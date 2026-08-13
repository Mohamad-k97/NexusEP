"""
ABBEY config loader.

Loads JSONC config files:
- strips // and /* */ comments safely
- parses JSON
- validates required top-level sections
"""

from pathlib import Path
from typing import Any, Union

from nexusep.jsonc import loads_strict_json, strip_jsonc


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

ALLOWED_TOP_LEVEL_SECTIONS = {
    "_meta",
    "action_friction",
    "actions",
    "circadian",
    "decision",
    "dirty_clothes",
    "external_schedules",
    "fatigue",
    "household_care",
    "household_cooking",
    "household_dirty_clothes",
    "household_inspection",
    "hunger",
    "idle_movement_profiles",
    "perception",
    "sickness",
    "simulation_calendar",
    "sleep_pressure",
    "space_exit_rules",
}

ALLOWED_ACTION_FIELDS = {
    "action_cooldowns_on_start",
    "activity_intensity",
    "background_process",
    "blocks_actor",
    "can_be_interrupted",
    "can_continue_without_actor",
    "can_fill_remaining_time",
    "can_repeat",
    "category",
    "duration_minutes",
    "effort",
    "execution_type",
    "person_effects",
    "post_action_zone_role",
    "power_w",
    "requires_awake",
    "requires_home",
    "system_effects",
    "target_zone_role",
}


def strip_jsonc_comments(text: str) -> str:
    """
    Strip // and /* */ comments from JSONC text without removing content
    inside quoted strings.
    """

    return strip_jsonc(text, trailing_commas=False)


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

    unknown_sections = sorted(set(config) - ALLOWED_TOP_LEVEL_SECTIONS)
    if unknown_sections:
        raise KeyError(
            "Unknown ABBEY config sections: " + ", ".join(unknown_sections)
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

        if not isinstance(action_cfg, dict):
            raise TypeError(f"Action '{action_name}' must be an object.")

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

        unknown_fields = sorted(set(action_cfg) - ALLOWED_ACTION_FIELDS)
        if unknown_fields:
            raise KeyError(
                f"Action '{action_name}' has unknown fields: "
                + ", ".join(unknown_fields)
            )


def load_jsonc(path: Union[str, Path]) -> dict[str, Any]:
    """
    Load ABBEY JSONC config file.
    """

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"ABBEY config file not found: {path}")

    text = path.read_text(encoding="utf-8")
    try:
        config = loads_strict_json(text, source=path, jsonc=True)
    except ValueError as exc:
        raise ValueError(
            f"Invalid JSONC configuration: {path}\n"
            f"{exc}"
        ) from exc

    if not isinstance(config, dict):
        raise TypeError(f"ABBEY config root must be an object: {path}")

    validate_abbey_config(config)

    return config

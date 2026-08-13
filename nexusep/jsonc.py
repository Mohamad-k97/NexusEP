"""Strict, source-aware JSON and JSONC parsing utilities."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


class DuplicateJSONKeyError(ValueError):
    """A JSON object declared the same key more than once."""

    def __init__(self, source: str | Path, path: tuple[str | int, ...]) -> None:
        self.source = str(source)
        self.path = path
        super().__init__(
            f"Duplicate JSON key at {format_json_path(path)} in {self.source}"
        )

    @property
    def json_pointer(self) -> str:
        if not self.path:
            return "/"
        escaped = (
            str(part).replace("~", "~0").replace("/", "~1") for part in self.path
        )
        return "/" + "/".join(escaped)


class _ObjectPairs(list[tuple[str, Any]]):
    """Marker used to distinguish JSON objects from arrays during decoding."""


def format_json_path(path: Iterable[str | int]) -> str:
    """Return an unambiguous JSONPath-like location for diagnostics."""

    result = "$"
    for part in path:
        if isinstance(part, int):
            result += f"[{part}]"
        elif part.isidentifier():
            result += f".{part}"
        else:
            result += f"[{json.dumps(part)}]"
    return result


def strip_jsonc(text: str, *, trailing_commas: bool = True) -> str:
    """Remove JSONC comments while preserving strings and source line positions."""

    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "/" and following == "/":
            output.extend((" ", " "))
            index += 2
            while index < len(text) and text[index] not in "\r\n":
                output.append(" ")
                index += 1
            continue
        if char == "/" and following == "*":
            output.extend((" ", " "))
            index += 2
            while index < len(text):
                if index + 1 < len(text) and text[index : index + 2] == "*/":
                    output.extend((" ", " "))
                    index += 2
                    break
                output.append("\n" if text[index] == "\n" else " ")
                index += 1
            else:
                raise ValueError("unterminated JSONC block comment")
            continue
        output.append(char)
        index += 1

    without_comments = "".join(output)
    if not trailing_commas:
        return without_comments

    output = []
    index = 0
    in_string = False
    escaped = False
    while index < len(without_comments):
        char = without_comments[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < len(without_comments) and without_comments[
                lookahead
            ].isspace():
                lookahead += 1
            if (
                lookahead < len(without_comments)
                and without_comments[lookahead] in "}]"
            ):
                index += 1
                continue
        output.append(char)
        index += 1
    return "".join(output)


def loads_strict_json(
    text: str,
    *,
    source: str | Path = "<string>",
    jsonc: bool = False,
    trailing_commas: bool = True,
) -> Any:
    """Decode JSON and reject duplicate object keys at every nesting depth."""

    prepared = strip_jsonc(text, trailing_commas=trailing_commas) if jsonc else text
    value = json.loads(prepared, object_pairs_hook=_ObjectPairs)

    def materialize(item: Any, path: tuple[str | int, ...]) -> Any:
        if isinstance(item, _ObjectPairs):
            result: dict[str, Any] = {}
            for key, child in item:
                child_path = (*path, key)
                if key in result:
                    raise DuplicateJSONKeyError(source, child_path)
                result[key] = materialize(child, child_path)
            return result
        if isinstance(item, list):
            return [materialize(child, (*path, index)) for index, child in enumerate(item)]
        return item

    return materialize(value, ())


__all__ = [
    "DuplicateJSONKeyError",
    "format_json_path",
    "loads_strict_json",
    "strip_jsonc",
]

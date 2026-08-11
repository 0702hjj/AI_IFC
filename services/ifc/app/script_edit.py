# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Targeted scalar-argument rewrite of a script factory call (libcst, lossless)."""

from __future__ import annotations

import json
import math
from typing import Any, Union

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

Scalar = Union[str, int, float, bool]


def _literal(value: Scalar) -> cst.BaseExpression:
    if isinstance(value, bool):
        return cst.Name("True" if value else "False")
    if isinstance(value, (int, float)):
        return cst.Float(repr(value)) if isinstance(value, float) else cst.Integer(repr(value))
    return cst.SimpleString(json.dumps(value, ensure_ascii=False))


class _ArgRewriter(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, line: int, argument: str, value: Scalar) -> None:
        super().__init__()
        self._line, self._argument, self._value = line, argument, value
        self.hit = False

    def leave_Call(self, original: cst.Call, updated: cst.Call) -> cst.Call:
        pos = self.get_metadata(PositionProvider, original, None)
        if pos is None or pos.start.line != self._line:
            return updated
        args, found = [], False
        for arg in updated.args:
            if arg.keyword and arg.keyword.value == self._argument:
                arg = arg.with_changes(value=_literal(self._value))
                found = True
            args.append(arg)
        if not found:
            args.append(
                cst.Arg(
                    keyword=cst.Name(self._argument),
                    value=_literal(self._value),
                    equal=cst.AssignEqual(
                        whitespace_before=cst.SimpleWhitespace(""),
                        whitespace_after=cst.SimpleWhitespace(""),
                    ),
                    whitespace_after_arg=cst.SimpleWhitespace(""),
                )
            )
        self.hit = True
        return updated.with_changes(args=args)


def rewrite_call_argument(script: str, line: int, argument: str, value: Any) -> str:
    """Rewrite `argument=` of the factory call starting at `line`; return new source."""
    if not isinstance(value, (str, int, float, bool)):
        raise ValueError(f"value must be a scalar literal, got {type(value).__name__}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"value must be finite, got {value!r}")
    if not argument.isidentifier():
        raise ValueError(f"argument must be a valid identifier, got {argument!r}")
    try:
        module = cst.parse_module(script)
    except cst.ParserSyntaxError as exc:
        raise ValueError(f"script parse error: {exc}") from exc
    rewriter = _ArgRewriter(line, argument, value)
    new_module = MetadataWrapper(module).visit(rewriter)
    if not rewriter.hit:
        raise ValueError(f"no call found at line {line}")
    return new_module.code

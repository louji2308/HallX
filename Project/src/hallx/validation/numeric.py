"""Numeric and unit consistency checks.

This is a deterministic guard against number drift. It does not attempt
scientific unit conversion; it requires the same normalized value and the same
normalized unit in the claim, the declared values, and the exact quote.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Sequence

_NUMBER = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?(?![\w.])")
_UNIT = re.compile(r"\s*([%‰°]|[A-Za-zµμ][A-Za-z0-9µμ/^·%-]*)")

_UNIT_ALIASES = {
    "%": "percent",
    "percent": "percent",
    "‰": "per-mille",
    "per-mille": "per-mille",
    "°": "degree",
    "deg": "degree",
    "degrees": "degree",
    "degree": "degree",
    "c": "celsius",
    "°c": "celsius",
    "celsius": "celsius",
    "f": "fahrenheit",
    "°f": "fahrenheit",
    "fahrenheit": "fahrenheit",
}


@dataclass(frozen=True, slots=True)
class NormalizedNumber:
    value: Decimal
    unit: str

    def key(self) -> tuple[str, str]:
        return format(self.value.normalize(), "f"), self.unit


@dataclass(frozen=True, slots=True)
class NumericMismatch:
    kind: str
    declared: str
    claim_values: tuple[str, ...]
    quote_values: tuple[str, ...]
    message: str


def _normalize_unit(raw: str) -> str:
    unit = raw.strip().lower().replace(" ", "")
    return _UNIT_ALIASES.get(unit, unit)


def _parse_value(raw: str) -> Decimal:
    return Decimal(raw.replace(",", ""))


def extract_numbers(text: str) -> tuple[NormalizedNumber, ...]:
    numbers: list[NormalizedNumber] = []
    for match in _NUMBER.finditer(text):
        try:
            value = _parse_value(match.group(0))
        except InvalidOperation:
            continue
        unit_match = _UNIT.match(text, match.end())
        unit = _normalize_unit(unit_match.group(1)) if unit_match else ""
        numbers.append(NormalizedNumber(value=value, unit=unit))
    return tuple(numbers)


def parse_declared(raw: str) -> NormalizedNumber | None:
    match = _NUMBER.search(raw)
    if match is None:
        return None
    try:
        value = _parse_value(match.group(0))
    except InvalidOperation:
        return None
    unit_match = _UNIT.match(raw, match.end())
    unit = _normalize_unit(unit_match.group(1)) if unit_match else ""
    return NormalizedNumber(value=value, unit=unit)


def check_numeric_consistency(
    claim_text: str, exact_quote: str, declared_values: Sequence[str]
) -> tuple[NumericMismatch, ...]:
    """Return every number/unit inconsistency between claim, quote, and values."""

    claim_numbers = extract_numbers(claim_text)
    quote_numbers = extract_numbers(exact_quote)
    claim_keys = {number.key() for number in claim_numbers}
    quote_keys = {number.key() for number in quote_numbers}
    claim_display = tuple(str(number.value) + (f" {number.unit}" if number.unit else "") for number in claim_numbers)
    quote_display = tuple(str(number.value) + (f" {number.unit}" if number.unit else "") for number in quote_numbers)

    mismatches: list[NumericMismatch] = []
    for raw in declared_values:
        declared = parse_declared(raw)
        if declared is None:
            mismatches.append(
                NumericMismatch(
                    kind="UNPARSEABLE_DECLARED_VALUE",
                    declared=raw,
                    claim_values=claim_display,
                    quote_values=quote_display,
                    message="declared numeric value could not be parsed",
                )
            )
            continue
        if declared.key() not in claim_keys:
            mismatches.append(
                NumericMismatch(
                    kind="DECLARED_NOT_IN_CLAIM",
                    declared=raw,
                    claim_values=claim_display,
                    quote_values=quote_display,
                    message="declared numeric value does not appear in the claim text",
                )
            )
        if declared.key() not in quote_keys:
            mismatches.append(
                NumericMismatch(
                    kind="DECLARED_NOT_IN_QUOTE",
                    declared=raw,
                    claim_values=claim_display,
                    quote_values=quote_display,
                    message="declared numeric value does not appear in the exact quote",
                )
            )

    for number in claim_numbers:
        if number.key() not in quote_keys:
            mismatches.append(
                NumericMismatch(
                    kind="CLAIM_NUMBER_NOT_IN_QUOTE",
                    declared="",
                    claim_values=claim_display,
                    quote_values=quote_display,
                    message="a number stated in the claim is absent from the exact quote",
                )
            )

    unique: dict[tuple[str, str, tuple[str, ...], tuple[str, ...]], NumericMismatch] = {}
    for mismatch in mismatches:
        unique[
            (mismatch.kind, mismatch.declared, mismatch.claim_values, mismatch.quote_values)
        ] = mismatch
    return tuple(unique.values())

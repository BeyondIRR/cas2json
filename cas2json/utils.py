import re
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from cas2json.exceptions import HeaderParseError
from cas2json.flags import MULTI_TEXT_FLAGS


def get_statement_dates(parsed_lines: list[str], reg_exp: str) -> tuple[str | Any, ...]:
    """
    Helper to get dates for which the statement is applicable.
    """
    text = "\u2029".join(parsed_lines)
    if m := re.search(reg_exp, text, MULTI_TEXT_FLAGS):
        return m.groups()
    raise HeaderParseError("Error parsing CAS header")


def formatINR(value: str | None) -> Decimal | None:
    """Helper to format amount related strings to Decimal."""
    if isinstance(value, str):
        return Decimal(value.replace(",", "_").replace("(", "-").replace(")", ""))
    return None


def format_values(values: Iterable[str | None]) -> list[Decimal | None]:
    return [formatINR(value) for value in values]

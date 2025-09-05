import re
from decimal import Decimal

from cas2json.exceptions import HeaderParseError
from cas2json.flags import MULTI_TEXT_FLAGS


def get_statement_dates(parsed_lines: list[str], reg_exp: str) -> tuple[str | None, str | None]:
    """
    Helper to get dates for which the statement is applicable.
    """
    text = "\u2029".join(parsed_lines)
    if m := re.search(reg_exp, text, MULTI_TEXT_FLAGS):
        return m.groups()
    raise HeaderParseError("Error parsing CAS header")


def formatINR(value: str | None) -> Decimal | None:
    if isinstance(value, str):
        return Decimal(value.replace(",", "_").replace("(", "-"))
    return None

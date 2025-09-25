import logging
import re
from decimal import Decimal

from dateutil import parser as date_parser
from pymupdf import Rect

from cas2json import patterns
from cas2json.constants import MISCELLANEOUS_KEYWORDS
from cas2json.enums import TransactionType
from cas2json.flags import MULTI_TEXT_FLAGS, TEXT_FLAGS
from cas2json.types import TransactionData
from cas2json.utils import formatINR

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_transaction_type(description: str, units: Decimal | None) -> tuple[TransactionType, Decimal | None]:
    """Get transaction type from the description text."""

    description = description.lower()
    # Dividend
    if div_match := re.search(patterns.DIVIDEND, description, TEXT_FLAGS):
        reinvest_flag, dividend_str = div_match.groups()
        dividend_rate = Decimal(dividend_str)
        txn_type = TransactionType.DIVIDEND_REINVEST if reinvest_flag else TransactionType.DIVIDEND_PAYOUT
        return (txn_type, dividend_rate)

    # Tax/Misc
    if units is None:
        if "stt" in description:
            return (TransactionType.STT_TAX, None)
        if "stamp" in description:
            return (TransactionType.STAMP_DUTY_TAX, None)
        if "tds" in description:
            return (TransactionType.TDS_TAX, None)
        return (TransactionType.MISC, None)

    # Purchase/SwitchIn/SIP/Segregation
    if units > 0:
        if "switch" in description:
            return (TransactionType.SWITCH_IN_MERGER if "merger" in description else TransactionType.SWITCH_IN, None)
        if "segregat" in description:
            return (TransactionType.SEGREGATION, None)
        if (
            "sip" in description
            or "systematic" in description
            or re.search("instal+ment", description, re.I)
            or re.search("sys.+?invest", description, TEXT_FLAGS)
        ):
            return (TransactionType.PURCHASE_SIP, None)
        return (TransactionType.PURCHASE, None)

    # Redemption/Reversal/SwitchOut
    if units < 0:
        if re.search(r"reversal|rejection|dishonoured|mismatch|insufficient\s+balance", description, re.I):
            return (TransactionType.REVERSAL, None)
        if "switch" in description:
            return (TransactionType.SWITCH_OUT_MERGER if "merger" in description else TransactionType.SWITCH_OUT, None)
        return (TransactionType.REDEMPTION, None)

    for keyword in MISCELLANEOUS_KEYWORDS:
        if keyword in description:
            return (TransactionType.MISC, None)

    logger.warning("Error identifying transaction. Please report the issue with the transaction description")
    logger.info(f"Txn description: {description} :: Units: {units}")
    return (TransactionType.UNKNOWN, None)


def get_transaction_values(
    values: str, word_rects: list[tuple[Rect, str]], headers: dict[str, Rect]
) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Extract transaction values in the order of amount, units, nav, and balance (in this order) from the given string.
    """

    def formatString(s: str) -> str:
        return s.replace("(", "").replace(")", "").strip()

    txn_values = {"amount": None, "units": None, "nav": None, "balance": None}
    for val in values:
        val_rects = [(w[0], idx) for idx, w in enumerate(word_rects) if formatString(w[1]) == formatString(val)]
        if not val_rects:
            continue
        val_rect, idx = val_rects[0]
        # Remove to avoid matching again
        word_rects.pop(idx)
        for key, header_rect in headers.items():
            if header_rect and val_rect.x0 >= header_rect.x0 - 20 and val_rect.x1 <= header_rect.x1 + 5:
                txn_values[key] = val
    return txn_values["amount"], txn_values["units"], txn_values["nav"], txn_values["balance"]


def get_parsed_scheme_name(scheme: str) -> str:
    scheme = re.sub(r"\((formerly|erstwhile).+?\)", "", scheme, flags=TEXT_FLAGS).strip()
    scheme = re.sub(r"\((Demat|Non-Demat).*", "", scheme, flags=TEXT_FLAGS).strip()
    scheme = re.sub(r"\s+", " ", scheme).strip()
    return re.sub(r"[^a-zA-Z0-9_)]+$", "", scheme).strip()


def parse_transaction(line: str, word_rects: list[tuple[Rect, str]], headers: dict[str, Rect]) -> list[TransactionData]:
    """
    Parse a transaction line and return a list of TransactionData objects.
    """
    transactions: list[TransactionData] = []
    parsed_transactions = re.findall(patterns.TRANSACTIONS, line, MULTI_TEXT_FLAGS)
    if not parsed_transactions:
        return transactions

    for txn in parsed_transactions:
        date, details, *_ = txn
        if not details or not details.strip() or not date:
            continue
        description_match = re.match(patterns.DESCRIPTION, details.strip(), MULTI_TEXT_FLAGS)
        if not description_match:
            continue
        description, values, *_ = description_match.groups()
        values = re.findall(patterns.AMT, values.strip())
        units = nav = balance = amount = None
        if len(values) >= 4:
            # Normal entry
            amount, units, nav, balance, *_ = values
        else:
            amount, units, nav, balance = get_transaction_values(values, word_rects, headers)
        description = description.strip()
        units = formatINR(units)
        txn_type, dividend_rate = get_transaction_type(description, units)
        transactions.append(
            TransactionData(
                date=date_parser.parse(date).date(),
                description=description,
                type=txn_type.name,
                amount=formatINR(amount, negative=False),  # Always consider positive and handle via type
                units=units,
                nav=formatINR(nav),
                balance=formatINR(balance),
                dividend_rate=dividend_rate,
            )
        )
    return transactions

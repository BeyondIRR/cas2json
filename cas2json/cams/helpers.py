import logging
import re
from decimal import Decimal

from cas2json import patterns
from cas2json.constants import MISCELLANEOUS_KEYWORDS
from cas2json.enums import TransactionType
from cas2json.flags import TEXT_FLAGS

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_transaction_type(description: str | None, units: Decimal | None) -> tuple[TransactionType, Decimal | None]:
    """Get transaction type from the description text and units."""
    if not description:
        return (TransactionType.UNKNOWN, None)

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

    logger.warning(f"Error identifying transaction. Description: {description} :: Units: {units}")
    return (TransactionType.UNKNOWN, None)


def get_parsed_scheme_name(scheme: str) -> str:
    """Helper to clean scheme names."""
    scheme = re.sub(r"\((formerly|erstwhile).+?\)", "", scheme, flags=TEXT_FLAGS).strip()
    scheme = re.sub(r"\((Demat|Non-Demat).*", "", scheme, flags=TEXT_FLAGS).strip()
    scheme = re.sub(r"\s+", " ", scheme).strip()
    return re.sub(r"[^a-zA-Z0-9_)]+$", "", scheme).strip()

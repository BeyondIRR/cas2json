from enum import StrEnum, auto


class CustomStrEnum(StrEnum):
    """Custom string enum that auto-generates values in uppercase."""

    @staticmethod
    def _generate_next_value_(name, *args):
        return name.upper()


class FileType(CustomStrEnum):
    """Enum for CAS file source."""

    UNKNOWN = auto()
    CAMS = auto()
    KFINTECH = auto()
    CDSL = auto()
    NSDL = auto()


class CASFileType(CustomStrEnum):
    """Enum for CAS file type"""

    UNKNOWN = auto()
    SUMMARY = auto()
    DETAILED = auto()


class TransactionType(CustomStrEnum):
    PURCHASE = auto()
    PURCHASE_SIP = auto()
    REDEMPTION = auto()
    DIVIDEND_PAYOUT = auto()
    DIVIDEND_REINVEST = auto()
    SWITCH_IN = auto()
    SWITCH_IN_MERGER = auto()
    SWITCH_OUT = auto()
    SWITCH_OUT_MERGER = auto()
    STT_TAX = auto()
    STAMP_DUTY_TAX = auto()
    TDS_TAX = auto()
    SEGREGATION = auto()
    MISC = auto()
    UNKNOWN = auto()
    REVERSAL = auto()

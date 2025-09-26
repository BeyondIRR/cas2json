from collections import defaultdict

from cas2json.enums import CashFlow, TransactionType

HOLDINGS_CASHFLOW = defaultdict(lambda: CashFlow.ADD)
HOLDINGS_CASHFLOW.update(
    {
        TransactionType.PURCHASE: CashFlow.ADD,
        TransactionType.PURCHASE_SIP: CashFlow.ADD,
        TransactionType.DIVIDEND_REINVEST: CashFlow.ADD,
        TransactionType.SWITCH_IN: CashFlow.ADD,
        TransactionType.SWITCH_IN_MERGER: CashFlow.ADD,
        TransactionType.STT_TAX: CashFlow.ADD,
        TransactionType.STAMP_DUTY_TAX: CashFlow.ADD,
        TransactionType.TDS_TAX: CashFlow.ADD,
        TransactionType.SEGREGATION: CashFlow.ADD,
        TransactionType.MISC: CashFlow.ADD,
        TransactionType.UNKNOWN: CashFlow.ADD,
        TransactionType.REVERSAL: CashFlow.ADD,
        TransactionType.REDEMPTION: CashFlow.SUBTRACT,
        TransactionType.SWITCH_OUT: CashFlow.SUBTRACT,
        TransactionType.DIVIDEND_PAYOUT: CashFlow.SUBTRACT,
        TransactionType.SWITCH_OUT_MERGER: CashFlow.SUBTRACT,
    }
)

MISCELLANEOUS_KEYWORDS = ["mobile", "address", "details", "nominee", "change"]

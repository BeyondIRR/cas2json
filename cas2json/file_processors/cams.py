import re
from decimal import Decimal

from dateutil import parser as date_parser

from cas2json import patterns
from cas2json.enums import CASFileType, TransactionType
from cas2json.exceptions import CASParseError
from cas2json.flags import MULTI_TEXT_FLAGS, TEXT_FLAGS
from cas2json.helpers import formatINR, get_statement_dates
from cas2json.types import ProcessedCASData, Scheme, SchemeValuation, StatementPeriod, TransactionData


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

    print("Warning: Error identifying transaction. Please report the issue with the transaction description")
    print(f"Txn description: {description} :: Units: {units}")
    return (TransactionType.UNKNOWN, None)


def get_transaction_values(values: str) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Extract transaction values in the order of amount, units, nav, and balance from the given string.
    """
    values = re.findall(patterns.AMT, values.strip())
    units = nav = balance = amount = None
    if len(values) >= 4:
        # Normal entry
        amount, units, nav, balance, *_ = values
    elif len(values) == 3:
        # Zero unit entry
        amount, nav, balance = values
        units = "0.000"
    elif len(values) == 2:
        # Segregated Portfolio Entries
        units, balance = values
    elif len(values) == 1:
        # Tax entries
        amount = values[0]
    return amount, units, nav, balance


def get_parsed_scheme_name(scheme: str) -> str:
    scheme = re.sub(r"\((formerly|erstwhile).+?\)", "", scheme, flags=TEXT_FLAGS).strip()
    scheme = re.sub(r"\((Demat|Non-Demat).*", "", scheme, flags=TEXT_FLAGS).strip()
    scheme = re.sub(r"\s+", " ", scheme).strip()
    return re.sub(r"[^a-zA-Z0-9_)]+$", "", scheme).strip()


def parse_transaction(line: str, description_tail: str) -> list[TransactionData]:
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
        amount, units, nav, balance = get_transaction_values(values)
        description = description.strip()
        units = formatINR(units)
        if description_tail != "":
            description = f"{description} {description_tail}"
        txn_type, dividend_rate = get_transaction_type(description, units)
        transactions.append(
            TransactionData(
                date=date_parser.parse(date).date(),
                description=description,
                type=txn_type.name,
                amount=formatINR(amount),
                units=units,
                nav=formatINR(nav),
                balance=formatINR(balance),
                dividend_rate=dividend_rate,
            )
        )
    return transactions


def process_detailed_text(parsed_lines: list[str]) -> ProcessedCASData:
    """
    Process the text version of a CAS pdf and return the detailed processed data.
    """

    def finalize_current_scheme():
        """Append current scheme to the schemes list and reset"""
        nonlocal current_scheme
        if current_scheme:
            schemes.append(current_scheme)
            current_scheme = None

    from_date, to_date, *_ = get_statement_dates(parsed_lines, patterns.DETAILED_DATE)
    statement_period = StatementPeriod(from_=from_date, to=to_date)

    schemes: list[Scheme] = []
    current_folio: str | None = None
    current_pan: str | None = None
    current_amc: str | None = None
    current_scheme: Scheme | None = None
    current_registrar: str | None = None
    for idx, line in enumerate(parsed_lines):
        if amc_match := re.search(patterns.AMC, line, TEXT_FLAGS):
            current_amc = amc_match.group(0)
            continue

        if folio_match := re.search(patterns.FOLIO, line):
            folio = folio_match.group(1).strip()
            if current_folio != folio:
                finalize_current_scheme()
                current_folio = folio
                pan_match = re.search(patterns.PAN, line)
                current_pan = pan_match.group(1) if pan_match else None
            continue
        # Long scheme names are sometimes split into multiple lines (usually 2).
        # Thus, we need to join the split lines.
        scheme_line = line
        if idx + 1 < len(parsed_lines) and not re.search(patterns.NOMINEE, line, TEXT_FLAGS):
            scheme_line = f"{scheme_line} {parsed_lines[idx + 1]}"
        if scheme_match := re.search(patterns.SCHEME, scheme_line, MULTI_TEXT_FLAGS):
            if current_folio is None:
                raise CASParseError("Layout Error! Scheme found before folio entry.")

            scheme_name = get_parsed_scheme_name(scheme_match.group("name"))
            if current_scheme and current_scheme.scheme_name != scheme_name:
                finalize_current_scheme()
            # Split Scheme details becomes a bit malformed having "Registrar : CAMS" in between, hence
            # we have to re-parse the line
            formatted_line = re.sub(r"Registrar\s*:\s*CAMS", "", scheme_line).strip()
            metadata = {
                key.strip().lower(): re.sub(r"\s+", "", value)
                for key, value in re.findall(patterns.SCHEME_METADATA, formatted_line, MULTI_TEXT_FLAGS)
            }

            isin_match = re.search(f"({patterns.ISIN})", metadata.get("isin") or "")
            isin = isin_match.group(1) if isin_match else metadata.get("isin")
            current_scheme = Scheme(
                scheme_name=scheme_name,
                amc=current_amc,
                pan=current_pan,
                folio=current_folio,
                advisor=metadata.get("advisor"),
                rta=None,
                rta_code=scheme_match.group("code").strip(),
                isin=isin,
                open=Decimal("0.0"),
                close=Decimal("0.0"),
                close_calculated=Decimal("0.0"),
                valuation=SchemeValuation(date=statement_period.to, value=Decimal("0.0"), nav=Decimal("0.0")),
                transactions=[],
            )
            if current_registrar:
                current_scheme.rta = current_registrar
                current_registrar = None

        # Registrar can be on the same line as scheme description or on the next/previous line
        if registrar_match := re.search(patterns.REGISTRAR, line, TEXT_FLAGS):
            if current_scheme:
                current_scheme.rta = registrar_match.group(1).strip()
            else:
                current_registrar = registrar_match.group(1).strip()
            continue

        if not current_scheme:
            continue

        if nominee_match := re.findall(patterns.NOMINEE, line, TEXT_FLAGS):
            current_scheme.nominees.extend([x.strip() for x in nominee_match if x.strip()])
            continue

        if open_units_match := re.search(patterns.OPEN_UNITS, line):
            current_scheme.open = formatINR(open_units_match.group(1))
            current_scheme.close_calculated = current_scheme.open
            continue

        # All the following details are in one line (generally :))
        if close_units_match := re.search(patterns.CLOSE_UNITS, line):
            current_scheme.close = formatINR(close_units_match.group(1))

        if cost_match := re.search(patterns.COST, line, re.I):
            current_scheme.valuation.cost = formatINR(cost_match.group(1))

        if valuation_match := re.search(patterns.VALUATION, line, re.I):
            current_scheme.valuation.date = date_parser.parse(valuation_match.group(1)).date()
            current_scheme.valuation.value = formatINR(valuation_match.group(2))

        if nav_match := re.search(patterns.NAV, line, re.I):
            current_scheme.valuation.date = date_parser.parse(nav_match.group(1)).date()
            current_scheme.valuation.nav = formatINR(nav_match.group(2))
            continue

        description_tail = ""
        if description_tail_match := re.search(patterns.DESCRIPTION_TAIL, line):
            description_tail = description_tail_match.group(1).strip()
            line = line.replace(description_tail_match.group(1), "")

        if parsed_txns := parse_transaction(line, description_tail):
            for txn in parsed_txns:
                if txn.units is not None:
                    current_scheme.close_calculated += txn.units
            current_scheme.transactions.extend(parsed_txns)

    finalize_current_scheme()

    return ProcessedCASData(cas_type=CASFileType.DETAILED, statement_period=statement_period, schemes=schemes)


def process_summary_text(parsed_lines: list[str]) -> ProcessedCASData:
    """
    Process the text version of a CAS pdf and return the summarized processed data.
    """
    date, *_ = get_statement_dates(parsed_lines, patterns.SUMMARY_DATE)
    statement_period = StatementPeriod(from_=date, to=date)

    schemes: list[Scheme] = []
    current_folio: str | None = None
    for line in parsed_lines:
        if schemes and re.search("Total", line, re.I):
            break

        if summary_row_match := re.search(patterns.SUMMARY_ROW, line, MULTI_TEXT_FLAGS):
            folio = summary_row_match.group("folio").strip()
            if current_folio is None or current_folio != folio:
                current_folio = folio

            scheme_name = summary_row_match.group("name")
            scheme_name = re.sub(r"\(formerly.+?\)", "", scheme_name, flags=TEXT_FLAGS).strip()

            scheme_data = Scheme(
                scheme_name=scheme_name,
                advisor="N/A",
                pan="N/A",
                folio=current_folio,
                amc="N/A",
                rta_code=summary_row_match.group("code").strip(),
                rta=summary_row_match.group("rta").strip(),
                isin=summary_row_match.group("isin"),
                open=formatINR(summary_row_match.group("balance")),
                close=formatINR(summary_row_match.group("balance")),
                close_calculated=formatINR(summary_row_match.group("balance")),
                valuation=SchemeValuation(
                    date=date_parser.parse(summary_row_match.group("date")).date(),
                    nav=formatINR(summary_row_match.group("nav")),
                    value=formatINR(summary_row_match.group("value")),
                    cost=formatINR(summary_row_match.group("cost")),
                ),
                transactions=[],
            )
            schemes.append(scheme_data)

    return ProcessedCASData(cas_type=CASFileType.SUMMARY, statement_period=statement_period, schemes=schemes)

import io
import re

from cas2json import patterns
from cas2json.enums import FileType
from cas2json.exceptions import CASParseError
from cas2json.flags import MULTI_TEXT_FLAGS
from cas2json.parser import cas_pdf_to_text
from cas2json.types import DematAccount, DematOwner, Equity, MutualFund, NSDLCASData, StatementPeriod
from cas2json.utils import get_statement_dates


def process_nsdl_text(text):
    """
    Process the text version of a NSDL pdf and return the processed data.
    """
    hdr_data = get_statement_dates(text[:1000], patterns.DEMAT_STATEMENT_PERIOD)
    statement_period = StatementPeriod(from_=hdr_data["from"], to=hdr_data["to"])
    accounts = re.findall(patterns.DEMAT_HEADER, text, flags=re.I | re.MULTILINE)
    mutual_funds = re.findall(patterns.DEMAT_MF_HEADER, text, flags=re.I | re.MULTILINE)
    demat = {}
    for account_type, account_name, dp_id, client_id, folios, balance in accounts:
        demat[(dp_id, client_id)] = DematAccount(
            name=account_name,
            folios=folios,
            balance=balance,
            type=account_type,
            dp_id=dp_id,
            client_id=client_id,
            owners=[],
            equities=[],
            mutual_funds=[],
        )
    for num_folios, _, balance in mutual_funds:
        demat[(None, None)] = DematAccount(
            name="Mutual Fund Folios",
            folios=num_folios,
            balance=balance,
            type="MF",
            dp_id="",
            client_id="",
            owners=[],
            equities=[],
            mutual_funds=[],
        )

    current_demat = None
    demat_holders = []
    start_processing_holdings = False
    for line in text.split("\u2029"):
        if m := re.search(patterns.DEMAT_AC_TYPE, line, flags=re.I):
            start_processing_holdings = True
            current_demat = None
        if not start_processing_holdings:
            continue
        if current_demat is None:
            if re.search(patterns.DEMAT_MF_TYPE, line.strip(), flags=re.I):
                current_demat = demat[(None, None)]

            if "ACCOUNT HOLDER" in line.upper():
                for owner, pan in re.findall(patterns.DEMAT_AC_HOLDER, line, re.I):
                    demat_holders.append(DematOwner(owner, pan))

            if m := re.search(patterns.DEMAT_DP_ID, line, flags=MULTI_TEXT_FLAGS):
                dp_id, client_id = m.groups()
                current_demat = demat[(dp_id, client_id)]
                current_demat.owners = demat_holders.copy()
                demat_holders = []
            continue
        if "NSDL" in current_demat.type:
            if m := re.search(patterns.NSDL_EQ, line, MULTI_TEXT_FLAGS):
                isin, _, _, num_shares, market_value, current_value = m.groups()
                scheme = Equity(isin=isin, num_shares=num_shares, price=market_value, value=current_value)
                current_demat.equities.append(scheme)
                continue
            elif m := re.search(patterns.NSDL_MF, line, MULTI_TEXT_FLAGS):
                isin, name, balance, nav, value = m.groups()
                scheme = MutualFund(isin=isin, name=name, balance=balance, nav=nav, value=value)
                current_demat.mutual_funds.append(scheme)
                continue
        elif "CDSL" in current_demat.type:
            if m := re.search(patterns.NSDL_CDSL_HOLDINGS, line, MULTI_TEXT_FLAGS):
                isin, name, balance, *_, nav, value = m.groups()
                if isin.startswith("INF"):
                    scheme = MutualFund(isin=isin, name=name, balance=balance, nav=nav, value=value)
                    current_demat.mutual_funds.append(scheme)
                elif isin.startswith("INE"):
                    current_demat.equities.append(Equity(isin=isin, num_shares=balance, price=nav, value=value))
                continue
        elif current_demat.type == "MF" and (m := re.search(patterns.NSDL_MF_HOLDINGS, line, MULTI_TEXT_FLAGS)):
            isin, _, name, _, units, _, _, nav, value, *_ = m.groups()
            name = re.sub(r"\s+", " ", name).strip()
            name = re.sub(r"[^a-zA-Z0-9_)]+$", "", name).strip()
            scheme = MutualFund(isin=isin, name=name, balance=units, nav=nav, value=value)
            current_demat.mutual_funds.append(scheme)

    cas_data = NSDLCASData(
        statement_period=statement_period,
        accounts=list(demat.values()),
    )

    return cas_data


def parse_nsdl_pdf(filename: str | io.IOBase, password: str) -> NSDLCASData:
    partial_cas_data = cas_pdf_to_text(filename, password)
    if partial_cas_data.file_type != FileType.NSDL:
        raise CASParseError("Not a valid NSDL file")
    processed_data = process_nsdl_text("\u2029".join(partial_cas_data.lines))
    return NSDLCASData(
        statement_period=processed_data.statement_period,
        accounts=processed_data.accounts,
        investor_info=partial_cas_data.investor_info,
        file_type=partial_cas_data.file_type,
    )

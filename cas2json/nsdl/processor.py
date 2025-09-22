import io
import re
from collections import defaultdict

from cas2json import patterns
from cas2json.enums import FileType
from cas2json.exceptions import CASParseError
from cas2json.flags import MULTI_TEXT_FLAGS
from cas2json.nsdl.helpers import parse_demat_accounts
from cas2json.parser import cas_pdf_to_text
from cas2json.types import NSDLCASData, Scheme, SchemeType, StatementPeriod
from cas2json.utils import format_values, get_statement_dates

SCHEME_MAP = defaultdict(lambda: SchemeType.OTHER)
SCHEME_MAP.update(
    {
        "Equities (E)": SchemeType.STOCK,
        "Mutual Funds (M)": SchemeType.MUTUAL_FUND,
        "Corporate Bonds (C)": SchemeType.CORPORATE_BOND,
        "Preference Shares (P)": SchemeType.PREFERENCE_SHARES,
    }
)


def process_nsdl_text(parsed_lines: list[str]) -> NSDLCASData:
    """
    Process the text version of a NSDL pdf and return the processed data.
    """
    from_data, to_date = get_statement_dates(parsed_lines, patterns.DEMAT_STATEMENT_PERIOD)
    statement_period = StatementPeriod(from_=from_data, to=to_date)
    demats = parse_demat_accounts(parsed_lines)
    current_demat = None
    schemes = []
    scheme_type = SchemeType.OTHER
    for line in parsed_lines:
        # Do not parse transactions
        if "Summary of Transaction" in line:
            break

        if "NSDL Demat Account" in line or "CDSL Demat Account" in line:
            current_demat = None
            continue

        if dp_client_match := re.search(patterns.DP_CLIENT_ID, line, MULTI_TEXT_FLAGS):
            dp_id, client_id = dp_client_match.groups()
            current_demat = demats.get(dp_id + client_id, None)
            continue

        if current_demat is None:
            continue

        if any(i in line for i in SCHEME_MAP):
            scheme_type = SCHEME_MAP[line.strip()]
            continue

        if folio_scheme_match := re.search(patterns.MF_FOLIO_SCHEMES, line, MULTI_TEXT_FLAGS):
            isin, name, folio, units, price, invested_value, nav, value, *_ = folio_scheme_match.groups()
            units, price, invested_value, nav, value = format_values((units, price, invested_value, nav, value))
            name = re.sub(r"\s+", " ", name).strip()
            scheme = Scheme(
                isin=isin,
                units=units,
                nav=nav,
                market_value=value,
                scheme_type=SchemeType.MUTUAL_FUND,
                cost=price,
                scheme_name=name,
                invested_value=invested_value,
                folio=folio,
            )
            schemes.append(scheme)
            continue

        if current_demat.ac_type == "CDSL" and (
            cdsl_scheme_match := re.search(patterns.CDSL_SCHEME, line, MULTI_TEXT_FLAGS)
        ):
            isin, name, units, _, _, nav, value = cdsl_scheme_match.groups()
            units, nav, value = format_values((units, nav, value))
            name = re.sub(r"\s+", " ", name).strip()
            scheme = Scheme(
                isin=isin,
                scheme_name=name,
                units=units,
                nav=nav,
                market_value=value,
                invested_value=None,
                cost=None,
                scheme_type=scheme_type,
                demat_number=current_demat.dp_id + current_demat.client_id,
            )
            schemes.append(scheme)

        if current_demat.ac_type == "NSDL" and (
            nsdl_scheme_match := re.search(patterns.NSDL_SCHEME, line, MULTI_TEXT_FLAGS)
        ):
            isin, name, price, units, nav, value = nsdl_scheme_match.groups()
            price, units, nav, value = format_values((price, units, nav, value))
            # TODO: name are mostly split into lines but there are cases of page breaks and thus there
            # will be lots of validations and checks to do to parse correct name
            name = re.sub(r"\s+", " ", name).strip()
            scheme = Scheme(
                isin=isin,
                scheme_name=name,
                units=units,
                cost=price,
                nav=nav,
                market_value=value,
                invested_value=price * units if price and units else None,
                scheme_type=scheme_type,
                demat_number=current_demat.dp_id + current_demat.client_id,
            )
            schemes.append(scheme)
            continue

    return NSDLCASData(statement_period=statement_period, accounts=list(demats.values()), schemes=schemes)


def parse_nsdl_pdf(filename: str | io.IOBase, password: str) -> NSDLCASData:
    """
    Parse NSDL pdf and returns processed data.

    Parameters
    ----------
    filename : str | io.IOBase
        The path to the PDF file or a file-like object.
    password : str
        The password to unlock the PDF file.

    Returns
    -------
    Parsed NSDL CAS data
    """
    partial_cas_data = cas_pdf_to_text(filename, password)
    if partial_cas_data.file_type != FileType.NSDL:
        raise CASParseError("Not a valid NSDL file")
    processed_data = process_nsdl_text(partial_cas_data.lines)
    processed_data.file_type = partial_cas_data.file_type
    processed_data.investor_info = partial_cas_data.investor_info
    return processed_data

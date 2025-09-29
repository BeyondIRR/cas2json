import re
from collections import defaultdict
from decimal import Decimal

from cas2json import patterns
from cas2json.flags import MULTI_TEXT_FLAGS
from cas2json.types import DematAccount, DematOwner, DocumentData, NSDLCASData, Scheme, SchemeType, StatementPeriod
from cas2json.utils import format_values, get_statement_dates

SCHEME_MAP = defaultdict(
    lambda: SchemeType.OTHER,
    {
        "Equities (E)": SchemeType.STOCK,
        "Mutual Funds (M)": SchemeType.MUTUAL_FUND,
        "Corporate Bonds (C)": SchemeType.CORPORATE_BOND,
        "Preference Shares (P)": SchemeType.PREFERENCE_SHARES,
    },
)


class NSDLProcessor:
    __slots__ = ()

    @staticmethod
    def extract_holders(line: str) -> DematOwner | None:
        """
        Extract holder details from the line if present.

        Supported line formats
        ----------------------
        - "DEEPESH BHARGAVA (PAN:ALXXXXXX3E)"
        """
        if holder_match := re.search(patterns.DEMAT_HOLDER, line, MULTI_TEXT_FLAGS):
            name, pan = holder_match.groups()
            return DematOwner(name=name.strip(), pan=pan.strip())
        return None

    @staticmethod
    def extract_dp_client_id(line: str) -> tuple[str, str] | None:
        """
        Extract DP ID and Client ID from the line if present.

        Supported line formats
        ----------------------
        - "DP ID:12345678 Client ID:12345678"
        """
        if dp_client_match := re.search(patterns.DP_CLIENT_ID, line, MULTI_TEXT_FLAGS):
            return dp_client_match.groups()
        return None

    @staticmethod
    def extract_nsdl_cdsl_demat(line: str) -> tuple[str, int, Decimal] | None:
        """
        Extract NSDL or CDSL demat account details from the line if present.

        Supported line formats
        ----------------------
        - "NSDL Demat Account 1 1,234.50"   (1 is number of schemes and 1,234.50 is market value)
        - "CDSL Demat Account 2 1,234.50"   (2 is number of schemes and 1,234.50 is market value)
        """
        if demat_match := re.search(patterns.DEMAT, line, MULTI_TEXT_FLAGS):
            ac_type, schemes_count, ac_balance = demat_match.groups()
            schemes_count, ac_balance = format_values((schemes_count, ac_balance))
            return ac_type, int(schemes_count), ac_balance
        return None

    @staticmethod
    def extract_mf_demat(line: str) -> tuple[str, int, Decimal] | None:
        """
        Extract Mutual Fund demat account details from the line if present.

        Supported line formats
        ----------------------
        - "Mutual Fund Folios 10 Folios 10 1234.38"   (10 is number of folios, 10 is number of schemes and 1,234.38 is market value)
        """
        if demat_mf_match := re.search(patterns.DEMAT_MF_HEADER, line, MULTI_TEXT_FLAGS):
            folios, schemes_count, ac_balance = format_values(demat_mf_match.groups())
            return folios, int(schemes_count), ac_balance
        return None

    @staticmethod
    def extract_mf_scheme(line: str) -> Scheme | None:
        """
        Extract Scheme details for MF Folio from the line if present.
        `Annualized Return (%)` is not always available making pattern match fail hence, is not parsed.

        Supported line formats
        ----------------------
        - "INF109K01BF6 ICICI Prudential 123456 1234.793 12.3891 12345.00 12.6220 12345.39 1,354.39 5.42"

        Order of details (in above):

        ISIN, Scheme Name (incomplete), Folio, Units, Cost Per Unit, Total Cost, NAV, Market Value, Unrealized Profit/Loss
        """
        if scheme_match := re.search(patterns.MF_FOLIO_SCHEMES, line, MULTI_TEXT_FLAGS):
            isin, name, folio, units, price, invested_value, nav, value, *_ = scheme_match.groups()
            units, price, invested_value, nav, value = format_values((units, price, invested_value, nav, value))
            name = re.sub(r"\s+", " ", name).strip()
            return Scheme(
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
        return None

    @staticmethod
    def extract_cdsl_scheme(line: str) -> Scheme | None:
        """
        Extract Scheme details for CDSL demat account from the line if present.

        Supported line formats
        ----------------------
        - "INE883F01010 AADHAR HOUSING FINANCE 0.000 0.000 0.000 502.75 0.00"

        Order of details (in above):

        ISIN, Scheme Name (incomplete), Units, SafeKeep Balance, Pledged Balance, NAV, Market Value
        """
        if scheme_match := re.search(patterns.CDSL_SCHEME, line, MULTI_TEXT_FLAGS):
            isin, name, units, _, _, nav, value = scheme_match.groups()
            units, nav, value = format_values((units, nav, value))
            name = re.sub(r"\s+", " ", name).strip()
            return Scheme(isin=isin, scheme_name=name, units=units, nav=nav, market_value=value, cost=None)
        return None

    @staticmethod
    def extract_nsdl_scheme(line: str) -> Scheme | None:
        """
        Extract Scheme details for NSDL demat account from the line if present.

        Supported line formats
        ----------------------
        - "INE758E01017 JIO FINANCIAL SERVICES 10.00 5 311.70 1,558.50"

        Order of details (in above):

        ISIN, Scheme Name (incomplete), Cost per Unit, Units, NAV, Market Value
        """
        if scheme_match := re.search(patterns.NSDL_SCHEME, line, MULTI_TEXT_FLAGS):
            isin, name, price, units, nav, value = scheme_match.groups()
            price, units, nav, value = format_values((price, units, nav, value))
            # TODO: name are mostly split into lines but there are cases of page breaks and thus there
            # will be lots of validations and checks to do to parse correct name
            name = re.sub(r"\s+", " ", name).strip()
            return Scheme(
                isin=isin,
                scheme_name=name,
                units=units,
                cost=price,
                nav=nav,
                market_value=value,
                invested_value=price * units if price and units else None,
            )
        return None

    def process_nsdl_text(self, document_data: DocumentData) -> NSDLCASData:
        """
        Process the text version of a NSDL pdf and return the processed data.
        """
        statement_period: StatementPeriod | None = None
        current_demat: DematAccount | None = None
        schemes: list[Scheme] = []
        scheme_type: SchemeType = SchemeType.OTHER
        holders: list[DematOwner] = []
        demats: dict[str, DematAccount] = {}
        process_demats: bool = True
        for page_data in document_data:
            page_lines = [line for line, _ in page_data.lines_data]

            if not statement_period:
                from_date, to_date = get_statement_dates(page_lines, patterns.DEMAT_STATEMENT_PERIOD)
                statement_period = StatementPeriod(from_=from_date, to=to_date)

            for idx, line in enumerate(page_lines):
                # Do not parse transactions
                if "Summary of Transaction" in line:
                    break

                if process_demats:
                    if holder := self.extract_holders(line):
                        if current_demat:
                            holders = []
                            current_demat = None
                        holders.append(holder)
                        continue

                    if demat_details := self.extract_nsdl_cdsl_demat(line):
                        ac_type, schemes_count, ac_balance = demat_details
                        dp_id, client_id = "", ""
                        if dp_details := self.extract_dp_client_id(
                            page_lines[idx + 1] if idx + 1 < len(page_lines) else ""
                        ):
                            dp_id, client_id = dp_details
                        current_demat = DematAccount(
                            name=page_lines[idx - 1].strip(),
                            ac_type=ac_type,
                            units=ac_balance,
                            dp_id=dp_id,
                            client_id=client_id,
                            schemes_count=schemes_count,
                            holders=holders,
                        )
                        demats[dp_id + client_id] = current_demat
                        continue

                    if mf_demat_details := self.extract_mf_demat(line):
                        folios, schemes_count, ac_balance = mf_demat_details
                        if "MF Folios" not in demats:
                            current_demat = DematAccount(
                                name="Mutual Fund Folios",
                                ac_type="MF",
                                units=ac_balance,
                                folios=folios,
                                schemes_count=schemes_count,
                            )
                            demats["MF Folios"] = current_demat
                        else:
                            current_demat = demats["MF Folios"]
                            current_demat.folios += folios
                            current_demat.schemes_count += schemes_count
                            current_demat.units += ac_balance
                        continue

                if "portfolio value trend" in line.lower():
                    process_demats = False
                    continue

                if "NSDL Demat Account" in line or "CDSL Demat Account" in line:
                    current_demat = None
                    continue

                if dp_client_ids := self.extract_dp_client_id(line):
                    current_demat = demats.get(dp_client_ids[0] + dp_client_ids[1], None)
                    continue

                if current_demat is None:
                    continue

                if any(i in line for i in SCHEME_MAP):
                    scheme_type = SCHEME_MAP[line.strip()]
                    continue

                if mf_scheme := self.extract_mf_scheme(line):
                    schemes.append(mf_scheme)
                    continue

                if current_demat.ac_type == "CDSL" and (cdsl_scheme := self.extract_cdsl_scheme(line)):
                    cdsl_scheme.scheme_type = scheme_type
                    cdsl_scheme.demat_number = current_demat.dp_id + current_demat.client_id
                    schemes.append(cdsl_scheme)
                    continue

                if current_demat.ac_type == "NSDL" and (nsdl_scheme := self.extract_nsdl_scheme(line)):
                    nsdl_scheme.scheme_type = scheme_type
                    nsdl_scheme.demat_number = current_demat.dp_id + current_demat.client_id
                    schemes.append(nsdl_scheme)

        return NSDLCASData(statement_period=statement_period, accounts=list(demats.values()), schemes=schemes)

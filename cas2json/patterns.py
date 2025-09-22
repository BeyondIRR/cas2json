# ---------------CAMS--------------- #

DATE = r"(\d{2}-[A-Za-z]{3}-\d{4})"
AMT = r"([(-]*\d[\d,.]+)\)*"
ISIN = r"[A-Z]{2}[0-9A-Z]{9}[0-9]{1}"
# Summary Version
SUMMARY_ROW = (
    rf"(?P<folio>[\d/\s]+?)?(?P<isin>{ISIN})\s+(?P<code>[ \w]+)-"
    r"(?P<name>.+?)\s+(?P<cost>[\d,.]+)?\s+(?P<balance>[\d,.]+)\s*"
    r"(?P<date>\d{2}-[A-Za-z]{3}-\d{4})\s*(?P<nav>[\d,.]+)\s*(?P<value>[\d,.]+)\s*(?P<rta>\w+)\s*$"
)
# Detailed Version
# Scheme details
SCHEME = r"(?P<code>[\w]+)\s*-\s*\d*\s*(?P<name>.+?)(?:\(Advi|ISIN).*$"
SCHEME_METADATA = r"([A-Za-z]+)\s*:\s*([-\w]+(?:\s+[-\w]+)*)"
REGISTRAR = r"Registrar\s*:\s*(.+?)(?:\s\s|$)"
AMC = r"^(.+?\s+(MF|Mutual\s*Fund)|franklin\s+templeton\s+investments)$"
NOMINEE = r"Nominee\s*\d+\s*:\s*([^:]+?)(?=\s*Nominee\s*\d+\s*:|$)"
OPEN_UNITS = r"Opening\s+Unit\s+Balance.+?([\d,.]+)"
CLOSE_UNITS = r"Closing\s+Unit\s+Balance.+?([\d,.]+)"
COST = r"Total\s+Cost\s+Value\s*:.+?[INR\s]*([\d,.]+)"
VALUATION = rf"(?:Valuation|Market\s+Value)\s+on\s+{DATE}\s*:\s*INR\s*([\d,.]+)"
NAV = rf"NAV\s+on\s+{DATE}\s*:\s*INR\s*([\d,.]+)"
FOLIO = r"Folio\s+No\s*:\s+([\d/\s]+\d)\s"
# Transaction details
# To not match text like "15-Sep-2025: 1% redeemed.... added exclusion for ':' "
TRANSACTIONS = rf"^{DATE}\s*([^:]*?)(?=\s*{DATE}|\Z)"
DESCRIPTION = r"^(.*?)\s+((?:[(-]*[\d,]+\.\d+\)*\s*)+)"
CAS_TYPE = r"consolidated\s+account\s+(statement|summary)"
DETAILED_DATE = rf"{DATE}\s+to\s+{DATE}"
SUMMARY_DATE = rf"as\s+on\s+{DATE}"
DIVIDEND = r"(?:div\.|dividend|idcw).+?(reinvest)*.*?@\s*Rs\.\s*([\d\.]+)(?:\s+per\s+unit)?"

# Investor Details
INVESTOR_STATEMENT = r"Mutual\s+Fund|Date\s+Transaction|Folio\s+No|^Date\s*$"
INVESTOR_MAIL = r"^\s*email\s+id\s*:\s*(.+?)(?:\s|$)"

# ---------------NSDL--------------- #

DEMAT_STATEMENT_PERIOD = (
    r"for\s+the\s+period\s+from\s+(\d{2}-[a-zA-Z0-9]{2,3}-\d{4})"
    r"\s+to\s+(\d{2}-[a-zA-Z0-9]{2,3}-\d{4})"
)
PAN = r"PAN\s*:\s*([A-Z]{5}\d{4}[A-Z])"
# Account details
DEMAT = r"(CDSL|NSDL)\s+Demat\s+Account\s+(\d+)\s+([\d,.]+)"
DP_CLIENT_ID = r"^DP\s*Id\s*:\s*(.+?)\s*Client\s*Id\s*:\s*(\d+)"
DEMAT_MF_HEADER = r"Mutual Fund Folios\s+(\d+)\s+Folios\s+(\d+)\s+([\d,.]+)"
DEMAT_HOLDER = r"([^\t\n0-9]+?)\s*\(PAN\s*:\s*(.+?)\)"
# Scheme details
NSDL_SCHEME = rf"^({ISIN})\s*(.+?)\s*{AMT}\s+([\d,.]+)\s+{AMT}\s+{AMT}$"
CDSL_SCHEME = rf"^({ISIN})\s*(.+?)\s+" + rf"{AMT}\s+" * 4 + rf"{AMT}$"
MF_FOLIO_SCHEMES = rf"^({ISIN})\s*(.+?)\s+(\d*)\s+" + rf"{AMT}\s+" * 5 + rf"{AMT}"
# Investor Details
CAS_ID = r"[CAS|NSDL]\s+ID\s*:\s*(.+?)(?:\s|$)"
INVESTOR_STATEMENT_DP = r"Statement\s+for\s+the\s+period|Your\s+demat\s+account\s+and\s+mutual\s+fund"

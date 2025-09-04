"""Regular expressions for parsing various sections in CAS."""

DATE = r"(\d{2}-[A-Za-z]{3}-\d{4})"
AMT = r"([(-]*\d[\d,.]+)\)*"
ISIN = r"[A-Z]{2}[0-9A-Z]{9}[0-9]{1}"


SUMMARY_ROW = r"(?P<folio>[\d/\s]+?)(?P<isin>[A-Z]{2}[0-9A-Z]{9}[0-9]{1})?\s+(?P<code>[ \w]+)-(?P<name>.+?)\s+(?P<cost>[\d,.]+)?\s+(?P<balance>[\d,.]+)\t\t(?P<date>\d{2}-[A-Za-z]{3}-\d{4})\t\t(?P<nav>[\d,.]+)\t\t(?P<value>[\d,.]+)\t\t(?P<rta>\w+)\s*$"

FOLIO = r"Folio\s+No\s*:\s+([\d/\s]+\d)\s"

DESCRIPTION_TAIL = r"(\n.+?)(\s\s|$)"
DIVIDEND = r"(?:div\.|dividend|idcw).+?(reinvest)*.*?@\s*Rs\.\s*([\d\.]+)(?:\s+per\s+unit)?"
SCHEME_TAIL = r"(\n.+?)(?:\s\s|$)"

DEMAT_HEADER = (
    r"((?:CDSL|NSDL)\s+demat\s+account)\s+(.+?)\s*DP\s*Id\s*:\s*(.+?)"
    r"\s*Client\s*Id\s*:\s*(\d+)\s+(\d+)\s+([\d,.]+)"
)
DEMAT_MF_HEADER = r"Mutual Fund Folios\s+(\d+)\s+folios\s+(\d+)\s+([\d,.]+)"
DEMAT_AC_TYPE = r"^(NSDL|CDSL)\s+demat\s+account|Mutual\s+Fund\s+Folios\s+\(F\)"
DEMAT_MF_TYPE = r"^Mutual\s+Fund\s+Folios\s+\(F\)$"
DEMAT_AC_HOLDER = r"([^\t\n]+?)\s*\(PAN\s*:\s*(.+?)\)"
DEMAT_DP_ID = r"DP\s*Id\s*:\s*(.+?)\s*Client\s*Id\s*:\s*(\d+).+PAN"
NSDL_EQ = (
    rf"^([A-Z]{{2}}[E|9][0-9A-Z]{{8}}[0-9]{{1}})"
    rf"\s*(.+?)\s*{AMT}\s+([\d,.]+)\s+{AMT}\s+{AMT}$"
)
NSDL_MF = rf"^(INF[0-9A-Z]{{8}}[0-9]{{1}})\s*(.*?)\s*{AMT}\s+{AMT}\s+{AMT}$"
NSDL_CDSL_HOLDINGS = r"^([A-Z]{2}[0-9A-Z]{9}[0-9]{1})\s*(.+?)\s+" + rf"{AMT}\s+" * 10 + rf"{AMT}$"
NSDL_MF_HOLDINGS = (
    rf"({ISIN})\n(.+?)[\n\t]+(.+?)\t\t(\w+?)\t\t{AMT}"
    rf"\t\t{AMT}\t\t{AMT}\t\t{AMT}\t\t{AMT}\t\t{AMT}(?:\t\t{AMT})?$"
)

INVESTOR_STATEMENT = r"Mutual\s+Fund|Date\s+Transaction|Folio\s+No|^Date\s*$"
INVESTOR_STATEMENT_DP = r"Statement\s+for\s+the\s+period|Your\s+demat\s+account\s+and\s+mutual\s+fund"
INVESTOR_MAIL = r"^\s*email\s+id\s*:\s*(.+?)(?:\s|$)"
CAS_ID = r"[CAS|NSDL]\s+ID\s*:\s*(.+?)(?:\s|$)"

# CAMS

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

# Transaction details
# To not match transactions like "15-Sep-2025: 1% redeemed.... added exclusion for ':' "
TRANSACTIONS = rf"{DATE}\s*([^:]*?)(?=\s*{DATE}|\Z)"
DESCRIPTION = r"^(.*?)\s+((?:[(-]*[\d,]+\.\d+\)*\s*)+)"
CAS_TYPE = r"consolidated\s+account\s+(statement|summary)"
DETAILED_DATE = rf"{DATE}\s+to\s+{DATE}"
SUMMARY_DATE = rf"as\s+on\s+{DATE}"

# NSDL
DEMAT_STATEMENT_PERIOD = (
    r"for\s+the\s+period\s+from\s+(\d{2}-[a-zA-Z0-9]{2,3}-\d{4})"
    r"\s+to\s+(\d{2}-[a-zA-Z0-9]{2,3}-\d{4})"
)
PAN = r"PAN\s*:\s*([A-Z]{5}\d{4}[A-Z])"

import io
import re

from pymupdf import TEXTFLAGS_TEXT, Document, Page, Rect

from cas2json.enums import FileType
from cas2json.exceptions import CASParseError, IncorrectPasswordError
from cas2json.patterns import CAS_ID, INVESTOR_MAIL, INVESTOR_STATEMENT, INVESTOR_STATEMENT_DP
from cas2json.types import InvestorInfo, PartialCASData


def parse_file_type(page_blocks: list[tuple]) -> FileType:
    """Parse file type using text of blocks. First page of File is preferred"""
    for block in page_blocks:
        block_text = block[4].strip()
        if re.search("CAMSCASWS", block_text):
            return FileType.CAMS
        elif re.search("KFINCASWS", block_text):
            return FileType.KFINTECH
        elif "NSDL Consolidated Account Statement" in block_text or "About NSDL" in block_text:
            return FileType.NSDL
        elif "Central Depository Services (India) Limited" in block_text:
            return FileType.CDSL
    return FileType.UNKNOWN


def parse_investor_info(page: Page, is_cams=True) -> InvestorInfo:
    """
    Parse investor info using pymupdf tables.

    Parameters
    ----------
    page : Page
        The pymupdf page object to extract information from.
    is_cams : bool
        Flag indicating if the document is a CAMS statement.
        Used to swap regex patterns.

    Returns
    -------
    InvestorInfo
        The extracted investor information.
    """
    email_found = False
    address_lines = []
    email = mobile = name = None

    regex_string = INVESTOR_MAIL if is_cams else CAS_ID
    statement_regex = INVESTOR_STATEMENT if is_cams else INVESTOR_STATEMENT_DP

    tables = page.find_tables(strategy="lines")
    first_table = tables.tables[0] if tables.tables else None
    # getting text of first row
    row_text = first_table.extract()[0]

    for cell_text in row_text:
        for text in cell_text.strip().split("\n"):
            text = text.strip()
            if is_cams and not email_found:
                if email_match := re.search(regex_string, text, re.I):
                    email = email_match.group(1).strip()
                    email_found = True
                continue

            if name is None:
                name = text
                continue

            if re.search(statement_regex, text, re.I | re.MULTILINE) or mobile is not None:
                return InvestorInfo(email=email, name=name, mobile=mobile or "", address="\n".join(address_lines))
            if mobile_match := re.search(r"mobile\s*:\s*([+\d]+)(?:s|$)", text, re.I):
                mobile = mobile_match.group(1).strip()
            address_lines.append(text)

    raise CASParseError("Unable to parse investor data")


def recover_lines(page: Page):
    """
    Reconstitute text lines on the page by using the coordinates of the
    single words.

    Based on `get_sorted_text` of pymupdf.

    Parameters
    ----------
    page : Page
        The pymupdf page object to extract information from.

    Returns
    -------
    list[str]
        A list of reconstituted text lines.
    """
    # flags are important as they control the extraction behavior like keep "hidden text" or not
    words = [(Rect(w[:4]), w[4]) for w in page.get_text("words", sort=True, flags=TEXTFLAGS_TEXT)]
    if not words:
        return []

    lines = []
    line = [words[0]]  # current line
    lrect = words[0][0]  # the line's rectangle

    # walk through the words
    for wr, text in words[1:]:
        # ignore vertical elements
        if abs(wr.x1 - wr.x0) * 4 < abs(wr.y1 - wr.y0):
            continue
        # if this word matches top or bottom of the line, append it
        if abs(lrect.y0 - wr.y0) <= 3 or abs(lrect.y1 - wr.y1) <= 3:
            line.append((wr, text))
            lrect |= wr
        else:
            # output current line and re-initialize
            # note that we sort the words in current line first
            ltext = " ".join([w[1] for w in sorted(line, key=lambda w: w[0].x0)])
            lines.append((lrect, ltext))
            line = [(wr, text)]
            lrect = wr

    # also append last unfinished line
    ltext = " ".join([w[1] for w in sorted(line, key=lambda w: w[0].x0)])
    lines.append((lrect, ltext))

    # sort all lines vertically
    lines.sort(key=lambda x: (x[0].y1))

    # Return list of line texts
    return [ltext for _, ltext in lines]


def cas_pdf_to_text(filename: str | io.IOBase, password: str) -> PartialCASData:
    """
    Parse CAS pdf and returns line data.

    Parameters
    ----------
    filename : str | io.IOBase
        The path to the PDF file or a file-like object.
    password : str
        The password to unlock the PDF file.

    Returns
    -------
    PartialCasData which includes investor info, file type and parsed text lines (as much as close to original layout)
    """
    if isinstance(filename, str):
        fp = open(filename, "rb")  # NOQA
    elif hasattr(filename, "read") and hasattr(filename, "close"):  # file-like object
        fp = filename
    else:
        raise CASParseError("Invalid input. filename should be a string or a file like object")

    with fp:
        try:
            doc = Document(stream=fp.read(), filetype="pdf")
        except Exception as e:
            raise CASParseError(f"Unhandled error while opening file :: {e!s}") from e

        if doc.needs_pass:
            rc = doc.authenticate(password)
            if not rc:
                raise IncorrectPasswordError("Incorrect PDF password!")

        first_page_blocks = doc.get_page_text(pno=0, flags=TEXTFLAGS_TEXT, sort=True, option="blocks")
        file_type = parse_file_type(first_page_blocks)

        investor_info = None
        if file_type in (FileType.CAMS, FileType.KFINTECH):
            investor_info = parse_investor_info(doc.load_page(0))
        elif file_type in (FileType.NSDL, FileType.CDSL):
            # NSDL has no information on first page
            investor_info = parse_investor_info(doc.load_page(1), is_dp=True)

        lines = []
        for page_num, page in enumerate(doc):
            if file_type == FileType.NSDL and page_num == 0:
                # No useful data in first page of NSDL doc
                continue
            lines.extend(recover_lines(page))

        return PartialCASData(file_type=file_type, investor_info=investor_info, lines=lines)

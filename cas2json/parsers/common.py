import io
import re

from pymupdf import Document, Page, Rect

from cas2json.enums import FileType
from cas2json.exceptions import CASParseError, IncorrectPasswordError
from cas2json.patterns import CAS_ID, INVESTOR_MAIL, INVESTOR_STATEMENT, INVESTOR_STATEMENT_DP
from cas2json.types import InvestorInfo, PartialCASData


def parse_file_type(blocks):
    """Parse file type."""
    for block in sorted(blocks, key=lambda x: -x["bbox"][1]):
        block_str = str(block)
        if re.search("CAMSCASWS", block_str):
            return FileType.CAMS
        elif re.search("KFINCASWS", block_str):
            return FileType.KFINTECH
        elif "NSDL Consolidated Account Statement" in block_str or "About NSDL" in block_str:
            return FileType.NSDL
        elif "Central Depository Services (India) Limited" in block_str:
            return FileType.CDSL
    return FileType.UNKNOWN


def parse_investor_info(page_dict, page_rect: Rect, is_dp=False) -> InvestorInfo:
    """Parse investor info."""
    width = max(page_rect.width, 600)
    height = max(page_rect.height, 800)

    blocks = sorted([x for x in page_dict["blocks"] if x["bbox"][1] < height / 2], key=lambda x: x["bbox"][1])

    email_found = False
    address_lines = []
    email = mobile = name = None

    width_factor = 2 if is_dp else 3
    regex_string = CAS_ID if is_dp else INVESTOR_MAIL
    statement_regex = INVESTOR_STATEMENT_DP if is_dp else INVESTOR_STATEMENT

    for block in blocks:
        for line in block["lines"]:
            for span in filter(
                lambda x: x["bbox"][0] <= width / width_factor and x["text"].strip() != "", line["spans"]
            ):
                txt = span["text"].strip()
                # TODO: check this : extract email id if not dp
                if not email_found and not is_dp:
                    if email_match := re.search(regex_string, txt, re.I):
                        email = email_match.group(1).strip()
                        email_found = True
                    continue

                if name is None:
                    name = txt
                    continue

                if re.search(statement_regex, txt, re.I | re.MULTILINE) or mobile is not None:
                    return InvestorInfo(email=email, name=name, mobile=mobile or "", address="\n".join(address_lines))
                if mobile_match := re.search(r"mobile\s*:\s*([+\d]+)(?:s|$)", txt, re.I):
                    mobile = mobile_match.group(1).strip()
                address_lines.append(txt)
    raise CASParseError("Unable to parse investor data")


def recover_lines(page: Page):
    """
    Reconstitute text lines on the page by using the coordinates of the
    single words.
    """
    # extract words, sorted by bottom, then left coordinate
    words = [(Rect(w[:4]), w[4]) for w in page.get_text("words", sort=True)]
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

        lines = []
        investor_info = None

        for page_num, page in enumerate(doc):
            text_page = page.get_textpage()
            # sort blocks vertically
            page_dict = text_page.extractDICT(sort=True)
            lines.extend(recover_lines(page))
            file_type = parse_file_type(page_dict["blocks"])

            if investor_info is None:
                if file_type in (FileType.CAMS, FileType.KFINTECH):
                    investor_info = parse_investor_info(page_dict, page.rect)
                elif file_type in (FileType.NSDL, FileType.CDSL) and page_num == 1:
                    investor_info = parse_investor_info(page_dict, page.rect, is_dp=True)
            if file_type == FileType.NSDL and page_num == 0:
                # Ignore first page. no useful data
                continue

        return PartialCASData(file_type=file_type, investor_info=investor_info, lines=lines)

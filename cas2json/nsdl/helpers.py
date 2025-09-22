import re

from cas2json import patterns
from cas2json.flags import MULTI_TEXT_FLAGS
from cas2json.types import DematAccount, DematOwner
from cas2json.utils import format_values


def parse_demat_accounts(parsed_lines: list[str]) -> dict[str, DematAccount]:
    """
    Helper to parse demat accounts from lines of text.
    Returns a dictionary with key as DP ID + Client ID or "MF Folios" for mutual fund folios.
    """
    demats: dict[str, DematAccount] = {}
    holders: list[DematOwner] = []
    current_demat = None
    for idx, line in enumerate(parsed_lines):
        if holder_match := re.search(patterns.DEMAT_HOLDER, line, MULTI_TEXT_FLAGS):
            if current_demat and holders:
                holders = []
            name, pan = holder_match.groups()
            holders.append(DematOwner(name=name.strip(), pan=pan.strip()))
            continue

        if demat_match := re.search(patterns.DEMAT, line, MULTI_TEXT_FLAGS):
            ac_type, schemes_count, ac_balance = demat_match.groups()
            dp_id, client_id = "", ""
            if dp_client_match := re.search(patterns.DP_CLIENT_ID, parsed_lines[idx + 1], MULTI_TEXT_FLAGS):
                dp_id, client_id = dp_client_match.groups()
            schemes_count, ac_balance = format_values((schemes_count, ac_balance))
            current_demat = DematAccount(
                name=parsed_lines[idx - 1].strip(),
                ac_type=ac_type,
                units=ac_balance,
                dp_id=dp_id,
                client_id=client_id,
                schemes_count=schemes_count,
                holders=holders,
            )
            demats[dp_id + client_id] = current_demat
            continue

        if demat_mf_match := re.search(patterns.DEMAT_MF_HEADER, line, MULTI_TEXT_FLAGS):
            folios, schemes_count, ac_balance = format_values(demat_mf_match.groups())
            if "MF Folios" not in demats:
                current_demat = DematAccount(
                    name="Mutual Fund Folios",
                    ac_type="MF",
                    units=ac_balance,
                    folios=int(folios),
                    schemes_count=int(schemes_count),
                )
                demats["MF Folios"] = current_demat
            else:
                current_demat = demats["MF Folios"]
                current_demat.folios += int(folios)
                current_demat.schemes_count += int(schemes_count)
                current_demat.units += ac_balance
    return demats

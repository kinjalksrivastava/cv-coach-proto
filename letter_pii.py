"""
The cover letter's own personal-data layer.

pii.strip_pii() was written for a CV, where the only person named is the author.
A cover letter names a second person: whoever it is addressed to. That person
never uploaded anything and never agreed to anything, and their name is not the
student's to hand over. Round 5 caught the tool repeating one back:

    "The cover letter is addressed to Anna-Sophia Schmitz, who is listed as
     'Deputy CHRO Division Service' at Stadler Rail AG."

The CV layer had no reason to look for them. It removes the author's name
everywhere once it has found it in the contact block, and a body name is only
trusted with corroboration, which an address block does not provide.

So this runs the CV layer first, unchanged - it is the one that knows how to
take the author apart - and then removes the recipient from what is left. By
that point the author's own block is already a placeholder, so a person's name
still standing above the salutation belongs to the recipient.

What stays: the company. "Why this organisation?" is one of Career Services'
nine checks and cannot be answered against a blank. Job titles stay too, the
student's for the same reason they stay on a CV.
"""

import re

import pii
import pii_local

PLACEHOLDER = pii.CATEGORIES["recipient"][0]
# Every marker the removal layers write, so the sweep below never redacts a
# redaction.
PLACEHOLDERS = [value[0] for value in pii.CATEGORIES.values()]

# "z. Hd. Anna-Sophia Schmitz", "zu Handen von ...", "Attn: ...". The marker is
# kept and only what follows it is removed, so the letter still reads as having
# been addressed to someone.
ATTENTION_RE = re.compile(
    r"^(\s*(?:z\.?\s*hd\.?(?:\s+von)?|zu\s+h[äa]nden(?:\s+von)?|attn\.?|attention"
    r"|for the attention of|f\.?\s*a\.?\s*o\.?)\s*[:.]?\s*)(\S.*)$",
    re.IGNORECASE)

# The opener is kept for the same reason: cover_letter.analyse() checks that the
# letter has a salutation at all, and that check has to go on working.
SALUTATION_RE = re.compile(
    r"^(\s*(?:dear|sehr\s+geehrte[rn]?|liebe[rs]?|guten\s+tag)\b[\s,]*)(.*)$",
    re.IGNORECASE)

HONORIFIC_RE = re.compile(
    r"^(?:mr|mrs|ms|miss|dr|prof(?:essor)?|herr|frau)\b\.?\s+", re.IGNORECASE)

# Salutations that name nobody. Removing from these would turn "Dear Sir or
# Madam" into a redaction notice and tell the student personal data was found
# where there is none.
GENERIC_TAIL_RE = re.compile(
    r"^(?:sir|sirs|madam|madams|sir or madam|sir/madam|hiring\s+(?:manager|team|committee)"
    r"|recruit(?:ment|ing)\s+team|recruiter|ladies\s+and\s+gentlemen|damen\s+und\s+herren"
    r"|damen|herren|team|colleagues|all)\b[\s,.:;!-]*$",
    re.IGNORECASE)

# Lines in the address block that are plainly not a person.
COMPANY_SUFFIX_RE = re.compile(
    r"\b(ag|gmbh|sa|sarl|ltd|limited|llp|llc|inc|plc|kg|se|ohg|gbr|co|corp|"
    r"holding|group|gruppe|bank|universit[äay]t?|university|hochschule|"
    r"spital|klinik|stiftung|verein|kanton|stadt|gemeinde)\b\.?\s*$",
    re.IGNORECASE)

# How far down a letter the address block can plausibly reach when there is no
# salutation to stop at.
MAX_ADDRESS_LINES = 18

# A name immediately followed by one of these is part of an organisation's name.
_COMPANY_FOLLOWS = (r"[\s\-]+(?:AG|GmbH|SA|SARL|Ltd|Limited|LLP|LLC|Inc|PLC|KG|SE|"
                    r"OHG|GbR|Co|Corp|Holding|Group|Gruppe|Bank|Stiftung|Verein|"
                    r"Institut|Institute|University|Universit[äa]t|Hochschule)\b")

# The author's own name, at the bottom. A CV always opens with a contact block,
# so pii.strip_pii learns the author's name from the top of the page and then
# removes it everywhere. A letter need not have one: plenty open straight on
# "Sehr geehrte Frau ...", and then the only place the author is named is under
# the sign-off, which the CV layer has no reason to look at. Round 5 did not
# catch this one; the test letters did.
# "Your sincerely" with no s is in Career Services' own template, and a student
# copying it should not have their name sent to the model as the price.
CLOSING_RE = re.compile(
    r"^(\s*(?:yours?\s+(?:sincerely|faithfully|truly)|kind(?:est)?\s+regards"
    r"|best\s+(?:regards|wishes)|sincerely(?:\s+yours)?|warm\s+regards|regards"
    # "ue" as well as "ü": some PDF extractions transliterate the umlaut away.
    r"|mit\s+freundlichen\s+gr[üu]e?(?:ss|ß)en|freundliche\s+gr[üu]e?(?:ss|ß)e"
    r"|mit\s+besten\s+gr[üu]e?(?:ss|ß)en|beste\s+gr[üu]e?(?:ss|ß)e"
    r"|herzliche\s+gr[üu]e?(?:ss|ß)e|hochachtungsvoll)\s*[,.]?\s*)(.*)$",
    re.IGNORECASE)

# "Ms [RECIPIENT REDACTED]" reads as a leak that was half-caught. The honorific
# carries nothing once the name is gone, so it goes with it.
LEFTOVER_HONORIFIC_RE = re.compile(
    r"\b(?:mr|mrs|ms|miss|dr|prof(?:essor)?|herr|frau)\b\.?\s+"
    r"(?=" + "|".join(re.escape(p) for p in PLACEHOLDERS) + r")",
    re.IGNORECASE)


def _tail_names(text: str) -> tuple[str, list[str], bool]:
    """
    The two places a letter spells out who it is for: the attention line and the
    salutation. Both keep their opener and lose what follows.
    """
    names: list[str] = []
    hit = False
    out = []
    for line in text.splitlines():
        for pattern in (ATTENTION_RE, SALUTATION_RE):
            match = pattern.match(line)
            if not match:
                continue
            opener, tail = match.group(1), match.group(2).strip(" ,.:;")
            tail = HONORIFIC_RE.sub("", tail).strip(" ,.:;")
            if not tail or GENERIC_TAIL_RE.match(tail):
                break
            names.append(tail)
            line = opener.rstrip() + " " + PLACEHOLDER
            hit = True
            break
        out.append(line)
    return "\n".join(out), names, hit


def _address_block(lines: list[str]) -> list[str]:
    """Everything above the salutation, which is where the recipient is written."""
    for index, line in enumerate(lines):
        if SALUTATION_RE.match(line) and line.strip():
            return lines[:index]
    return lines[:MAX_ADDRESS_LINES]


def _address_names(text: str, language: str) -> list[str]:
    """
    A person named above the salutation of a letter is the person it is for. The
    author is not a candidate here: pii.strip_pii has already run and replaced
    their block. No corroboration is asked for, unlike in the body of a CV,
    because an address block is corroboration - that is what it is for.
    """
    if not pii_local.available():
        return []
    block = "\n".join(
        line for line in _address_block(text.splitlines())
        if line.strip() and not COMPANY_SUFFIX_RE.search(line.strip())
    )
    if not block.strip():
        return []
    other = "de" if language != "de" else "en"
    veto = (pii_local.place_and_org_strings(text, language)
            | pii_local.place_and_org_strings(text, other))
    return pii._filter_names(pii_local.detect_persons(block, language), veto, text)


def _author_line(line: str) -> bool:
    """
    Name-shaped for the one position where position is the evidence: the line
    under the sign-off. pii._looks_like_a_name_line is not used here because it
    vetoes any line containing a role word, and "Martina Master" - the author
    of Career Services' own template - is vetoed by her own surname. In a CV
    that veto is right, because a job title sits where a name might. Under a
    sign-off nothing else belongs.
    """
    stripped = line.strip()
    if not (2 < len(stripped) <= 60) or any(ch.isdigit() for ch in stripped):
        return False
    if "@" in stripped or ":" in stripped:
        return False
    words = stripped.replace(",", " ").split()
    return (1 < len(words) <= 4
            and all(w[0].isupper() for w in words if w[:1].isalpha()))


def _signoff_name(text: str) -> str | None:
    """
    The name under the sign-off, where a letter that never gave a contact block
    names its author. Taken only when the line is name-shaped: an enclosure
    note or a postscript sits in the same place and is not a name.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = CLOSING_RE.match(line)
        if not match:
            continue
        # "Mit freundlichen Grüssen, Jonas Keller" puts both on one line.
        tail = match.group(2).strip(" ,.")
        if tail and _author_line(tail):
            return tail
        for following in lines[index + 1:index + 4]:
            candidate = following.strip(" ,.")
            if not candidate or PLACEHOLDER in candidate:
                continue
            if any(placeholder in candidate
                   for placeholder, _ in pii.CATEGORIES.values()):
                return None
            return candidate if _author_line(candidate) else None
    return None


def _other_people(text: str, language: str) -> list[str]:
    """
    Anyone else the letter names in passing. Career Services' own template says
    "It was a pleasure meeting you and Max Mustermann at HSG Talents" - a third
    person, at a named company, who agreed to nothing.

    A CV only trusts a body name with corroboration, because most body hits
    there are institutions a small model misread. A letter is prose about one
    organisation, so the same hits are much more likely to be people, and the
    place-and-organisation veto already holds back the company names. What is
    lost if this is wrong is one word of a sentence the model still reads.
    """
    if not pii_local.available():
        return []
    other = "de" if language != "de" else "en"
    veto = (pii_local.place_and_org_strings(text, language)
            | pii_local.place_and_org_strings(text, other))
    return [name for name in pii._filter_names(
        pii_local.detect_persons(text, language), veto, text)
        if len(name.split()) > 1]


def _address_block_sweep(text: str, language: str) -> tuple[str, bool]:
    """
    Positional, and the backstop for everything the name model does not see.

    Above the salutation a letter carries exactly three kinds of line: the two
    parties' addresses, the organisation, and a date or a reference. Anything
    there that is a short run of capitalised words with no digits in it is a
    person or a person's job title - "Ms Anika Muster", "HR Business Partner",
    "Martina Master", none of which spaCy flagged on Career Services' own
    template. The organisation is held back by its legal suffix and by the
    model's own organisation list, because "why this organisation?" is one of
    the nine checks.

    This runs last, so the lines it looks at are what survived every other
    layer.
    """
    lines = text.splitlines()
    cut = len(_address_block(lines))
    if not cut:
        return text, False
    orgs = (pii_local.place_and_org_strings(text, language)
            | pii_local.place_and_org_strings(
                text, "de" if language != "de" else "en")) if pii_local.available() else set()

    out, hit = [], False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if index >= cut or not stripped:
            out.append(line)
            continue
        if any(place in stripped for place in PLACEHOLDERS):
            out.append(line)
            continue
        if COMPANY_SUFFIX_RE.search(stripped) or stripped.lower() in orgs:
            out.append(line)
            continue
        words = stripped.replace(",", " ").split()
        if (1 < len(words) <= 4
                and not any(ch.isdigit() for ch in stripped)
                and all(w[0].isupper() for w in words if w[:1].isalpha())
                and not any(w.lower() in orgs for w in words)):
            out.append(PLACEHOLDER)
            hit = True
            continue
        out.append(line)
    return "\n".join(out), hit


def _redact(text: str, names: list[str], placeholder: str = PLACEHOLDER) -> tuple[str, bool]:
    """
    Every part of the name, everywhere in the letter. "Dear Ms Schmitz" three
    paragraphs down is the same person as the address block.
    """
    working, hit = text, False
    for part in pii._name_parts(names):
        # Not where the same word is the start of the company's name. A letter
        # to Frau Maria Muster at Muster GmbH would otherwise lose the company
        # along with the person, and "why this organisation?" is one of the
        # nine checks.
        new = re.sub(r"\b" + re.escape(part) + r"\b(?!" + _COMPANY_FOLLOWS + r")",
                     placeholder, working)
        if new != working:
            working, hit = new, True
    return working, hit


def strip_letter_pii(text: str, language: str = "en") -> dict:
    """
    Same contract as pii.strip_pii, same keys, plus the recipient. Makes no
    network call, for the same reason that one does not.
    """
    result = pii.strip_pii(text, language)
    if not text.strip():
        return result

    working, names, marked = _tail_names(result["text"])
    names += [n for n in _address_names(working, language) if n not in names]
    working, redacted = _redact(working, names)
    working, swept = _address_block_sweep(working, language)
    redacted = redacted or swept
    # Unconditional: the CV layer may have taken the name and left the "Ms".
    working = LEFTOVER_HONORIFIC_RE.sub("", working)

    author = _signoff_name(working)
    signed = False
    if author:
        working, signed = _redact(working, [author], pii.CATEGORIES["name"][0])

    working, others = _redact(working, _other_people(working, language),
                              pii.CATEGORIES["name"][0])
    signed = signed or others

    if marked or redacted or signed:
        result["text"] = working
        if signed and "name" not in result["categories"]:
            result["categories"] = result["categories"] + ["name"]
            result["redactions"] = result["redactions"] + [pii.CATEGORIES["name"][1]]
            result["names_found"] = result.get("names_found", 0) + 1
        if (marked or redacted) and "recipient" not in result["categories"]:
            result["categories"] = result["categories"] + ["recipient"]
            result["redactions"] = result["redactions"] + [pii.CATEGORIES["recipient"][1]]
        # The sweep runs again: the recipient layer rewrote the text after
        # pii.strip_pii verified it, and a verification that ran before the last
        # edit has verified the wrong document.
        result["residual"] = pii.residual_pii(working)
    return result

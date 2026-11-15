"""Hindi / Hinglish number words -> digits ("छः सौ पचास" -> "650", "paanch hazaar" -> "5000").

Speech-to-text sometimes spells amounts out. Converting them to digits keeps the rule-based parser
and the number guard working. Ambiguous words ("दो"/"do" = two or give, "saath" = sixty or with)
are only treated as numbers next to another number word.
"""
from __future__ import annotations

import re

_DEV_1_99 = (
    "एक दो तीन चार पांच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस बीस "
    "इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस "
    "छत्तीस सैंतीस अड़तीस उनतालीस चालीस इकतालीस बयालीस तैंतालीस चवालीस पैंतालीस छियालीस सैंतालीस "
    "अड़तालीस उनचास पचास इक्यावन बावन तिरेपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ साठ इकसठ बासठ "
    "तिरेसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर "
    "छिहत्तर सतहत्तर अठहत्तर उन्यासी अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सतासी अट्ठासी "
    "नवासी नब्बे इक्यानवे बानवे तिरानवे चौरानवे पचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे"
).split()

UNITS: dict[str, int] = {w: i + 1 for i, w in enumerate(_DEV_1_99)}
UNITS.update({"पाँच": 5, "छः": 6, "छे": 6, "छ": 6, "पन्द्रह": 15, "शून्य": 0})
UNITS.update({
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "chhah": 6, "che": 6,
    "saat": 7, "aath": 8, "nau": 9, "das": 10, "gyarah": 11, "barah": 12, "pandrah": 15, "bees": 20,
    "pachchis": 25, "pachis": 25, "tees": 30, "chalis": 40, "chaalis": 40, "pachas": 50, "pachaas": 50,
    "saath": 60, "sattar": 70, "assi": 80, "nabbe": 90,
})
MULTIPLIERS = {"सौ": 100, "sau": 100, "हज़ार": 1000, "हजार": 1000, "hazaar": 1000, "hazar": 1000,
               "hajar": 1000, "लाख": 100_000, "lakh": 100_000, "lac": 100_000}
FRACTIONS = {"डेढ़": 1.5, "dedh": 1.5, "ढाई": 2.5, "dhai": 2.5}
AMBIGUOUS = {"दो", "do", "saath", "सात", "nau", "नौ", "das", "char"}

_TOKEN = re.compile(r"[ऀ-ॿ]+|[A-Za-z]+|\d+(?:,\d+)*|\S")


def _value(tok: str) -> float | None:
    t = tok.lower()
    if re.fullmatch(r"\d+(?:,\d+)*", t):
        return float(t.replace(",", ""))
    if t in UNITS:
        return float(UNITS[t])
    if t in FRACTIONS:
        return FRACTIONS[t]
    return None


def _is_num(tok: str) -> bool:
    t = tok.lower()
    return _value(t) is not None or t in MULTIPLIERS


def _combine(tokens: list[str]) -> int:
    total, current = 0.0, 0.0
    for tok in tokens:
        t = tok.lower()
        if t in MULTIPLIERS:
            m = MULTIPLIERS[t]
            if m == 100:
                current = (current or 1) * 100
            else:
                total += (current or 1) * m
                current = 0
        else:
            current += _value(t) or 0
    return int(round(total + current))


DATE_WORDS = {"तारीख", "तारीख़", "tareekh", "tarikh", "tarik", "दिन", "din", "hafte", "हफ्ते"}


def words_to_digits(text: str) -> str:
    """Replace runs of number words with digits, keeping the rest of the text (and spacing) as is."""
    spans = [(m.start(), m.end(), m.group(0)) for m in _TOKEN.finditer(text)]
    out, pos, i = [], 0, 0
    while i < len(spans):
        start, end, tok = spans[i]
        if not _is_num(tok):
            i += 1
            continue
        j = i
        while j + 1 < len(spans) and _is_num(spans[j + 1][2]) and text[spans[j][1]:spans[j + 1][0]].strip() == "":
            j += 1
        group = [s[2] for s in spans[i:j + 1]]
        has_word = any(_value(g) is None or not re.fullmatch(r"\d+(?:,\d+)*", g) for g in group)
        next_tok = spans[j + 1][2].lower() if j + 1 < len(spans) else ""
        lone_ambiguous = len(group) == 1 and group[0].lower() in AMBIGUOUS and next_tok not in DATE_WORDS
        lone_multiplier = len(group) == 1 and group[0].lower() in MULTIPLIERS
        if has_word and not lone_ambiguous and not lone_multiplier:
            out.append(text[pos:start])
            out.append(str(_combine(group)))
            pos = spans[j][1]
        i = j + 1
    out.append(text[pos:])
    return "".join(out)

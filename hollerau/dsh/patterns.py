"""Find a supplier's pattern fast: the sentences it repeats, and what followed them before.

Almost every supplier follows a logic of its own - it answers our movement with its own, or it
needs its boss for the big step, or it prices every term we ask - and it says so, in sentences
that come back from one supplier to the next ("We need to clarify this internally - we will come
back to you on price."). `cues.json` (built offline by `lab/dsh_archives.py` from the replays of
our finished games) holds those sentences with what followed each: how large the supplier's next
step was, what it was per euro of our move, how often the next reply was a final offer.
`signals` reads a thread, recognises the sentences and returns them with those records - leaving
out the games of the case being played, so that the record is about suppliers, never about this
case. Nothing here decides: it tells the model what kind of supplier it is facing.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from statistics import median

CUES = Path(__file__).with_name("cues.json")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
SERIES = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9…]+)+\b")
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
WORD = re.compile(r"[a-zäöüß<>…€]+", re.I)
MIN_RECORD = 5  # fewer replies than this in the other cases: the sentence is shown without a record


def normalise(sentence):
    """A sentence without its figures and index names: what the replay's reasons look like."""
    s = NUMBER.sub("…", sentence)
    s = re.sub(r"(?:… ?)+", "… ", s)
    s = SERIES.sub("<SERIES>", s)
    return re.sub(r"\s+", " ", s).strip()


def _words(sentence):
    return frozenset(w.lower() for w in WORD.findall(sentence))


@lru_cache(maxsize=1)
def library():
    try:
        rows = json.loads(CUES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    return tuple({**r, "words": _words(r["cue"])} for r in rows)


def recognise(sentence):
    """The library entry a supplier's sentence matches (exactly, or nearly: suppliers rephrase)."""
    text = normalise(sentence)
    words = _words(text)
    if len(words) < 4:
        return None
    best, score = None, 0.0
    for entry in library():
        if entry["cue"] == text:
            return entry
        both = len(words & entry["words"])
        s = both / len(words | entry["words"])
        if s > score:
            best, score = entry, s
    return best if score >= 0.8 else None


def record(entry, skip_case=None):
    """What followed this sentence in our finished games, the case being played left out."""
    cells = [c for case, c in entry["by_case"].items() if case != skip_case]
    replies = sum(c["replies"] for c in cells)
    if replies < MIN_RECORD:
        return None
    steps = [v for c in cells for v in c["next_step_pct"]]
    ratio = [v for c in cells for v in c["per_eur_of_our_move"]]
    final = [v for c in cells for v in c["next_final"]]
    out = {"replies_in_our_records": replies, "suppliers_who_said_it": entry["suppliers"]}
    if steps:
        out["its_next_step_pct_of_opening_to_best"] = round(median(steps), 1)
    if len(ratio) >= MIN_RECORD:
        out["its_next_step_per_eur_of_our_move"] = round(median(ratio), 2)
    if final:
        out["next_reply_was_its_final_offer_pct"] = round(100 * sum(final) / len(final))
    return out


def signals(events, skip_case=None):
    """Per supplier reply, the sentences we recognise and their record: [{"reply", "said": [...]}]."""
    out, n = [], 0
    for m in events:
        if m.get("from") == "buyer":
            continue
        said, seen = [], set()
        for sentence in SENTENCE.split(m.get("body") or ""):
            entry = recognise(sentence) if sentence.strip() else None
            if entry is None or entry["cue"] in seen:
                continue
            seen.add(entry["cue"])
            item = {"sentence": entry["cue"]}
            rec = record(entry, skip_case)
            if rec:
                item["what_followed_in_our_records"] = rec
            said.append(item)
        if said and n:  # the opening quote answers nothing of ours
            out.append({"its_reply_number": n, "it_said": said})
        n += 1
    return out

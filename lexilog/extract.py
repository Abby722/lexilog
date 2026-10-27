"""Turn a document (PDF or image) into a ranked list of vocabulary candidates.

Pipeline: text with page numbers → segments (sentences or table rows, each with
its section heading) → tokens → dictionary forms → filter known and common
words → rank by frequency → meanings and word parts from the offline dictionary.
"""
import io
import re
from collections import defaultdict
from dataclasses import dataclass, field

from . import dictionary as dictmod
from . import nlp as nlpmod

KEEP_POS = {"NOUN", "VERB", "ADJ", "ADV"}
WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœ][A-Za-zÀ-ÖØ-öø-ÿŒœ'’-]*")
ARTICLES = {"der", "die", "das", "le", "la", "les", "l'", "un", "une", "ein", "eine"}
FUGEN_STEMS = ("ung", "ion", "heit", "keit", "schaft", "tät", "ität", "ling", "tum")


@dataclass
class Segment:
    text: str
    page: int | None
    heading: str = ""

    @property
    def context(self) -> str:
        if self.heading and not self.text.startswith(self.heading):
            return f"{self.heading} → {self.text}"
        return self.text


# ---------- 1. text ----------

def pages_from_file(data: bytes, filename: str, language: str) -> list[tuple[int, str]]:
    name = filename.lower()
    if name.endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return [(i + 1, p.extract_text() or "") for i, p in enumerate(pdf.pages)]
    if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")):
        return [(1, ocr_image(data, language))]
    if name.endswith((".txt", ".md")):
        return [(1, data.decode("utf-8", errors="replace"))]
    raise ValueError("Use a PDF, an image (PNG or JPG) or a text file.")


def ocr_image(data: bytes, language: str) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Reading images needs pytesseract and Pillow: "
                           "pip install pytesseract pillow") from exc
    code = {"de": "deu", "fr": "fra"}[language]
    try:
        return pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang=code)
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError("Reading images needs the Tesseract program. See the README.") from exc
    except pytesseract.TesseractError as exc:
        raise RuntimeError(f"Tesseract has no '{code}' language data installed. "
                           "See the README.") from exc


# ---------- 2. segments ----------

def _is_heading(line: str) -> bool:
    """Short, number-free lines that start a block: section titles and table headers."""
    words = line.split()
    return (0 < len(words) <= 6 and not any(c.isdigit() for c in line)
            and line[0].isupper() and not line.endswith((",", ";", "!", "?")))


def _is_table_row(line: str) -> bool:
    return bool(re.search(r"\d", line)) and not line.endswith((".", "!", "?"))


def segment(pages: list[tuple[int, str]]) -> list[Segment]:
    """Split page text into sentences and table rows, remembering the latest heading."""
    out: list[Segment] = []
    for page, text in pages:
        heading, buffer = "", []

        def flush():
            if buffer:
                para = re.sub(r"-\n(?=[a-zäöü])", "", "\n".join(buffer)).replace("\n", " ")
                for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜÀ-Ý])", para):
                    if s.strip():
                        out.append(Segment(s.strip(), page, heading))
                buffer.clear()

        for raw in text.splitlines():
            line = re.sub(r"\s+", " ", raw).strip()
            if not line:
                flush()
            elif _is_heading(line) and (not buffer or buffer[-1].endswith((".", "!", "?", ":"))):
                flush()
                heading = line
                out.append(Segment(line, page, ""))
            elif _is_table_row(line):
                flush()
                out.append(Segment(line, page, heading))
            else:
                buffer.append(line)
        flush()
    return out


# ---------- 3. candidates ----------

@dataclass
class Candidate:
    lemma: str
    pos: str | None = None
    count: int = 0
    forms: set = field(default_factory=set)
    contexts: list = field(default_factory=list)   # (context, page)
    gender: str | None = None
    plural: str | None = None
    gloss: str = ""
    parts: str = ""
    verb_forms: str = ""
    irregular: bool | None = None
    known: bool = False

    def best_context(self) -> tuple[str, int | None]:
        good = [c for c in self.contexts if 25 <= len(c[0]) <= 220]
        pool = good or self.contexts
        return min(pool, key=lambda c: abs(len(c[0]) - 90)) if pool else ("", None)


def normalise_known(lemma: str) -> str:
    words = lemma.strip().split()
    if len(words) > 1 and words[0].lower() in ARTICLES:
        words = words[1:]
    return " ".join(words).lower()


def _stopwords(language: str) -> set[str]:
    try:
        if language == "de":
            from spacy.lang.de.stop_words import STOP_WORDS
        else:
            from spacy.lang.fr.stop_words import STOP_WORDS
        return set(STOP_WORDS)
    except ImportError:
        return {"und", "oder", "der", "die", "das", "mit", "für", "von", "auf", "pro", "aus",
                "le", "la", "les", "et", "ou", "de", "des", "du", "pour", "avec", "dans"}


# ---------- compounds ----------

def _strip_linking(left: str, d) -> str:
    """Remove a linking element: 'Übertragungs' → 'Übertragung', 'Bundes' → 'Bund'."""
    options = [left]
    for suffix in ("es", "s", "en", "n", "e"):
        if left.lower().endswith(suffix) and len(left) - len(suffix) >= 3:
            options.append(left[:-len(suffix)])
    if d is not None:
        for o in options:
            if d.has(o):
                return o
    if left.lower().endswith("s") and left.lower()[:-1].endswith(FUGEN_STEMS):
        return left[:-1]
    return left


def split_parts(word: str, d=None, min_len: int = 9) -> list[str]:
    """Split a German compound: 'Übertragungsnetz' → ['Übertragung', 'Netz']."""
    if len(word) < min_len:
        return []
    try:
        from compound_split import char_split
    except ImportError:
        return []
    is_adj = word[:1].islower()
    score, left, right = char_split.split_compound(word.capitalize())[0]
    if score < 0.6:
        return []
    left = _strip_linking(left.capitalize(), d)
    sub = split_parts(right if not is_adj else right.lower(), d, min_len)
    last = sub if sub else [right.lower() if is_adj else right.capitalize()]
    return [left] + last


def _short(gloss: str | None) -> str:
    return re.split(r"[;,(]", gloss or "")[0].strip()


def describe_parts(parts: list[str], d) -> str:
    out = []
    for p in parts:
        e = d.lookup(p) if d else None
        short = _short(e["gloss"]) if e else ""
        out.append(f"{p} ({short})" if short else p)
    return " + ".join(out)


def _fill_from_head(c: "Candidate", parts: list[str], d):
    """A German compound takes gender and plural from its last part:
    Netz + Zuschlag (m, pl. Zuschläge) → der Netzzuschlag, pl. Netzzuschläge."""
    if not parts or d is None:
        return
    head = d.lookup(parts[-1], prefer_pos="noun") or {}
    prefix = c.lemma[: len(c.lemma) - len(parts[-1])]
    if not c.gender and head.get("gender"):
        c.gender = head["gender"]
    if not c.plural and head.get("plural") and c.lemma.lower().endswith(parts[-1].lower()):
        c.plural = prefix + head["plural"].lower()
    if not c.gloss:
        shorts = [_short((d.lookup(p) or {}).get("gloss")) for p in parts]
        if all(shorts):
            c.gloss = "≈ " + " + ".join(shorts)


def _choose_lemma(lemma: str, surface: str, pos: str, d) -> str:
    """Prefer whichever form the dictionary knows; for unknown compounds, fix the last part."""
    if d is None:
        return lemma
    for cand in (lemma, surface):
        if d.has(cand):
            return cand
    base = d.base_form(surface)
    if base:
        return base
    if pos == "NOUN":
        parts = split_parts(surface, d)
        if parts:
            last = surface[len(surface) - len(parts[-1]):]   # e.g. "kosten" in Messkosten
            if d.has(last):
                return surface                               # plural-only head such as Kosten
            head_base = d.base_form(last)
            if head_base:
                return surface[: len(surface) - len(last)] + head_base.lower()
    return lemma


# ---------- candidates ----------

def candidates(segments: list[Segment], language: str, known: set[str] = frozenset(),
               min_len: int = 3, data_dir: str | None = None) -> list[Candidate]:
    """All content words in the document. Words already in `known` are marked, not dropped."""
    d = dictmod.load(language, data_dir)
    nlp = nlpmod._load(language)
    stop = _stopwords(language)
    known = {normalise_known(k) for k in known}
    found: dict[str, Candidate] = {}

    def add(lemma, surface, pos, seg):
        key = lemma if pos == "NOUN" else lemma.lower()
        c = found.get(key) or found.setdefault(key, Candidate(lemma=key, pos=pos))
        c.count += 1
        c.forms.add(surface)
        if len(c.contexts) < 20:
            c.contexts.append((seg.context, seg.page))

    texts = [s.text for s in segments]
    if nlp is not None:
        for seg, doc in zip(segments, nlp.pipe(texts, batch_size=64)):
            for t in doc:
                if (t.pos_ not in KEEP_POS or t.is_stop or not t.is_alpha
                        or len(t.text) < min_len or t.text.isupper()):
                    continue
                if (t.i + 1 < len(doc) and doc[t.i + 1].text == "." and not t.whitespace_
                        and t.text.islower() and len(t.text) <= 5
                        and not (d and d.has(t.text))):
                    continue  # abbreviation such as "exkl." or "inkl."
                lemma = _choose_lemma(t.lemma_, t.text, t.pos_, d)
                if t.pos_ == "NOUN":
                    lemma = lemma[:1].upper() + lemma[1:]
                if language == "de" and t.pos_ == "VERB":
                    particles = [c.text.lower() for c in t.children if c.dep_ == "svp"]
                    if particles:
                        lemma = particles[0] + lemma
                add(lemma, t.text, t.pos_, seg)
    else:  # no spaCy model: plain words, capitalised German words treated as nouns
        for seg in segments:
            for w in WORD_RE.findall(seg.text):
                if len(w) < min_len or w.lower() in stop or w.isupper():
                    continue
                pos = "NOUN" if language == "de" and w[0].isupper() else None
                add(_choose_lemma(w, w, pos, d), w, pos, seg)

    result = []
    pos_map = {"NOUN": "noun", "VERB": "verb", "ADJ": "adj", "ADV": "adv"}
    for c in found.values():
        if c.lemma.lower() in stop:
            continue
        c.known = normalise_known(c.lemma) in known
        if d:
            e = d.lookup(c.lemma, prefer_pos=pos_map.get(c.pos))
            if e:
                c.gloss, c.gender, c.plural = e["gloss"] or "", e["gender"], e["plural"]
                c.verb_forms = e.get("verb_forms") or ""
                c.irregular = bool(e["irregular"]) if e.get("irregular") is not None else None
                if c.pos is None and e.get("pos") in ("noun", "verb", "adj", "adv"):
                    c.pos = {v: k for k, v in pos_map.items()}[e["pos"]]
        if language == "de" and c.pos in ("NOUN", "ADJ", None):
            parts = split_parts(c.lemma, d)
            if parts:
                c.parts = describe_parts(parts, d)
                if c.pos in ("NOUN", None) and c.lemma[:1].isupper():
                    _fill_from_head(c, parts, d)
                elif not c.gloss and d:
                    shorts = [_short((d.lookup(p) or {}).get("gloss")) for p in parts]
                    if all(shorts):
                        c.gloss = "≈ " + " + ".join(shorts)
        if c.pos and c.pos != "NOUN":
            c.gender = c.plural = None
        result.append(c)

    # Frequent first; among equals, longer words (usually the document's own terms) first.
    return sorted(result, key=lambda c: (-c.count, -len(c.lemma), c.lemma.lower()))

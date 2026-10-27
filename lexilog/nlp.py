"""Optional lemmatization with spaCy.

If spaCy or the language models are missing, everything still works: the
suggestion simply falls back to the text you selected.

Install models with:
    python -m spacy download de_core_news_sm
    python -m spacy download fr_core_news_sm
"""
from functools import lru_cache

MODELS = {"de": "de_core_news_sm", "fr": "fr_core_news_sm"}
GENDER = {"Masc": "m", "Fem": "f", "Neut": "n"}


@lru_cache(maxsize=2)
def _load(language: str):
    try:
        import spacy
        return spacy.load(MODELS[language])
    except Exception:
        return None


def available(language: str) -> bool:
    return _load(language) is not None


def suggest(language: str, text: str, sentence: str = "") -> dict:
    """Suggest lemma, part of speech and gender for a selected word or phrase.

    Multi-word selections are treated as expressions and kept as typed, except
    that German separable verbs ("schließt ... ab") are joined back together.
    """
    text = text.strip()
    result = {"lemma": text, "pos": None, "gender": None,
              "kind": "expression" if len(text.split()) > 1 else "word"}
    nlp = _load(language)
    if nlp is None or not text:
        return result

    doc = nlp(sentence if sentence and text.split()[0] in sentence else text)
    target = [t for t in doc if t.text.lower() == text.split()[0].lower()]
    if not target:
        target = list(nlp(text))
    tok = target[0]

    if result["kind"] == "word":
        result["lemma"] = tok.lemma_ if tok.pos_ != "PROPN" else tok.text
        result["pos"] = tok.pos_
        g = tok.morph.get("Gender")
        result["gender"] = GENDER.get(g[0]) if g else None
        # German separable verb: attach the particle ("ab") found in the sentence
        if language == "de" and tok.pos_ in ("VERB", "AUX"):
            particles = [c.text.lower() for c in tok.children if c.dep_ == "svp"]
            if particles:
                result["lemma"] = particles[0] + tok.lemma_
    else:
        result["pos"] = "EXPR"
    return result

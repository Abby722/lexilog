# lexilog

A personal system for learning German and French vocabulary from real material.
Every word or expression is logged together with **where you met it**: the sentence,
the source (news site, Duolingo, a PDF book, a podcast transcript, a YouTube video) and
the date. Those contexts feed spaced-repetition flashcards and a progress dashboard.

## Why encounters, not word lists

Most vocabulary tools store a word and a translation. lexilog stores *encounters*:
each time you meet *abschließen* or *en revanche*, it becomes a new context under the
same entry. That gives you

- flashcards that show a different real sentence each time,
- a record of which sources actually teach you words,
- the words you keep meeting but still don't know, which are the ones worth attention.

## Quick start

```bash
pip install -r requirements.txt
python scripts/seed_demo.py                     # optional: 12 weeks of sample data
LEXILOG_DB=data/demo.db streamlit run app.py    # explore the demo
streamlit run app.py                            # your own data, in data/lexilog.db
```

### Language tools (one-time setup)

**Dictionary forms** (*Abgaben* → *Abgabe*, *schließt ... ab* → *abschließen*):

```bash
python -m spacy download de_core_news_sm
python -m spacy download fr_core_news_sm
```

**Offline dictionary** for meanings, gender and plurals, built from Wiktionary data.
On https://kaikki.org/dictionary/, open German (and French), download the JSONL file
with all senses, then:

```bash
python scripts/build_dictionary.py de path/to/german-file.jsonl
python scripts/build_dictionary.py fr path/to/french-file.jsonl
```

This creates `data/dictionary_de.sqlite` with meanings, genders, plurals and, for
verbs, the key forms (*er geht · ging · ist gegangen*) and whether the verb is
irregular. The download can be deleted afterwards, but keep it if you expect to
rebuild after an update of lexilog.

German compounds that Wiktionary doesn't list get their gender and plural from their
last part (*Netz* + *Zuschlag* → *der Netzzuschlag*, pl. *Netzzuschläge*) and a
meaning assembled from the parts, marked with ≈.

**Reading screenshots and scanned pages** needs the Tesseract OCR program with German
and French language data:
- Mac: `brew install tesseract tesseract-lang`
- Windows: the installer from UB Mannheim (github.com/UB-Mannheim/tesseract/wiki);
  tick German and French under "Additional language data" during setup.

Everything works without these tools; you just get fewer automatic suggestions.

## Capturing words

| Source | How |
|---|---|
| DW, Tagesschau, Le Monde, any web page | Bookmarklet (see *Goals & capture*): select a phrase, click, and the sentence, link and language are filled in |
| YouTube / Netflix | Save words in Language Reactor, export, then *Import* |
| Reports, PDFs, screenshots | *Read a document*: drop the file in, tick the words worth learning |
| PDF books you annotate | Export highlights from your PDF reader or Zotero as CSV, then *Import* |
| Podcast transcripts | Web transcript: bookmarklet. File: *Import* |
| Duolingo, class, conversation | *Add a word* by hand |

## Reading a document

*Read a document* turns a PDF, screenshot or text file into a list of words you don't
have yet. Each comes with its dictionary form, gender, a meaning from the offline
dictionary, its word parts (*Netzzuschlag* = *Netz* + *Zuschlag*) and the place it
appears; for tables, that's the row with its section heading. Words are ranked by how
often the document uses them.

If a word you already have turns up in a new document, no duplicate is created: the
document is added to the places where that word appeared (the *Appeared in* column in
the *Word list*).

Every list you save is also written as a CSV to `data/lists/`, named by date and title,
in a format the *Import* page reads back. They are kept out of Git by default; delete
the `data/lists/` line in `.gitignore` to version them too.

## Architecture

```
app.py                 Streamlit entry point and navigation
views/                 One file per page (dashboard, capture, review, list, import, goals)
lexilog/
  schema.sql           lexemes, encounters, cards, review_log, goals
  db.py                data access; every function takes a connection
  scheduler.py         spaced repetition (SM-2 variant), pure and tested
  stats.py             dashboard aggregations in pandas, no UI code
  importers.py         CSV/TSV/Excel import with column auto-detection
  extract.py           document → segments → ranked vocabulary candidates
  dictionary.py        offline Wiktionary dictionary (build + lookup)
  nlp.py               optional spaCy lemmatisation, incl. German separable verbs
bookmarklet.js         browser capture
scripts/seed_demo.py   demo data
scripts/build_dictionary.py   builds the offline dictionary from kaikki.org data
tests/                 pytest
```

Design choices: SQLite keeps everything in one portable file; the scheduler and
statistics are plain functions with no UI dependencies, so they are unit-tested and
could back a different front end later (a web API, or a page on a personal site).

## Roadmap

- [ ] Replace SM-2 with FSRS (`pip install fsrs`) and compare retention
- [ ] Frequency-list coverage ("you know 1,840 of the 3,000 most common words")
- [ ] Audio and images on cards (pronunciation, *Fluent Forever* style)
- [ ] Anki export for reviewing on the phone
- [ ] Read-only public dashboard for a personal website

## Tests

```bash
pytest
```

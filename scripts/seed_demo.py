"""Fill a database with ~12 weeks of plausible demo activity.

    python scripts/seed_demo.py                 # writes data/demo.db
    LEXILOG_DB=data/demo.db streamlit run app.py
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lexilog import db  # noqa: E402

GERMAN = [
    ("abschließen", "to complete; to lock", "VERB", None, "Die Regierung will die Verhandlungen bis Ende des Jahres abschließen.", "news", "DW Nachrichten"),
    ("die Verhandlung", "negotiation", "NOUN", "f", "Die Verhandlungen dauerten bis spät in die Nacht.", "news", "Tagesschau"),
    ("der Haushalt", "budget; household", "NOUN", "m", "Der Bundestag stimmt heute über den Haushalt ab.", "news", "DW Nachrichten"),
    ("allerdings", "however; admittedly", "ADV", None, "Das Wetter war schön, allerdings sehr windig.", "duolingo", "Duolingo"),
    ("sich erholen", "to recover", "VERB", None, "Die Wirtschaft erholt sich nur langsam.", "news", "DW Nachrichten"),
    ("die Umfrage", "survey, poll", "NOUN", "f", "Laut einer Umfrage ist die Mehrheit dafür.", "news", "Tagesschau"),
    ("vorschlagen", "to propose", "VERB", None, "Sie schlägt vor, das Treffen zu verschieben.", "podcast", "Easy German"),
    ("die Einrichtung", "institution; furnishing", "NOUN", "f", "Die Einrichtung wurde 1950 gegründet.", "pdf", "Tschick"),
    ("zunehmend", "increasingly", "ADV", None, "Das Thema wird zunehmend wichtiger.", "youtube", "Easy German"),
    ("die Voraussetzung", "prerequisite", "NOUN", "f", "Gute Deutschkenntnisse sind eine Voraussetzung.", "news", "DW Nachrichten"),
    ("auf etwas verzichten", "to do without something", "EXPR", None, "Viele verzichten inzwischen auf das Auto.", "podcast", "Deutsch – warum nicht?"),
    ("der Zeitraum", "period of time", "NOUN", "m", "In diesem Zeitraum stiegen die Preise stark.", "news", "Tagesschau"),
    ("beeinflussen", "to influence", "VERB", None, "Das Wetter beeinflusst unsere Stimmung.", "duolingo", "Duolingo"),
    ("der Anspruch", "claim; entitlement", "NOUN", "m", "Sie hat Anspruch auf Urlaub.", "pdf", "Goethe B1 Übungsbuch"),
    ("es geht um", "it's about", "EXPR", None, "Es geht um die Zukunft der Energieversorgung.", "youtube", "DW Deutsch lernen"),
    ("die Maßnahme", "measure (policy)", "NOUN", "f", "Die neuen Maßnahmen gelten ab Montag.", "news", "DW Nachrichten"),
    ("umsetzen", "to implement", "VERB", None, "Die Stadt setzt den Plan bis 2030 um.", "news", "SRF News"),
    ("gleichzeitig", "at the same time", "ADV", None, "Ich kann nicht gleichzeitig lesen und hören.", "duolingo", "Duolingo"),
]
FRENCH = [
    ("en revanche", "on the other hand", "EXPR", None, "Le film est long ; en revanche, il est passionnant.", "news", "Le Monde"),
    ("avoir beau", "however much one ...", "EXPR", None, "J'ai beau chercher, je ne trouve pas mes clés.", "podcast", "InnerFrench"),
    ("la grève", "strike", "NOUN", "f", "La grève des transports continue ce lundi.", "news", "Le Monde"),
    ("s'attendre à", "to expect", "VERB", None, "On ne s'attendait pas à une telle hausse.", "news", "RFI"),
    ("le bilan", "assessment; toll", "NOUN", "m", "Le bilan de l'année est plutôt positif.", "news", "Le Monde"),
    ("davantage", "more", "ADV", None, "Il faudrait investir davantage dans l'éducation.", "youtube", "HugoDécrypte"),
    ("mettre en œuvre", "to implement", "EXPR", None, "Le gouvernement veut mettre en œuvre la réforme.", "news", "RFI"),
    ("l'enjeu", "stake, issue", "NOUN", "m", "L'enjeu climatique est au cœur du débat.", "news", "Le Monde"),
    ("quand même", "still, anyway", "EXPR", None, "Il pleuvait, mais on est sortis quand même.", "podcast", "InnerFrench"),
    ("susciter", "to provoke, arouse", "VERB", None, "La décision a suscité de vives critiques.", "news", "Le Temps"),
    ("la hausse", "increase", "NOUN", "f", "La hausse des prix inquiète les ménages.", "news", "Le Temps"),
    ("il s'agit de", "it's a matter of", "EXPR", None, "Il s'agit de trouver un compromis.", "pdf", "L'Étranger"),
    ("désormais", "from now on", "ADV", None, "Les billets sont désormais plus chers.", "news", "RFI"),
    ("le chantier", "construction site; big project", "NOUN", "m", "Le chantier durera deux ans.", "youtube", "HugoDécrypte"),
]


def main(path: str = "data/demo.db", weeks: int = 12, seed: int = 7):
    Path(path).unlink(missing_ok=True)
    conn = db.connect(path)
    rng = random.Random(seed)
    today = date.today()
    start = today - timedelta(weeks=weeks)

    for lang, rows in (("de", GERMAN), ("fr", FRENCH)):
        # add synthetic filler so charts have some body
        filler = [(f"{'Wort' if lang == 'de' else 'mot'}_{i:03d}", "", "NOUN", None, "", rng.choice(db.SOURCE_TYPES[:6]), "")
                  for i in range(160 if lang == "de" else 110)]
        for lemma, gloss, pos, gender, sent, src, title in rows + filler:
            first = start + timedelta(days=int(rng.triangular(0, weeks * 7, weeks * 7 * 0.7)))
            kind = "expression" if pos == "EXPR" else "word"
            surface = lemma.split()[-1] if lang == "de" and pos == "NOUN" else lemma
            lid, _ = db.add_encounter(conn, lang, lemma, sentence=sent, surface=surface,
                                      source_type=src, source_title=title, seen_at=first.isoformat(),
                                      gloss=gloss, pos=pos, gender=gender, kind=kind)
            conn.execute("UPDATE cards SET due=? WHERE lexeme_id=?", (first.isoformat(), lid))
            for _ in range(rng.choice([0, 0, 1, 1, 2, 3])):  # later re-encounters
                again = first + timedelta(days=rng.randint(1, 30))
                if again <= today:
                    db.add_encounter(conn, lang, lemma, sentence=sent, surface=surface,
                                     source_type=rng.choice(db.SOURCE_TYPES[:6]),
                                     source_title=title, seen_at=again.isoformat())
            # simulate reviews
            day = first
            while True:
                row = conn.execute("SELECT due FROM cards WHERE lexeme_id=?", (lid,)).fetchone()
                day = max(day, date.fromisoformat(row["due"]))
                if day >= today:
                    break
                rating = rng.choices([1, 2, 3, 4], weights=[12, 18, 55, 15])[0]
                db.record_review(conn, lid, rating, today=day)

    db.add_goal(conn, "de", "Goethe B1 exam", 400, (today + timedelta(days=75)).isoformat(),
                start.isoformat())
    db.add_goal(conn, "fr", "Read Le Monde without a dictionary", 300,
                (today + timedelta(days=150)).isoformat(), start.isoformat())
    n = conn.execute("SELECT COUNT(*) FROM lexemes").fetchone()[0]
    e = conn.execute("SELECT COUNT(*) FROM encounters").fetchone()[0]
    print(f"Demo database written to {path}: {n} entries, {e} encounters.")


if __name__ == "__main__":
    main(*sys.argv[1:2])

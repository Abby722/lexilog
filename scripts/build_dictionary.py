"""Build the offline dictionary for one language from a kaikki.org download.

1. Go to https://kaikki.org/dictionary/ and open "German" (or "French").
2. Download the JSONL file with all word senses (large; a .gz file works too).
3. Run, from the project folder:
       python scripts/build_dictionary.py de path/to/the-german-file.jsonl
       python scripts/build_dictionary.py fr path/to/the-french-file.jsonl

This writes data/dictionary_de.sqlite (or _fr). You can delete the download afterwards.
"""
import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lexilog import dictionary  # noqa: E402


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("de", "fr"):
        print(__doc__)
        sys.exit(1)
    lang, src = sys.argv[1], Path(sys.argv[2])
    opener = gzip.open if src.suffix == ".gz" else open
    out = dictionary.path_for(lang)
    print(f"Reading {src.name}. A full download takes a few minutes.")
    with opener(src, "rt", encoding="utf-8") as f:
        n = dictionary.build(f, out)
    print(f"Wrote {n:,} entries to {out}")


if __name__ == "__main__":
    main()

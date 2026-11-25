"""Point the semantic model's data folder at this clone.

    python scripts/set_data_folder.py

The model reads its CSVs through one M parameter, Parameter_DataFolder, and that
parameter has to hold an absolute path: Power Query has no notion of a location
relative to the project. So the one value in the whole model that cannot be
made portable is this one, and a clone anywhere other than where it was authored
fails to refresh.

This script rewrites it to wherever the repository actually is. Run it after
cloning, and again if you ever move the folder. It is idempotent - running it
when the path is already correct changes nothing and says so.

Nothing else in the model depends on where the repository lives.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMDL = os.path.join(ROOT, "powerbi", "Ultimate F1 Dashboard.SemanticModel",
                    "definition", "expressions.tmdl")
DATA = os.path.join(ROOT, "powerbi", "data")

PATTERN = re.compile(r'(expression\s+Parameter_DataFolder\s*=\s*)"([^"]*)"')


def main():
    if not os.path.isfile(TMDL):
        # Chapters 01 to 03 have no semantic model yet, which is not an error.
        print("no semantic model yet - nothing to set")
        print("  (expected from chapter 04 onward: %s)" % TMDL)
        return 0

    text = io.open(TMDL, encoding="utf-8").read()
    m = PATTERN.search(text)
    if not m:
        sys.exit("Parameter_DataFolder not found in %s\n"
                 "The model has been restructured; set the CSV folder by hand."
                 % TMDL)

    current = m.group(2)
    wanted = DATA.replace("/", "\\")

    if current == wanted:
        print("already correct: %s" % wanted)
        return 0

    if not os.path.isdir(DATA):
        sys.exit("no CSVs at %s - run export_csv.py first" % DATA)

    text = text[:m.start()] + m.group(1) + '"' + wanted + '"' + text[m.end():]
    io.open(TMDL, "w", encoding="utf-8", newline="\n").write(text)

    print("Parameter_DataFolder updated")
    print("  was: %s" % current)
    print("  now: %s" % wanted)
    print("\nRefresh in Power BI Desktop to pick it up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

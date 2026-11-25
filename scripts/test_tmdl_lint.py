"""Self-test for tmdl_lint.py.

Same contract as test_pbir_lint.py: copy a real model, inject one convention
breach at a time, assert the right rule fires - and assert the unmodified model
stays clean. The second half is what stops the rules drifting into false
positives, which they did twice while this was being written.

    python test_tmdl_lint.py "C:\\path\\to\\Project.pbip"
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LINT = os.path.join(HERE, "tmdl_lint.py")


def run(project):
    out = subprocess.run([sys.executable, LINT, project, "--json"],
                         capture_output=True, text=True)
    try:
        return json.loads(out.stdout)
    except ValueError:
        print(out.stdout, out.stderr)
        raise


def model_dir(project):
    for d in os.listdir(project):
        if d.endswith(".SemanticModel"):
            return os.path.join(project, d, "definition")
    raise SystemExit("no SemanticModel folder")


def tbl(project, name):
    return os.path.join(model_dir(project), "tables", name + ".tmdl")


def edit(path, fn):
    s = io.open(path, encoding="utf-8").read()
    s2 = fn(s)
    assert s2 != s, "mutation did not change %s" % os.path.basename(path)
    io.open(path, "w", encoding="utf-8", newline="\n").write(s2)


CASES = []


def case(name, rule):
    def deco(fn):
        CASES.append((name, rule, fn))
        return fn
    return deco


@case("role prefix on a table name", "table.roleprefix")
def _(p):
    src = tbl(p, "Driver")
    edit(src, lambda s: s.replace("table Driver", "table Dim_Driver", 1))


@case("a measure on a dimension table", "dim.hasmeasures")
def _(p):
    edit(tbl(p, "Driver"), lambda s: s.replace(
        "\tcolumn 'Driver Key'",
        "\tmeasure 'Stray (#)' = COUNTROWS('Driver')\n"
        "\t\tdisplayFolder: 01 Base Measures\n\n\tcolumn 'Driver Key'", 1))


@case("a visible physical column on a fact", "fact.visiblecolumns")
def _(p):
    src = tbl(p, "Session Result")
    def m(s):
        i = s.index("\tcolumn Points")
        j = s.index("isHidden", i)
        return s[:j] + "summarizeBy: sum" + s[j + len("isHidden"):]
    edit(src, m)


@case("both formatString and formatStringDefinition", "measure.twoformats")
def _(p):
    edit(tbl(p, "Session Result"), lambda s: s.replace(
        "\t\tformatString: #,##0.##",
        "\t\tformatString: #,##0.##\n\t\tformatStringDefinition = \"0\"", 1))


@case("a VAR sharing a name with a column", "measure.varcollision")
def _(p):
    edit(tbl(p, "Session Result"), lambda s: s.replace(
        "measure 'Points (pts)' = SUM('Session Result'[Points])",
        "measure 'Points (pts)' =\n\t\t\tVAR Status = 1\n\t\t\tRETURN SUM('Session Result'[Points])", 1))


@case("a measure with no unit of measure", "measure.nouom")
def _(p):
    edit(tbl(p, "Session Result"), lambda s: s.replace(
        "measure 'Points (pts)'", "measure 'Points'", 1))


@case("a Total prefix", "measure.total")
def _(p):
    edit(tbl(p, "Session Result"), lambda s: s.replace(
        "measure 'Points (pts)'", "measure 'Total Points (pts)'", 1))


@case("a display folder with no sort prefix", "folder.noprefix")
def _(p):
    edit(tbl(p, "Session Result"), lambda s: s.replace(
        "displayFolder: 01 Base Measures", "displayFolder: Base Measures", 1))


@case("a variance measure in the wrong folder", "folder.mismatch")
def _(p):
    edit(tbl(p, "Session Result"), lambda s: s.replace(
        "displayFolder: 05 Variances", "displayFolder: 01 Base Measures", 1))


@case("a date table not marked as one", "table.notmarkeddate")
def _(p):
    edit(tbl(p, "Calendar"), lambda s: s.replace("\tdataCategory: Time\n", "", 1))


@case("a visible surrogate key", "column.keyvisible")
def _(p):
    src = tbl(p, "Driver")
    def m(s):
        i = s.index("column 'Driver Key'")
        j = s.index("isHidden", i)
        return s[:j] + "summarizeBy: none" + s[j + len("isHidden"):]
    edit(src, m)


@case("a property changed through the Desktop UI", "model.changedinui")
def _(p):
    marker = "\n\n\t\tchangedProperty = IsHidden"
    edit(tbl(p, "Team"), lambda s: s.replace(
        "\t\tsourceColumn: Team Colour",
        "\t\tsourceColumn: Team Colour" + marker, 1))


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if not src or not os.path.exists(src):
        print("usage: test_tmdl_lint.py <path to .pbip>")
        return 2
    if not src.lower().endswith(".pbip") or not os.path.isfile(src):
        # Without this, a folder argument is accepted and dirname() then
        # resolves to the folder's PARENT, which gets copied once per mutation.
        # Passing "." copied every repository on the machine, thirteen times,
        # in silence. Fail on the argument instead.
        print("usage: %s <path to the .pbip FILE>" % os.path.basename(__file__))
        print("  got: %s" % src)
        return 2
    src_dir = os.path.dirname(os.path.abspath(src))

    tmp = tempfile.mkdtemp(prefix="tmdllint-")
    base = os.path.join(tmp, "proj")
    shutil.copytree(src_dir, base, ignore=shutil.ignore_patterns(".pbi", "data"))

    clean = run(base)
    if not clean["tables"]:
        # Nothing to break, so nothing to test. Saying "OK" here is the same
        # false green tmdl_lint itself stopped giving on an empty model (F45),
        # and the first case then crashed on a file that was not there (run 6,
        # F66). Refuse instead, and say when the suite can run.
        print("baseline: 0 tables - there is no model to test yet.")
        print("This suite breaks a copy of a BUILT model. Run it once chapter 1.5")
        print("has built yours. Not a pass.")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    n_err = sum(1 for f in clean["findings"] if f["level"] == "ERROR")
    n_warn = sum(1 for f in clean["findings"] if f["level"] == "WARN")
    print("baseline (unmodified): %d tables, %d errors, %d warnings  %s"
          % (clean["tables"], n_err, n_warn,
             "OK" if not clean["findings"] else "*** FALSE POSITIVES ***"))
    for f in clean["findings"][:6]:
        print("   ", f["level"], f["rule"], f["where"])

    print()
    passed = failed = 0
    for name, rule, mutate in CASES:
        work = os.path.join(tmp, "case")
        if os.path.isdir(work):
            shutil.rmtree(work)
        shutil.copytree(base, work)
        try:
            mutate(work)
        except (AssertionError, ValueError, OSError) as exc:
            # Each case injects its fault at an anchor taken from the reference
            # model. A model built differently may not have that shape: a table
            # named otherwise, a file that is not there. That is not a miss,
            # and it must not be a traceback (run 6, F66). The case does not
            # apply to this model.
            print("  %-46s SKIP (not in your model: %s)" % (name, exc))
            continue
        found = {f["rule"] for f in run(work)["findings"]}
        ok = rule in found
        passed += ok
        failed += not ok
        print("  %-46s %s" % (name, "caught" if ok else "MISSED (%s)" % rule))

    shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d caught, %d missed, baseline %s"
          % (passed, failed, "clean" if not clean["findings"] else "DIRTY"))
    return 0 if (failed == 0 and not clean["findings"]) else 1


if __name__ == "__main__":
    sys.exit(main())

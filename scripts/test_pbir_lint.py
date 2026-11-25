"""Self-test for pbir_lint.py.

Copies a real PBIP project to a temp folder, injects each mistake that actually
cost time on a build, and asserts the linter catches it. Also asserts the
unmodified project stays clean, which is what stops the rules drifting into
false positives - an earlier version flagged three working visuals.

    python test_pbir_lint.py "C:\\path\\to\\Project.pbip"
"""
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LINT = os.path.join(HERE, "pbir_lint.py")


def run(project):
    out = subprocess.run([sys.executable, LINT, project, "--json"],
                         capture_output=True, text=True)
    try:
        return json.loads(out.stdout)
    except ValueError:
        print(out.stdout, out.stderr)
        raise


def visuals_of(project, pred):
    root = None
    for d in os.listdir(project):
        if d.endswith(".Report"):
            root = os.path.join(project, d, "definition", "pages")
    hits = []
    for base, _d, files in os.walk(root):
        for f in files:
            if f != "visual.json":
                continue
            p = os.path.join(base, f)
            d = json.load(io.open(p, encoding="utf-8"))
            if pred(d):
                hits.append((p, d))
    return hits


def write(p, d):
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        json.dumps(d, indent=2, ensure_ascii=False) + "\n")
Q = chr(39)
DQ = chr(34)
NL = chr(10)
IND = chr(9) * 3



CASES = []


def case(name, rule, pred=None):
    def deco(fn):
        CASES.append((name, rule, pred or (lambda d: "query" in (d.get("visual") or {})), fn))
        return fn
    return deco


@case("field well named Categories", "well.categories")
def _(d):
    qs = d["visual"]["query"]["queryState"]
    qs["Categories"] = qs.pop(list(qs)[0])


@case("columnHeaders.show on a table", "prop.invalid",
      lambda d: (d.get("visual") or {}).get("visualType") == "tableEx")
def _(d):
    d["visual"].setdefault("objects", {})["columnHeaders"] = [
        {"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]


@case("total.show instead of total.totals", "prop.invalid",
      lambda d: (d.get("visual") or {}).get("visualType") == "tableEx")
def _(d):
    d["visual"].setdefault("objects", {})["total"] = [
        {"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]


@case("imageHeight under values", "prop.imagesize")
def _(d):
    d["visual"].setdefault("objects", {})["values"] = [
        {"properties": {"imageHeight": {"expr": {"Literal": {"Value": "84D"}}}}}]


@case("invented maxTiles", "prop.invented")
def _(d):
    d["visual"].setdefault("objects", {})["layout"] = [
        {"properties": {"maxTiles": {"expr": {"Literal": {"Value": "24L"}}}}}]


@case("label.show without a selector", "selector.label")
def _(d):
    d["visual"].setdefault("objects", {})["label"] = [
        {"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]


@case("value.show WITH a selector", "selector.value")
def _(d):
    d["visual"].setdefault("objects", {})["value"] = [
        {"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}},
         "selector": {"id": "default"}}]


@case("image bound to a measure, no wildcard selector", "selector.wildcard")
def _(d):
    d["visual"].setdefault("objects", {})["image"] = [
        {"properties": {"image": {"expr": {"Measure": {
            "Expression": {"SourceRef": {"Entity": "Session Result"}},
            "Property": "Race Card (svg)"}}}},
         "selector": {"id": "default"}}]


@case("sorts by something the visual does not query", "sort.notqueried")
def _(d):
    d["visual"]["query"]["sortDefinition"] = {
        "sort": [{"field": {"Measure": {
            "Expression": {"SourceRef": {"Entity": "Session Result"}},
            "Property": "Points (pts)"}}, "direction": "Ascending"}],
        "isDefaultSort": True}


@case("references a measure that does not exist", "ref.object")
def _(d):
    qs = d["visual"]["query"]["queryState"]
    first = qs[list(qs)[0]]["projections"][0]
    first["field"] = {"Measure": {
        "Expression": {"SourceRef": {"Entity": "Session Result"}},
        "Property": "Ghost Measure"}}


@case("references a table that does not exist", "ref.table")
def _(d):
    qs = d["visual"]["query"]["queryState"]
    first = qs[list(qs)[0]]["projections"][0]
    first["field"] = {"Column": {
        "Expression": {"SourceRef": {"Entity": "Nope"}}, "Property": "X"}}


@case("malformed JSON", "json.invalid")
def _(d):
    d["__break__"] = True   # handled specially below


# --- layer 4: appearance --------------------------------------------------
# Three of these are visual-level and use the same harness. The other two
# change a page.json or pages.json, which no visual mutation can reach, so they
# get their own list below and a mutation that takes the whole project.

@case("a colour that is not in the palette", "theme.palette",
      lambda d: "#" in json.dumps(d))
def _(d):
    blob = json.dumps(d)
    start = blob.index("#")
    write_back = blob[:start] + "#FF5733" + blob[start + 7:]
    d.clear()
    d.update(json.loads(write_back))


@case("visual straddling the sidebar edge", "layout.rail",
      lambda d: "position" in d)
def _(d):
    d["position"].update({"x": 100, "width": 400})


@case("visual running off the canvas", "layout.offcanvas",
      lambda d: "position" in d)
def _(d):
    d["position"].update({"x": 1800, "width": 400})


PROJECT_CASES = []


def pcase(name, rule, hint=None):
    """hint, when given, must appear in that rule's fix hint. The hint is what
    the participant acts on, and it once shipped with words missing (F89)."""
    def deco(fn):
        PROJECT_CASES.append((name, rule, hint, fn))
        return fn
    return deco


def pages_dir(project):
    for d in os.listdir(project):
        if d.endswith(".Report"):
            return os.path.join(project, d, "definition", "pages")
    return None


def load(p):
    return json.load(io.open(p, encoding="utf-8"))


@pcase("a page on a different canvas size", "page.canvas")
def _(project):
    root = pages_dir(project)
    page = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))[0]
    p = os.path.join(root, page, "page.json")
    d = load(p)
    d["width"], d["height"] = 1280, 720
    write(p, d)


@pcase("a page with no navigation", "page.nav")
def _(project):
    root = pages_dir(project)
    page = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))[0]
    for base, _dirs, files in os.walk(os.path.join(root, page)):
        for f in files:
            if f != "visual.json":
                continue
            p = os.path.join(base, f)
            d = load(p)
            (d.get("visual") or {}).pop("visualContainerObjects", None)
            write(p, d)


@pcase("a card sized to the wrong aspect for its tile", "card.aspect",
       hint="The card still renders, so nothing else will tell you. Set the "
            "SVG's width and height to the tile, or change the grid's "
            "columnCount / rowCount to suit the card.")
def _(project):
    """The finding that prompted the rule: the card renders, keeps its border,
    headings and labels, and silently loses the band the crop takes. 408x153 in
    a 417x163 tile is 4% off and fine; 260x150 in the same tile is 48% off and
    loses the bottom row of values."""
    model = None
    for d in os.listdir(project):
        if d.endswith(".SemanticModel"):
            model = os.path.join(d, "definition", "tables")
    p = os.path.join(project, model, "Session Result.tmdl")
    t = io.open(p, encoding="utf-8").read()
    old = "width='408' height='153'"
    if old not in t:
        raise AssertionError("card size anchor not found")
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        t.replace(old, "width='260' height='150'", 1))


@pcase("a card sized wrongly via DAX variables", "card.aspect")
def _(project):
    """The literal case above is the easy one. A card that builds its size
    from variables defeated the rule twice: first the pattern missed the
    quoting TMDL actually uses, then the substitution swallowed the quotes
    the size regex needs. Both times the run reported clean. This is the
    case that said otherwise."""
    model = None
    for d in os.listdir(project):
        if d.endswith(".SemanticModel"):
            model = os.path.join(d, "definition", "tables")
    p = os.path.join(project, model, "Session Result.tmdl")
    t = io.open(p, encoding="utf-8").read()

    literal = "width=" + Q + "408" + Q + " height=" + Q + "153" + Q
    if literal not in t:
        raise AssertionError("literal card size anchor not found")

    # the same size, expressed the way a participant model actually writes it
    built = ("width=" + Q + DQ + " & CardW & " + DQ + Q
             + " height=" + Q + DQ + " & CardH & " + DQ + Q)
    t = t.replace(literal, built, 1)

    # 260 wide against a 417 tile: 38% off, past the error threshold
    anchor = IND + "VAR CodeNow = SELECTEDVALUE(" + Q + "Driver" + Q + "[Driver Code])"
    if anchor not in t:
        raise AssertionError("VAR anchor not found in the card measure")
    t = t.replace(anchor,
                  IND + "VAR CardW = 260" + NL
                  + IND + "VAR CardH = 162.67" + NL + anchor, 1)
    io.open(p, "w", encoding="utf-8", newline=NL).write(t)

@pcase("a page missing from pageOrder", "pages.order")
def _(project):
    p = os.path.join(pages_dir(project), "pages.json")
    d = load(p)
    d["pageOrder"] = d["pageOrder"][:-1]
    write(p, d)


@pcase("an off-palette colour written into a measure", "theme.palette")
def _(project):
    """theme.palette used to read visual.json and page.json only. But a card
    paints itself from DAX, so every appearance decision a participant makes
    lives in a measure - and none of it was checked. The reference's own four
    status colours sat outside the rule too, which meant the material passed
    the check while breaking it.

    This swaps one documented status colour for an undocumented green. A
    second green that disagrees with the first is exactly what the closed list
    exists to prevent, and it is invisible in a diff."""
    model = None
    for d in os.listdir(project):
        if d.endswith(".SemanticModel"):
            model = os.path.join(d, "definition", "tables")
    p = os.path.join(project, model, "Session Result.tmdl")
    t = io.open(p, encoding="utf-8").read()
    for token in ("#229971", "#FF8000", "#6B7280"):
        if token in t:
            io.open(p, "w", encoding="utf-8", newline=chr(10)).write(
                t.replace(token, "#2ECC71", 1))
            return
    raise AssertionError("no status colour found to replace")


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if not src or not os.path.exists(src):
        print("usage: test_pbir_lint.py <path to .pbip>")
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

    tmp = tempfile.mkdtemp(prefix="pbirlint-")
    base = os.path.join(tmp, "proj")
    shutil.copytree(src_dir, base, ignore=shutil.ignore_patterns(".pbi", "data"))

    clean = run(base)
    if not clean["visuals"]:
        # Nothing to break, so nothing to test: refuse rather than call an
        # empty report OK (the same false green as F66 in test_tmdl_lint).
        print("baseline: 0 visuals - there is no report to test yet.")
        print("This suite breaks a copy of a BUILT report. Run it once chapter 1.6")
        print("has built yours. Not a pass.")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1
    n_err = sum(1 for f in clean["findings"] if f["level"] == "ERROR")
    print("baseline (unmodified): %d visuals, %d errors  %s"
          % (clean["visuals"], n_err, "OK" if n_err == 0 else "*** FALSE POSITIVES ***"))
    if n_err:
        for f in clean["findings"][:5]:
            print("   ", f["level"], f["rule"], f["where"])

    print()
    passed = failed = 0
    for name, rule, pred, mutate in CASES:
        work = os.path.join(tmp, "case")
        if os.path.isdir(work):
            shutil.rmtree(work)
        shutil.copytree(base, work)
        targets = visuals_of(work, pred)
        if not targets:
            print("  %-46s SKIP (no matching visual)" % name)
            continue
        p, d = targets[0]
        d = copy.deepcopy(d)
        mutate(d)
        if d.pop("__break__", None):
            io.open(p, "w", encoding="utf-8").write('{"broken": ')
        else:
            write(p, d)
        found = {f["rule"] for f in run(work)["findings"]}
        ok = rule in found
        passed += ok
        failed += not ok
        print("  %-46s %s" % (name, "caught" if ok else "MISSED (%s)" % rule))

    for name, rule, hint, mutate in PROJECT_CASES:
        work = os.path.join(tmp, "case")
        if os.path.isdir(work):
            shutil.rmtree(work)
        shutil.copytree(base, work)
        try:
            mutate(work)
        except (AssertionError, ValueError, OSError) as exc:
            # The anchor comes from the reference model; a model built
            # differently may not have it. Not a miss, and not a traceback.
            print("  %-46s SKIP (not in your model: %s)" % (name, exc))
            continue
        hits = [f for f in run(work)["findings"] if f["rule"] == rule]
        ok = bool(hits)
        if ok and hint and not any(hint in (f.get("hint") or "") for f in hits):
            print("  %-46s HINT WRONG (%s): %r" % (name, rule, hits[0].get("hint")))
            failed += 1
            continue
        passed += ok
        failed += not ok
        print("  %-46s %s" % (name, "caught" if ok else "MISSED (%s)" % rule))

    shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d caught, %d missed, baseline %s"
          % (passed, failed, "clean" if n_err == 0 else "DIRTY"))
    return 0 if (failed == 0 and n_err == 0) else 1


if __name__ == "__main__":
    sys.exit(main())

"""Check a TMDL semantic model against the in2Facts conventions, offline.

The companion to pbir_lint.py. That one checks the report; this one checks the
model - naming, display folders, measure placement, column visibility - plus the
handful of TMDL mistakes that stop Desktop opening the project at all.

    python tmdl_lint.py "C:\\path\\to\\Project.pbip"
    python tmdl_lint.py .              # searches down for a .pbip
    python tmdl_lint.py . --json

Exit code is 1 if any ERROR was found. WARN never fails the run: a convention is
a default, and a model may have a good reason to depart from one.

What it will NOT tell you: whether the DAX is correct, or whether the numbers
are right. Use pbi-cli against a live model for that. This is the pass that
needs neither Desktop nor a refresh.

Conventions implemented here come from the three in2Facts skills:
power-bi-table-naming-convention, power-bi-measure-naming-convention and
power-bi-folder-naming-convention. Where this disagrees with them, they win -
they are the specification and this is only a reading of it.
"""
import argparse
import io
import json
import os
import re
import sys

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"

# Tables Power BI Desktop generates itself when Auto date/time is on: one
# hidden calculated date table per date column, plus a template. They are not
# the modeller's to fix, so they get their own rule and their own advice
# rather than eight copies of "prefer Power Query".
AUTO_DATE_RE = re.compile(r"^(LocalDateTable_|DateTableTemplate_)")

# Table names that are also DAX function names. Referenced unquoted, the parser has
# to decide between a table and a function call, and Date[Date] is the one that
# actually turns up: nearly every model has a Date table and DATE() is a function.
# Only names that really are DAX functions are listed - a false positive here would
# teach people to ignore the rule.
DAX_FUNCTION_NAMES = {
    "date", "calendar", "calendarauto", "time", "value", "filter", "format",
    "search", "union", "distinct", "rank", "row", "year", "month", "day", "hour",
    "minute", "second", "now", "today", "all", "min", "max", "sum", "count",
    "average", "median", "not", "order", "quarter", "weekday", "path", "lookupvalue",
}


class Finding(object):
    def __init__(self, level, rule, where, message, hint=None):
        self.level, self.rule, self.where = level, rule, where
        self.message, self.hint = message, hint

    def as_dict(self):
        return {"level": self.level, "rule": self.rule, "where": self.where,
                "message": self.message, "hint": self.hint}


# --------------------------------------------------------------------------
# TMDL reader
# --------------------------------------------------------------------------
# Deliberately self-contained rather than shared with pbir_lint.py, so either
# script can be copied out of this folder and still run.

OBJ_RE = re.compile(r"^\t(measure|column|hierarchy|partition)\s+('([^']+)'|[^\s=]+)\s*(=)?")
TABLE_RE = re.compile(r"^table\s+('([^']+)'|\S+)", re.M)
PROP_RE = re.compile(r"^\t\t([A-Za-z]+):\s*(.*)$")
FLAG_RE = re.compile(r"^\t\t([A-Za-z]+)\s*$")
TPROP_RE = re.compile(r"^\t([A-Za-z]+):\s*(.*)$")
TFLAG_RE = re.compile(r"^\t([A-Za-z]+)\s*$")
# Desktop records a property it changed through the UI as "changedProperty = X",
# with an equals sign rather than a colon, so the property regexes miss it.
CHANGED_RE = re.compile(r"^\t+changedProperty\s*=\s*(\S+)")
# A calendar object (calendar-based time intelligence, compatibility level 1701
# and up). It is a child of the table, like a column, and its own lines must
# not be read as part of the object above it.
CAL_RE = re.compile(r"^\tcalendar\s+('([^']+)'|\S+)")


def parse_table(text, fn):
    m = TABLE_RE.search(text)
    if not m:
        return None
    tbl = {"name": m.group(2) or m.group(1), "file": fn, "hidden": False,
           "dataCategory": None, "columns": [], "measures": [], "hierarchies": [],
           "changed": [],
           "calendars": [c.group(2) or c.group(1)
                         for c in map(CAL_RE.match, text.split("\n")) if c],
           # A DAX calculated table rather than a Power Query one. Kept as a
           # flag here because the rule below needs it and nothing else does.
           "calculated": "= calculated" in text}
    lines = text.split("\n")

    # table-level properties sit at one tab, before the first object
    for line in lines:
        if OBJ_RE.match(line):
            break
        p = TPROP_RE.match(line)
        if p and p.group(1) == "dataCategory":
            tbl["dataCategory"] = p.group(2).strip()
        f = TFLAG_RE.match(line)
        if f and f.group(1) == "isHidden":
            tbl["hidden"] = True
        ch = CHANGED_RE.match(line)
        if ch:
            tbl["changed"].append(ch.group(1))

    i = 0
    while i < len(lines):
        hit = OBJ_RE.match(lines[i])
        if not hit:
            i += 1
            continue
        kind = hit.group(1)
        name = hit.group(3) or hit.group(2)
        obj = {"name": name, "hidden": False, "dataType": None, "dataCategory": None,
               "displayFolder": None, "formatString": None,
               "formatStringDefinition": False, "expression": [], "line": i + 1,
               "changed": []}

        # everything on the declaration line after '=' starts the expression
        rest = lines[i].split("=", 1)
        if len(rest) > 1 and rest[1].strip():
            obj["expression"].append(rest[1].strip())

        j = i + 1
        while j < len(lines):
            ln = lines[j]
            if OBJ_RE.match(ln) or CAL_RE.match(ln) or \
                    (ln and not ln.startswith("\t")):
                break
            p = PROP_RE.match(ln)
            f = FLAG_RE.match(ln)
            ch = CHANGED_RE.match(ln)
            if ch:
                obj["changed"].append(ch.group(1))
            elif p:
                k, v = p.group(1), p.group(2).strip()
                if k in ("dataType", "dataCategory", "displayFolder", "formatString"):
                    obj[k] = v
                elif k == "formatStringDefinition":
                    obj["formatStringDefinition"] = True
            elif f and f.group(1) == "isHidden":
                obj["hidden"] = True
            elif ln.startswith("\t\t\t") or ln.startswith("\t\t\t\t"):
                obj["expression"].append(ln.strip())
            elif ln.strip().startswith("formatStringDefinition"):
                obj["formatStringDefinition"] = True
            j += 1

        obj["expression"] = "\n".join(obj["expression"])
        if kind == "measure":
            tbl["measures"].append(obj)
        elif kind == "column":
            tbl["columns"].append(obj)
        elif kind == "hierarchy":
            tbl["hierarchies"].append(obj)
        i = j
    return tbl


def read_model(model_dir):
    model = {"tables": {}, "relationships": []}
    defn = os.path.join(model_dir, "definition")
    tdir = os.path.join(defn, "tables")
    if os.path.isdir(tdir):
        for fn in sorted(os.listdir(tdir)):
            if not fn.endswith(".tmdl"):
                continue
            t = parse_table(io.open(os.path.join(tdir, fn), encoding="utf-8").read(), fn)
            if t:
                model["tables"][t["name"]] = t
    rp = os.path.join(defn, "relationships.tmdl")
    if os.path.isfile(rp):
        text = io.open(rp, encoding="utf-8").read()
        for blk in re.split(r"\nrelationship\s+", text):
            fm = re.search(r"fromColumn:\s*('([^']+)'|[^.\s]+)\.('([^']+)'|\S+)", blk)
            to = re.search(r"toColumn:\s*('([^']+)'|[^.\s]+)\.('([^']+)'|\S+)", blk)
            if fm and to:
                model["relationships"].append({
                    "fromTable": fm.group(2) or fm.group(1),
                    "toTable": to.group(2) or to.group(1)})
    return model


def roles(model):
    """A fact sits on the many side and never on the one side.

    Being on the many side is NOT sufficient: a snowflaked dimension is on the
    many side of its own parent. Race points at Calendar and is pointed at by
    two facts - it is a dimension, and an earlier version of this rule called it
    a fact and reported thirteen imaginary problems."""
    many = {r["fromTable"] for r in model["relationships"]}
    one = {r["toTable"] for r in model["relationships"]}
    out = {}
    for name in model["tables"]:
        if name in one:
            out[name] = "dimension"
        elif name in many:
            out[name] = "fact"
        else:
            out[name] = "disconnected"
    return out


# --------------------------------------------------------------------------
# convention vocabulary
# --------------------------------------------------------------------------

ROLE_PREFIX = re.compile(r"^(dim|fact|bridge|tbl|d|f|fct|dm)[_\s]", re.I)
UOM_RE = re.compile(r"\(([^)]+)\)")
TIME_QUAL = {"mtd", "wtd", "qtd", "ytd", "pm", "pq", "py", "sply"}
ROLLING_RE = re.compile(r"^r\d{2}m$")
SCENARIOS = {"ACT", "BDG", "TGT", "FCST"}
AGGREGATIONS = ("Average", "Median", "Min", "Max", "Distinct", "Rank")
TECHNICAL_UOM = {"hex", "txt", "svg", "html"}
FOLDER_PREFIX = re.compile(r"^\d{2}\s+\S")


def quals(name):
    return [q.strip() for q in UOM_RE.findall(name)]


def expected_folder(name):
    """The folder the naming convention implies, or None where it is ambiguous.
    Only the unambiguous mappings are asserted, and only as a warning."""
    qs = quals(name)
    if " Δ " in name:
        return "05 Variances"
    for q in qs:
        if q in TIME_QUAL or ROLLING_RE.match(q):
            return "03 Time Intelligence"
    if name.startswith("Rank "):
        return "07 Ranks"
    if re.match(r"^(Is|Has)\s", name):
        return "08 Flags"
    if qs and qs[0] in TECHNICAL_UOM:
        return "09 Technical"
    if any(re.search(r"\b%s\b" % s, name) for s in SCENARIOS):
        return "04 Scenarios"
    if name.startswith(AGGREGATIONS):
        return "02 Aggregations"
    return None


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------

def check_model(model, findings):
    role = roles(model)

    # Reported once, with a count. Eight findings that all say the same thing and
    # all name a GUID teach a reader to scroll past warnings.
    auto = sorted(t for t in model["tables"] if AUTO_DATE_RE.match(t))
    if auto:
        findings.append(Finding(
            WARN, "table.autodate", "%d table(s), e.g. %s" % (len(auto), auto[0]),
            "Power BI Desktop generated these, one per date column",
            "these come from Auto date/time, not from your model. Turn it off in "
            "Desktop under File > Options and settings > Options > Current File > "
            "Data Load, untick Auto date/time, and save. The tables and their "
            "relationships go with it."))

    # A table whose name is a DAX function name, referenced without quotes. The
    # expression usually still compiles - which is the problem: it compiles to
    # something else, or to a SYNTAXERROR that names no cause.
    risky = {t for t in model["tables"] if t.lower() in DAX_FUNCTION_NAMES}
    for tname, t in sorted(model["tables"].items()):
        for m in t["measures"]:
            for bad in sorted(risky):
                # 'Date'[Date] is fine: there the bracket follows a quote, not the
                # table name, so this pattern cannot match it.
                if re.search(r"(?<![\w'])%s\[" % re.escape(bad), m["expression"], re.I):
                    findings.append(Finding(
                        WARN, "dax.unquotedtable",
                        "%s[%s]" % (tname, m["name"]),
                        "references %s[...] unquoted, and %s is also a DAX function"
                        % (bad, bad.upper()),
                        "write '%s'[...] - the quotes are what tell the parser it is "
                        "your table and not the function." % bad))

    for tname, t in sorted(model["tables"].items()):
        if AUTO_DATE_RE.match(tname):
            continue          # already reported above, as one finding
        where = "%s (%s)" % (tname, role[tname])

        # ---- calculated tables --------------------------------------------
        # A calculated table whose span depends on another table is EMPTY until
        # the whole model refreshes, so it shows a nonsense range on first open
        # and reads as a modelling error. The reference model shipped a DAX
        # calendar and lessons-learned.md records the afternoon it cost. Build
        # date tables in Power Query instead.
        if t.get("calculated"):
            findings.append(Finding(
                WARN, "table.calculated", where,
                "this is a DAX calculated table",
                "prefer Power Query. A calculated table depending on another "
                "table is empty until the whole model refreshes, which looks "
                "exactly like a broken model on first open."))

        # ---- table naming -------------------------------------------------
        if ROLE_PREFIX.match(tname):
            findings.append(Finding(
                ERROR, "table.roleprefix", where,
                "table name carries a role prefix",
                "name it for its business content; role is visible in Model view."))

        if tname.lower() in ("_measures", "measures", "_measure", "measure table"):
            findings.append(Finding(
                ERROR, "table.measuresonly", where,
                "a table dedicated to holding measures",
                "each fact table hosts its own measures."))

        # ---- date table ----------------------------------------------------
        # Two designs are accepted. Classic time intelligence needs the table
        # marked (dataCategory: Time). Calendar-based time intelligence defines
        # a calendar object on the table instead, and its functions take the
        # calendar, not a date column. Run 6's agent chose the second, and an
        # ERROR here made chapter 1.5's gate unreachable on a sound model (F72).
        if tname.lower() in ("date", "calendar") and t["dataCategory"] != "Time" \
                and not t["calendars"]:
            findings.append(Finding(
                ERROR, "table.notmarkeddate", where,
                "a date table that is neither marked as one (dataCategory: Time) "
                "nor carries a calendar object",
                "classic time intelligence silently misbehaves without the mark. "
                "Mark it as the date table, or define a calendar on it "
                "(calendar-based time intelligence: compatibility level 1701 "
                "and the Desktop preview feature)."))

        # ---- measure placement ---------------------------------------------
        if role[tname] == "dimension" and t["measures"]:
            findings.append(Finding(
                ERROR, "dim.hasmeasures", where,
                "%d measure(s) on a dimension table" % len(t["measures"]),
                "move them to the fact table they describe."))

        # ---- fact hygiene ---------------------------------------------------
        if role[tname] == "fact":
            visible = [c for c in t["columns"] if not c["hidden"]]
            if visible:
                findings.append(Finding(
                    ERROR, "fact.visiblecolumns", where,
                    "%d visible physical column(s): %s"
                    % (len(visible), ", ".join(c["name"] for c in visible[:5])),
                    "users browse measures, not raw fact columns."))
            if not [m for m in t["measures"] if not m["hidden"]]:
                findings.append(Finding(
                    ERROR, "fact.nomeasures", where,
                    "no visible measure, so the table can become unselectable",
                    "add a real measure, or Dummy = BLANK() as a placeholder."))

        # ---- surrogate keys should not be browsable ---------------------------
        # Keyed on the name ending in "Key", which is exact. Whether some other
        # column ought to be hidden is a judgement the model has to make: column
        # names carry no unit of measure, so there is nothing to detect.
        for c in t["columns"]:
            if not c["hidden"] and (c["name"] == "Key" or c["name"].endswith(" Key")):
                findings.append(Finding(
                    WARN, "column.keyvisible", "%s.%s" % (tname, c["name"]),
                    "a surrogate key is visible in the field list",
                    "hide it; nobody should browse or slice by it."))

        # ---- properties changed through Desktop's UI --------------------------
        # Not a fault, and not necessarily wrong: Desktop stamps this when
        # someone changes a property in the UI, and the change is often the
        # correct one. Reported because it is the only trace that a file and the
        # script that generates it have diverged - a UI edit is silently lost the
        # next time the generator runs.
        #
        # Do not read this as "revert it". The first column that motivated this
        # rule had been unhidden on purpose, for self-service, and hiding it
        # again was the mistake.
        for kind, items in (("table", [t]), ("column", t["columns"]),
                            ("measure", t["measures"])):
            for o in items:
                if not o.get("changed"):
                    continue
                who = tname if kind == "table" else "%s.%s" % (tname, o["name"])
                findings.append(Finding(
                    INFO, "model.changedinui", who,
                    "%s edited in the Desktop UI: %s"
                    % (kind, ", ".join(sorted(set(o["changed"])))),
                    "if this model is generated, fold the change into the "
                    "generator or it is lost on the next run."))

        # ---- measures --------------------------------------------------------
        folders = {}
        for m in t["measures"]:
            mw = "%s[%s]" % (tname, m["name"])

            if m["formatString"] and m["formatStringDefinition"]:
                findings.append(Finding(
                    ERROR, "measure.twoformats", mw,
                    "has both formatString and formatStringDefinition",
                    "Desktop refuses to open the whole project, naming this measure."))

            cols = {c["name"].lower() for c in t["columns"]}
            for var in re.findall(r"\bVAR\s+(\w+)", m["expression"]):
                if var.lower() in cols:
                    findings.append(Finding(
                        ERROR, "measure.varcollision", mw,
                        "VAR %s shares a name with a column on this table" % var,
                        "compiles to SYNTAXERROR, and the error does not say why."))

            if m["name"] != "Dummy":
                if not quals(m["name"]):
                    findings.append(Finding(
                        WARN, "measure.nouom", mw,
                        "no unit of measure in the name",
                        "the convention is <Name> (<UoM>), e.g. Revenue (EUR), Customers (#)."))
                if m["name"].startswith("Total "):
                    findings.append(Finding(
                        WARN, "measure.total", mw,
                        "a Total prefix collides with the grand-total label Power BI generates",
                        "drop it, or name the aggregation (Average, Median, Max)."))
                if m["name"].startswith("Rank ") and "pos" not in quals(m["name"]):
                    findings.append(Finding(
                        WARN, "measure.rankuom", mw, "a rank measure without the (pos) unit"))
                if re.match(r"^(Is|Has)\s", m["name"]) and "flag" not in quals(m["name"]):
                    findings.append(Finding(
                        WARN, "measure.flaguom", mw, "a boolean measure without the (flag) unit"))
                for q in quals(m["name"]):
                    if q.lower() in TIME_QUAL and q != q.lower():
                        findings.append(Finding(
                            WARN, "measure.timecase", mw,
                            "time-intelligence qualifier %r should be lower case" % q))
                    if q.upper() in SCENARIOS and q != q.upper():
                        findings.append(Finding(
                            WARN, "measure.scenariocase", mw,
                            "scenario qualifier %r should be upper case" % q))

            df = m["displayFolder"]
            if not df:
                findings.append(Finding(
                    WARN, "folder.missing", mw, "measure is not in a display folder"))
            else:
                parts = df.split("\\")
                if len(parts) > 2:
                    findings.append(Finding(
                        WARN, "folder.deep", mw,
                        "display folder nests %d levels; the convention allows 2" % len(parts)))
                for part in parts:
                    if not FOLDER_PREFIX.match(part):
                        findings.append(Finding(
                            WARN, "folder.noprefix", mw,
                            "folder %r has no two-digit sort prefix" % part,
                            "without it folders sort among the loose measures."))
                        break
                want = expected_folder(m["name"])
                if want and not parts[0].startswith(want.split()[0]):
                    findings.append(Finding(
                        WARN, "folder.mismatch", mw,
                        "name implies %r but the measure sits in %r" % (want, parts[0])))
                folders.setdefault(df, []).append(m["name"])

        for df, members in sorted(folders.items()):
            if "\\" in df and len(members) == 1:
                findings.append(Finding(
                    WARN, "folder.lonely", "%s :: %s" % (tname, df),
                    "subfolder holds a single measure (%s)" % members[0],
                    "fold it back into its parent."))


# --------------------------------------------------------------------------

def find_project(start):
    if start.lower().endswith(".pbip"):
        return os.path.dirname(os.path.abspath(start))
    start = os.path.abspath(start)
    for base, dirs, files in os.walk(start):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".pbi")]
        if any(f.lower().endswith(".pbip") for f in files):
            return base
    return None


def main():
    ap = argparse.ArgumentParser(description="Check a TMDL model against the in2Facts conventions.")
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="errors only")
    args = ap.parse_args()

    project = find_project(args.path)
    if not project:
        print("no .pbip found under %s" % os.path.abspath(args.path))
        return 2

    model_dir = None
    for d in os.listdir(project):
        if d.endswith(".SemanticModel") and os.path.isdir(os.path.join(project, d)):
            model_dir = os.path.join(project, d)
    if not model_dir:
        print("no *.SemanticModel folder beside the .pbip")
        return 2

    model = read_model(model_dir)
    findings = []
    check_model(model, findings)

    if args.json:
        print(json.dumps({"model": os.path.basename(model_dir),
                          "tables": len(model["tables"]),
                          "findings": [f.as_dict() for f in findings]}, indent=2))
        return 1 if any(f.level == ERROR for f in findings) else 0

    role = roles(model)
    n_meas = sum(len(t["measures"]) for t in model["tables"].values())
    print("%s  -  %d tables (%d fact, %d dimension), %d measures"
          % (os.path.basename(model_dir), len(model["tables"]),
             sum(1 for r in role.values() if r == "fact"),
             sum(1 for r in role.values() if r == "dimension"), n_meas))

    # An empty model is not a clean model. The project shell ships from the
    # `start` checkpoint so that nobody has to check one out, which means this can
    # be run against a project with no tables in it at all - and reporting
    # "clean - nothing the conventions object to" on zero tables is a pass that
    # means nothing. Say what is true instead.
    #
    # And say it in the EXIT CODE too. Printing an honest sentence above a
    # "0 error(s)" line fixes the prose and leaves the machine-readable answer
    # saying pass: the chapter states its gate as "tmdl_lint reports 0 error(s)",
    # so an empty model satisfied the chapter's own success criterion BEFORE the
    # chapter began. Run 5 hit exactly that, because the chapter invites running
    # this check "as often as you like - after every prompt, if you want".
    # Non-zero is also what this file already means by "not acceptable"
    # everywhere else, so returning 0 here contradicted its own contract.
    # check_tags.sh only runs this when a tables/ directory exists, so the
    # `start` checkpoint's gates do not depend on the old behaviour.
    if not model["tables"]:
        print("")
        print("no tables in the model yet - nothing to check")
        print("this is not a pass: build the model, then run this again")
        print("")
        print("0 error(s), 0 warning(s) - from 0 tables")
        return 1

    order = {ERROR: 0, WARN: 1, INFO: 2}
    findings.sort(key=lambda f: (order[f.level], f.rule, f.where))
    shown = [f for f in findings if not (args.quiet and f.level != ERROR)]
    if not shown:
        print("\nclean - nothing the conventions object to")
    for f in shown:
        print("\n%-5s %s" % (f.level, f.rule))
        print("      %s" % f.where)
        print("      %s" % f.message)
        if f.hint:
            print("      -> %s" % f.hint)
    print("\n%d error(s), %d warning(s)"
          % (sum(1 for f in findings if f.level == ERROR),
             sum(1 for f in findings if f.level == WARN)))
    return 1 if any(f.level == ERROR for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())

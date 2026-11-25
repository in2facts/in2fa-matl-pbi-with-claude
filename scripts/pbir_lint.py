"""Validate a PBIP project before opening Power BI Desktop.

PBIR fails silently. A wrong property name, a wrong field-well name or a
reference to a measure that no longer exists all produce a blank visual and no
error at all - so every mistake costs a full close-regenerate-reopen-refresh
cycle to discover. This catches them offline, in about a second.

    python pbir_lint.py "C:\\path\\to\\Project.pbip"
    python pbir_lint.py .              # searches down for a .pbip
    python pbir_lint.py . --json       # machine-readable

Exit code is 1 if any ERROR was found, 0 otherwise. WARN never fails the run.

Four layers, cheapest first:

  1. SCHEMA     - the official Microsoft schemas, bundled in ../references.
                  Authoritative, but only sees structural damage: it types
                  visualType as "any string" and leaves field wells and object
                  names free-form.
  2. RULES      - the in2Facts field notes as executable checks. This is where
                  the expensive mistakes live, and the schema cannot see any
                  of them.
  3. REFERENCES - every Entity/Property in the report resolved against the
                  TMDL. Catches a visual pointing at a measure that was renamed
                  or never existed, which is invisible until you look at the
                  rendered page.
  4. APPEARANCE - the canvas, the navigation, the grid, the palette and the
                  page order. Layers 1-3 pass a page that is correctly wired
                  and looks nothing like the rest of the report; this is the
                  layer that notices. It checks the frame, never the content,
                  so two people with entirely different pages both pass.

Nothing here needs Desktop running or a network connection.
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.join(HERE, "..", "references", "json-schemas")

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"


class Finding(object):
    def __init__(self, level, rule, where, message, hint=None):
        self.level, self.rule, self.where = level, rule, where
        self.message, self.hint = message, hint

    def as_dict(self):
        return {"level": self.level, "rule": self.rule, "where": self.where,
                "message": self.message, "hint": self.hint}


# --------------------------------------------------------------------------
# TMDL - just enough to know what exists
# --------------------------------------------------------------------------

def read_model(model_dir):
    """Tables, columns, measures and column data types from a TMDL folder.

    Deliberately a small regex reader rather than a parser: it only needs to
    answer "does this name exist" and "what type is this column"."""
    model = {"tables": {}, "measures": {}, "columns": {}, "coltypes": {},
             "datacategory": {}, "expressions": {}}
    tables_dir = os.path.join(model_dir, "definition", "tables")
    if not os.path.isdir(tables_dir):
        return model

    name_re = re.compile(r"^\t(measure|column)\s+('([^']+)'|[^\s=]+)")
    for fn in sorted(os.listdir(tables_dir)):
        if not fn.endswith(".tmdl"):
            continue
        text = io.open(os.path.join(tables_dir, fn), encoding="utf-8").read()
        m = re.search(r"^table\s+('([^']+)'|\S+)", text, re.M)
        if not m:
            continue
        table = m.group(2) or m.group(1)
        model["tables"][table] = fn

        lines = text.split("\n")
        for i, line in enumerate(lines):
            hit = name_re.match(line)
            if not hit:
                continue
            kind = hit.group(1)
            obj = hit.group(3) or hit.group(2)
            key = (table, obj)
            if kind == "measure":
                model["measures"][key] = fn
                # The body too, not just the name. One rule needs to read what a
                # measure actually returns - see the card-aspect check - and a
                # second regex reader over the same file would be worse than
                # carrying the text.
                body = [line.split("=", 1)[1] if "=" in line else ""]
                for nxt in lines[i + 1:]:
                    if nxt.strip() and not nxt.startswith("\t\t\t"):
                        break
                    body.append(nxt)
                model["expressions"][key] = "\n".join(body)
            else:
                model["columns"][key] = fn
            # scan the object's own indented properties for dataType/dataCategory
            for nxt in lines[i + 1:]:
                if nxt.strip() and not nxt.startswith("\t\t"):
                    break
                dt = re.match(r"\t\tdataType:\s*(\S+)", nxt)
                if dt:
                    model["coltypes"][key] = dt.group(1)
                dc = re.match(r"\t\tdataCategory:\s*(\S+)", nxt)
                if dc:
                    model["datacategory"][key] = dc.group(1)
    return model


# --------------------------------------------------------------------------
# Layer 1 - official schemas
# --------------------------------------------------------------------------

def load_schema(name):
    p = os.path.join(SCHEMA_DIR, name)
    if not os.path.isfile(p):
        return None
    return json.load(io.open(p, encoding="utf-8"))


def build_validator(jsonschema, schema, findings):
    """A validator whose $refs resolve to the bundled copies.

    The "schema-embedded" file is not actually self-contained - it still points
    at formattingObjectDefinitions and semanticQuery. Left alone, jsonschema
    fetches those over the network, which makes a supposedly offline check fail
    on a train and emits a deprecation warning."""
    local = {
        "../../formattingObjectDefinitions/1.3.0/schema.json":
            "formattingObjectDefinitions.schema.json",
        "../../semanticQuery/1.2.0/schema.json":
            "semanticQuery-1.2.0.schema.json",
    }
    store = {}
    for ref, fn in local.items():
        doc = load_schema(fn)
        if doc is None:
            findings.append(Finding(
                INFO, "schema.incomplete", "-",
                "%s is not bundled, so layer 1 was skipped" % fn,
                "without it validation would silently go to the network."))
            return None
        store[ref] = doc
    try:
        from referencing import Registry, Resource
        resources = [(ref, Resource.from_contents(doc, default_specification=
                      __import__("referencing.jsonschema", fromlist=["DRAFT7"]).DRAFT7))
                     for ref, doc in store.items()]
        registry = Registry().with_resources(resources)
        return jsonschema.Draft7Validator(schema, registry=registry)
    except Exception:
        # older jsonschema: RefResolver still works and stays offline
        resolver = jsonschema.RefResolver.from_schema(schema, store=store)
        return jsonschema.Draft7Validator(schema, resolver=resolver)


def check_schema(visuals, findings):
    try:
        import jsonschema
    except ImportError:
        findings.append(Finding(
            INFO, "schema.unavailable", "-",
            "jsonschema is not installed, so layer 1 was skipped",
            "pip install jsonschema  (layers 2 and 3 still ran)"))
        return

    schema = load_schema("visualConfiguration.schema.json")
    if schema is None:
        findings.append(Finding(
            INFO, "schema.missing", "-",
            "visualConfiguration.schema.json is not bundled, so layer 1 was skipped",
            "fetch it from developer.microsoft.com into references/json-schemas/"))
        return

    validator = build_validator(jsonschema, schema, findings)
    if validator is None:
        return
    for path, doc in visuals:
        node = doc.get("visual")
        if node is None:
            continue
        for err in validator.iter_errors(node):
            loc = "/".join(str(x) for x in err.absolute_path) or "visual"
            findings.append(Finding(
                ERROR, "schema", "%s :: %s" % (rel(path), loc), err.message))


# --------------------------------------------------------------------------
# Layer 2 - field notes as rules
# --------------------------------------------------------------------------

# Field wells that are actually correct, per visual type. "Categories" is the
# format-pane label for a card's category well; the well itself is "Rows", and
# using the label renders nothing at all.
WELLS = {
    "cardVisual":           {"Data", "Rows", "ReferenceLabels", "AdditionalMeasure", "Tooltips"},
    "advancedSlicerVisual": {"Values", "Tooltips"},
    "tableEx":              {"Values"},
    "pivotTable":           {"Rows", "Columns", "Values"},
    "slicer":               {"Values"},
}

# Properties that do not exist, and what to use instead.
BAD_PROPS = {
    ("tableEx", "columnHeaders", "show"):
        "a table always shows its headers; Desktop strips this on save. "
        "Use a blank displayName on the projection instead.",
    ("tableEx", "total", "show"):
        "the property is total.totals, not total.show.",
    ("pivotTable", "total", "show"):
        "the property is total.totals, not total.show.",
}

# Properties that do not exist. maxTiles was invented while guessing at a card
# grid; a visual carrying it renders as a single column.
#
# autoGrid is NOT here on purpose: it is genuine on advancedSlicerVisual.layout,
# alongside columnCount/rowCount/showFixedSize, and appears in the report that
# renders correctly. Verified before adding this rule, after an earlier version
# flagged three working visuals.
INVENTED = {"maxTiles"}

# Grid object expected per visual type.
GRID_OBJECT = {
    "advancedSlicerVisual": ("layout", {"columnCount", "rowCount"}),
    "cardVisual": ("smallMultiplesLayout", {"rowCount"}),
}


def prop_names(entries):
    out = set()
    for e in entries or []:
        out |= set((e.get("properties") or {}).keys())
    return out


def check_rules(visuals, findings):
    for path, doc in visuals:
        v = doc.get("visual") or {}
        vt = v.get("visualType", "?")
        objs = v.get("objects") or {}
        where = rel(path)

        # --- field wells ---------------------------------------------------
        qs = ((v.get("query") or {}).get("queryState")) or {}
        known = WELLS.get(vt)
        for well in qs:
            if well == "Categories":
                findings.append(Finding(
                    ERROR, "well.categories", "%s :: %s" % (where, vt),
                    "field well 'Categories' does not exist",
                    "the well is 'Rows'. 'Categories' is only its label in the "
                    "format pane, and a visual using it renders nothing."))
            elif known and well not in known:
                findings.append(Finding(
                    WARN, "well.unknown", "%s :: %s" % (where, vt),
                    "field well %r is not one this skill has seen on %s" % (well, vt),
                    "known wells: %s. Confirm against a visual built in Desktop."
                    % ", ".join(sorted(known))))

        # --- properties that do not exist -----------------------------------
        for obj, entries in objs.items():
            for p in prop_names(entries):
                why = BAD_PROPS.get((vt, obj, p))
                if why:
                    findings.append(Finding(
                        ERROR, "prop.invalid", "%s :: objects.%s.%s" % (where, obj, p), why))
            if obj in ("values",) and prop_names(entries) & {"imageHeight", "imageWidth"}:
                findings.append(Finding(
                    ERROR, "prop.imagesize", "%s :: objects.values" % where,
                    "imageHeight/imageWidth under 'values' are silently ignored",
                    "they belong on objects.grid."))

        # --- invented properties --------------------------------------------
        for obj, entries in objs.items():
            bad = prop_names(entries) & INVENTED
            if bad:
                findings.append(Finding(
                    ERROR, "prop.invented", "%s :: objects.%s" % (where, obj),
                    "%s is not a real property; the visual renders as a single column"
                    % ", ".join(sorted(bad)),
                    "grid geometry differs per visual type - see GRID_OBJECT."))

        # --- selector presence is semantic -----------------------------------
        for entry in objs.get("label") or []:
            if "show" in (entry.get("properties") or {}) and "selector" not in entry:
                findings.append(Finding(
                    ERROR, "selector.label", "%s :: objects.label" % where,
                    "label.show needs selector {\"id\": \"default\"} or it is ignored"))
        for entry in objs.get("value") or []:
            if "show" in (entry.get("properties") or {}) and "selector" in entry:
                findings.append(Finding(
                    ERROR, "selector.value", "%s :: objects.value" % where,
                    "value.show must NOT carry a selector; with one it is ignored",
                    "the category then keeps printing under every tile, and the "
                    "space it reserves clips the artwork."))

        # --- per-item measure bindings need the wildcard ---------------------
        for obj in ("image", "accentBar"):
            for entry in objs.get(obj) or []:
                blob = json.dumps(entry.get("properties") or {})
                if '"Measure"' not in blob:
                    continue
                sel = entry.get("selector") or {}
                data = sel.get("data") or []
                if not any("dataViewWildcard" in d for d in data):
                    findings.append(Finding(
                        ERROR, "selector.wildcard", "%s :: objects.%s" % (where, obj),
                        "a measure-driven per-item property needs a dataViewWildcard selector",
                        'selector: {"data": [{"dataViewWildcard": {"matchingOption": 1}}], '
                        '"id": "default", "hierarchyMatching": 1} - without it the '
                        "binding lands on one tile instead of every tile."))

        # --- grid object per visual type -------------------------------------
        expect = GRID_OBJECT.get(vt)
        if expect:
            name, need = expect
            other = {"layout", "smallMultiplesLayout"} - {name}
            for wrong in other & set(objs):
                findings.append(Finding(
                    WARN, "grid.wrongobject", "%s :: objects.%s" % (where, wrong),
                    "%s uses objects.%s for its grid, not %s" % (vt, name, wrong)))
            if name in objs:
                missing = need - prop_names(objs[name])
                if missing:
                    findings.append(Finding(
                        WARN, "grid.incomplete", "%s :: objects.%s" % (where, name),
                        "missing %s" % ", ".join(sorted(missing)),
                        "state the grid outright rather than relying on derivation."))

        # --- projections: active ---------------------------------------------
        for well, spec in qs.items():
            for pr in spec.get("projections") or []:
                has = "active" in pr
                if vt == "cardVisual" and has:
                    findings.append(Finding(
                        WARN, "proj.active", "%s :: %s" % (where, well),
                        'a cardVisual projection should not carry "active": true'))

        # --- sortDefinition must reference something the visual queries -------
        sd = ((v.get("query") or {}).get("sortDefinition")) or {}
        for s in sd.get("sort") or []:
            fld = s.get("field") or {}
            kind = "Measure" if "Measure" in fld else "Column"
            prop = (fld.get(kind) or {}).get("Property")
            queried = set()
            for spec in qs.values():
                for pr in spec.get("projections") or []:
                    f = pr.get("field") or {}
                    k = "Measure" if "Measure" in f else "Column"
                    queried.add((f.get(k) or {}).get("Property"))
            if prop and prop not in queried:
                findings.append(Finding(
                    ERROR, "sort.notqueried", "%s :: sortDefinition" % where,
                    "sorts by %r, which the visual does not query - the sort is ignored" % prop,
                    "project it into Tooltips purely to make it sortable."))


# --------------------------------------------------------------------------
# Layer 3 - references resolve against the model
# --------------------------------------------------------------------------

def walk_refs(node, out):
    """Every (Entity, Property, kind) referenced anywhere in a visual."""
    if isinstance(node, dict):
        for kind in ("Measure", "Column"):
            spec = node.get(kind)
            if isinstance(spec, dict) and "Property" in spec:
                ent = (((spec.get("Expression") or {}).get("SourceRef")) or {}).get("Entity")
                if ent:
                    out.append((ent, spec["Property"], kind))
        for v in node.values():
            walk_refs(v, out)
    elif isinstance(node, list):
        for v in node:
            walk_refs(v, out)


def check_references(visuals, model, findings):
    if not model["tables"]:
        findings.append(Finding(
            INFO, "model.notfound", "-",
            "no TMDL tables found, so layer 3 was skipped"))
        return

    for path, doc in visuals:
        refs = []
        walk_refs(doc, refs)
        for ent, prop, kind in sorted(set(refs)):
            if ent not in model["tables"]:
                findings.append(Finding(
                    ERROR, "ref.table", "%s :: %s.%s" % (rel(path), ent, prop),
                    "table %r does not exist in the semantic model" % ent))
                continue
            key = (ent, prop)
            if key in model["measures"] or key in model["columns"]:
                continue
            # a name may legitimately be either; only complain if it is neither
            findings.append(Finding(
                ERROR, "ref.object", "%s :: %s.%s" % (rel(path), ent, prop),
                "%s %r does not exist on table %r" % (kind.lower(), prop, ent),
                "renamed or removed? this renders blank with no error."))

    # image bindings must point at an ImageUrl-categorised measure
    for path, doc in visuals:
        v = doc.get("visual") or {}
        for entry in (v.get("objects") or {}).get("image") or []:
            refs = []
            walk_refs(entry.get("properties") or {}, refs)
            for ent, prop, kind in refs:
                if kind != "Measure":
                    continue
                key = (ent, prop)
                if key in model["measures"] and model["datacategory"].get(key) != "ImageUrl":
                    findings.append(Finding(
                        ERROR, "ref.imageurl", "%s :: %s.%s" % (rel(path), ent, prop),
                        "measure used as an image is not dataCategory: ImageUrl",
                        "without it the image never renders."))

    # a slicer over a numeric column defaults to the range slider
    for path, doc in visuals:
        v = doc.get("visual") or {}
        if v.get("visualType") != "slicer":
            continue
        mode = None
        for e in (v.get("objects") or {}).get("data") or []:
            mode = ((e.get("properties") or {}).get("mode") or {}).get(
                "expr", {}).get("Literal", {}).get("Value")
        refs = []
        walk_refs((v.get("query") or {}), refs)
        for ent, prop, kind in refs:
            if kind != "Column":
                continue
            dt = model["coltypes"].get((ent, prop), "")
            if dt in ("int64", "double", "decimal") and mode != "'Basic'":
                findings.append(Finding(
                    ERROR, "slicer.numeric", "%s :: %s.%s" % (rel(path), ent, prop),
                    "slicer over a %s column without objects.data.mode = 'Basic'" % dt,
                    "Power BI defaults numeric fields to the range slider, which "
                    "shows no items in a short box and reads as broken."))


# --------------------------------------------------------------------------
# Layer 4 - appearance
# --------------------------------------------------------------------------
#
# Layers 1-3 all answer "is this wired up". None of them answers "does it look
# like the rest of the report", and a page can pass all three while carrying an
# invented accent colour, a visual half off the canvas, or no way to navigate to
# it. On a course where ten people build divergent reports from one generator,
# that gap is the whole question.
#
# These rules are deliberately shaped like the others: they tolerate divergence
# and check the frame, never the content. Nothing here cares how many visuals a
# page has, what type they are, or what they show.
#
# Every constant below was read off the reference report, not chosen:
#
#   CANVAS_W/H    every page.json says 1920 x 1080
#   SIDE_W        the sidebar panel is x=0 w=228; the rail's widest child ends
#                 at 228 (a 3px rule at x=225)
#   CONTENT_X     19 of 20 content visuals start at 252
#   GUTTER        the twentieth starts at 1098, which is 1074 + 24 - the right
#                 edge of the visual beside it plus one gutter
#   THEME_INK     the five colours the whole report actually uses, plus the two
#                 declared in build_report.py that no visual reached for yet.
#                 Team colours are absent on purpose: they arrive through a
#                 measure, so no team hex should ever appear as a literal.

CANVAS_W, CANVAS_H = 1920, 1080
SIDE_W = 228
CONTENT_X = 252
GUTTER = 24

THEME_INK = {
    "#1A1D23",   # INK
    "#5A6472",   # MUTED
    "#8A93A2",   # FAINT
    "#E4E8EE",   # LINE
    "#F4F6F9",   # PANEL / CANVAS
    "#E8002D",   # ACCENT
    "#FFFFFF",
}

# The status colours. These are NOT chrome, and that is why they are a separate
# set rather than seven more entries in THEME_INK: chrome carries no meaning and
# a status colour carries nothing else. They exist only inside measures - a card
# decides "this round is done" and paints it - so none may appear as a literal
# in a visual.json, and THEME_INK must not be used to mean "finished" either.
#
# The list is closed. A fifth status needs a fifth meaning, and inventing one
# silently is how a report ends up with three greens that disagree.
STATUS_INK = {
    "#229971",   # a completed round
    "#FF8000",   # the next race, and the sprint pill
    "#FFF3E6",   # the sprint pill's fill, tinted from the orange above
    "#6B7280",   # no livery known for this team
}

HEX = re.compile(r"#[0-9A-Fa-f]{6}")


def literal(spec):
    """The value out of {"expr": {"Literal": {"Value": "'x'"}}}."""
    val = (((spec or {}).get("expr") or {}).get("Literal") or {}).get("Value")
    if isinstance(val, str) and len(val) > 1 and val[0] == "'" and val[-1] == "'":
        return val[1:-1]
    return val


def nav_targets(doc):
    """Pages this visual navigates to. Detected by shape, not by name, so a
    participant's own naming makes no difference.

    The link lives under visualContainerObjects, not objects - it is a property
    of the container rather than of the visual inside it. Both are read here
    because the distinction is easy to get wrong and costs nothing to allow."""
    out = []
    v = doc.get("visual") or {}
    for holder in ("visualContainerObjects", "objects"):
        for entry in (v.get(holder) or {}).get("visualLink") or []:
            props = entry.get("properties") or {}
            if literal(props.get("type")) == "PageNavigation":
                out.append(literal(props.get("navigationSection")))
    return out


def page_of(visual_path):
    """pages/<page>/visuals/<visual>/visual.json -> <page>"""
    return os.path.basename(os.path.dirname(os.path.dirname(
        os.path.dirname(visual_path))))


def check_appearance(pages, pagemeta, visuals, model, findings):
    if not pages and not visuals:
        return

    page_names = set()
    for path, doc in pages:
        page_names.add(doc.get("name") or os.path.basename(os.path.dirname(path)))

    # --- A1: the canvas is the same size on every page --------------------
    # A page at a different size is not a layout choice: FitToPage rescales it,
    # so identical visuals render at a different scale and the report reads as
    # two reports stitched together.
    for path, doc in pages:
        where = rel(path)
        w, h = doc.get("width"), doc.get("height")
        if (w, h) != (CANVAS_W, CANVAS_H):
            findings.append(Finding(
                ERROR, "page.canvas", where,
                "canvas is %sx%s; every other page is %dx%d" % (w, h, CANVAS_W, CANVAS_H),
                "FitToPage scales the whole page to fit, so a different canvas "
                "renders every visual on it at a different size."))
        if doc.get("displayOption") != "FitToPage":
            findings.append(Finding(
                WARN, "page.displayoption", where,
                "displayOption is %r, not 'FitToPage'" % doc.get("displayOption"),
                "the other pages fit to the window; this one will scroll."))

    # --- A2: every page carries the navigation ----------------------------
    # The sidebar is what makes six pages read as one report. A page without it
    # renders fine and is unreachable, which is the kind of fault that survives
    # to the demo.
    #
    # Only once there is somewhere to navigate TO. The empty project that ships
    # at `start` is Desktop's own one-page shell, and demanding a rail on it
    # failed the gate at three checkpoints - correctly reported, wrongly
    # required.
    by_page = {}
    for path, doc in visuals:
        by_page.setdefault(page_of(path), []).append((path, doc))

    for page in sorted(page_names) if len(page_names) > 1 else []:
        targets = []
        for path, doc in by_page.get(page, []):
            targets.extend(nav_targets(doc))
        if not targets:
            findings.append(Finding(
                ERROR, "page.nav", page,
                "no page-navigation button on this page",
                "every page carries the sidebar. Without it the page is only "
                "reachable from the tab strip, which the report hides."))
            continue
        for target in targets:
            if target not in page_names:
                findings.append(Finding(
                    ERROR, "page.nav", "%s -> %s" % (page, target),
                    "navigates to %r, which is not a page in this report" % target,
                    "the button renders normally and does nothing when clicked."))
        missing = page_names - set(targets) - {page}
        if missing:
            findings.append(Finding(
                WARN, "page.nav", page,
                "sidebar offers no way to %s" % ", ".join(sorted(missing)),
                "the generator lays the rail out from PAGES; a hand-edited page "
                "drifts out of step with it."))

    # --- A3: visuals sit on the grid --------------------------------------
    for path, doc in visuals:
        where = rel(path)
        pos = doc.get("position") or {}
        x, y = pos.get("x"), pos.get("y")
        w, h = pos.get("width"), pos.get("height")
        if None in (x, y, w, h):
            findings.append(Finding(
                ERROR, "layout.position", where, "position is incomplete"))
            continue

        if any(float(n) != int(n) for n in (x, y, w, h)):
            findings.append(Finding(
                WARN, "layout.fractional", where,
                "fractional coordinates (%s, %s, %s, %s)" % (x, y, w, h),
                "Power BI rounds them to the device pixel, so edges that should "
                "line up end up one pixel apart."))

        if x + w > CANVAS_W or y + h > CANVAS_H:
            findings.append(Finding(
                ERROR, "layout.offcanvas", where,
                "extends to (%s, %s), past the %dx%d canvas"
                % (x + w, y + h, CANVAS_W, CANVAS_H),
                "the overflow is cropped on screen with no indication that "
                "anything is missing."))

        # Either wholly in the rail or wholly in the content area. The strip
        # between them is the rail's own margin.
        if x + w > SIDE_W and x < CONTENT_X:
            findings.append(Finding(
                ERROR, "layout.rail", where,
                "spans x=%s..%s, straddling the sidebar edge at %d"
                % (x, x + w, SIDE_W),
                "it overlaps the rail or sits in its margin. Content starts at "
                "x=%d." % CONTENT_X))

    # Content columns: either the left edge, or one gutter right of something.
    for page, entries in sorted(by_page.items()):
        edges = {CONTENT_X}
        for _p, doc in entries:
            pos = doc.get("position") or {}
            if pos.get("x") is not None and pos.get("width") is not None:
                edges.add(pos["x"] + pos["width"] + GUTTER)
        for path, doc in entries:
            pos = doc.get("position") or {}
            x = pos.get("x")
            if x is None or x < CONTENT_X or x in edges:
                continue
            findings.append(Finding(
                WARN, "layout.column", rel(path),
                "starts at x=%s, which is neither the content edge (%d) nor one "
                "gutter (%d) right of another visual" % (x, CONTENT_X, GUTTER),
                "columns that nearly line up read as a mistake rather than a "
                "choice. Derive the x from the visual beside it."))

    # --- A4: colours come from the palette --------------------------------
    # Team colours are not in THEME_INK on purpose: they reach a visual through
    # a measure, so a team hex written as a literal is itself the fault.
    for path, doc in pages + visuals:
        seen = set()
        for hit in HEX.findall(json.dumps(doc)):
            hit = hit.upper()
            if hit in THEME_INK or hit in seen:
                continue
            seen.add(hit)
            extra = ""
            if hit in STATUS_INK:
                extra = (" It is a status colour, which belongs in a measure "
                         "rather than in a visual's properties.")
            findings.append(Finding(
                ERROR, "theme.palette", "%s :: %s" % (rel(path), hit),
                "%s is not one of the report's colours" % hit,
                "use a palette token, or - for anything team-coded - bind the "
                "property to the colour measure instead of writing a hex."
                + extra))

    # The same rule, where the colours that matter actually live. A card paints
    # itself from DAX, so every appearance decision a participant makes is in a
    # measure and none of it was checked here: the check read visual.json and
    # page.json only, and the reference's own four status colours sat outside
    # it. The reference passed the check while breaking the rule the check
    # enforces, which is the worst state for a rule to be in - the material
    # demonstrates the opposite of what it tells you to do.
    for (table, name), body in sorted(model.get("expressions", {}).items()):
        seen = set()
        for hit in HEX.findall(body):
            hit = hit.upper()
            if hit in THEME_INK or hit in STATUS_INK or hit in seen:
                continue
            seen.add(hit)
            findings.append(Finding(
                ERROR, "theme.palette", "'%s'[%s] :: %s" % (table, name, hit),
                "%s is neither a palette token nor one of the four status "
                "colours" % hit,
                "the palette is the tokens at the top of build_report.py; the "
                "status colours are %s. Anything team-coded takes its colour "
                "from the team table, not from a hex you chose."
                % ", ".join(sorted(STATUS_INK))))

    # --- A6: a card's artwork is shaped like the tile it goes in -----------
    #
    # The rule that cost the most to discover, and it was written down nowhere.
    #
    # A card grid scales its SVG to FILL the tile and crops the overflow,
    # centred. So a card whose aspect ratio differs from its tile's loses a band
    # off the top and another off the bottom - and the failure does not look
    # like a failure. The card renders: border, headings, labels, all present.
    # Only whatever sat in the cropped bands is missing, which reads as a
    # styling problem rather than a broken visual.
    #
    # Neither preserveAspectRatio nor a viewBox helps. preserveAspectRatio does
    # nothing without a viewBox and is ignored by this renderer with one; the
    # intrinsic width and height are what the tile scales.
    #
    # Tolerance is set from the three cards that work: the reference's Schedule
    # card is the worst at 7.4% off its tile, Teams the best at 2.3%. The
    # failure that prompted the rule was 48% off. So 12% warns and 25% fails,
    # which leaves the working cards silent with room to spare.
    ASPECT_WARN, ASPECT_ERROR = 0.12, 0.25
    SVG_SIZE = re.compile(r"<svg[^>]*?width='(\d+(?:\.\d+)?)'"
                          r"[^>]*?height='(\d+(?:\.\d+)?)'")
    # A card may build its size from variables rather than literals:
    #     VAR CardW = 417
    #     "<svg ... width='" & CardW & "' height='" & CardH & "'>"
    # Without resolving those the pattern above matches nothing and the rule
    # skips in silence - which is the failure this whole layer exists to avoid.
    # Only a name bound to a bare number is resolved; anything computed stays
    # invisible, and the rule then honestly reports nothing rather than guessing.
    NUMERIC_VAR = re.compile(r"VAR\s+(\w+)\s*=\s*(\d+(?:\.\d+)?)\s*$", re.M)
    # The concatenation as it actually appears in TMDL is  '" & Name & "'  -
    # the DAX string closes, the variable joins, the string resumes - and the
    # line usually breaks in the middle of it. Two earlier attempts at this
    # failed and both looked right: one omitted the double quotes and matched
    # nothing; the next matched but swallowed the single quotes, so
    # width='" & CardW & "' became width=417 and SVG_SIZE,
    # which expects width='417', missed it too. The rule reported clean
    # through both. Only the injection test disagreed.
    CONCAT = re.compile(r"""'"\s*&\s*(\w+)\s*&\s*"'""")

    def resolve_vars(expression):
        """Inline `'" & Name & "'` where Name is a VAR bound to a number."""
        numbers = dict(NUMERIC_VAR.findall(expression))
        if not numbers:
            return expression
        def put_back(m):
            value = numbers.get(m.group(1))
            # quotes restored, or the size regex cannot read what it resolved
            return ("'" + value + "'") if value else m.group(0)

        return CONCAT.sub(put_back, expression)

    def grid_counts(objs):
        out = {}
        for entry in objs.get("layout") or []:
            for name in ("columnCount", "rowCount"):
                raw = literal((entry.get("properties") or {}).get(name))
                if isinstance(raw, str) and raw[:-1].isdigit():
                    out[name] = int(raw[:-1])
                elif isinstance(raw, (int, float)):
                    out[name] = int(raw)
        return out

    for path, doc in visuals:
        v = doc.get("visual") or {}
        objs = v.get("objects") or {}
        counts = grid_counts(objs)
        if not counts.get("columnCount") or not counts.get("rowCount"):
            continue

        refs = []
        for entry in objs.get("image") or []:
            walk_refs(entry.get("properties") or {}, refs)
        measure = next(((e, p) for e, p, k in refs if k == "Measure"), None)
        if not measure:
            continue

        expression = (model or {}).get("expressions", {}).get(measure)
        if not expression:
            continue
        size = SVG_SIZE.search(resolve_vars(expression))
        if not size:
            continue

        pos = doc.get("position") or {}
        if not pos.get("width") or not pos.get("height"):
            continue
        tile = (float(pos["width"]) / counts["columnCount"]) / \
               (float(pos["height"]) / counts["rowCount"])
        card = float(size.group(1)) / float(size.group(2))
        off = abs(card - tile) / tile

        if off < ASPECT_WARN:
            continue
        findings.append(Finding(
            ERROR if off >= ASPECT_ERROR else WARN,
            "card.aspect", "%s :: %s[%s]" % (rel(path), measure[0], measure[1]),
            "card is %s x %s (aspect %.2f) in a %.0f x %.0f tile (aspect %.2f) - %.0f%% off"
            % (size.group(1), size.group(2), card,
               float(pos["width"]) / counts["columnCount"],
               float(pos["height"]) / counts["rowCount"], tile, off * 100),
            "the grid scales the card to fill the tile and crops the overflow "
            "centred, so the edges on the card's longer axis disappear - top "
            "and bottom when the card is the taller shape, left and right when "
            "it is the wider one. The card still renders, so nothing else will "
            "tell you. Set the SVG's width and height to the tile, or change "
            "the grid's columnCount / "
            "rowCount to suit the card. A viewBox will not save you."))

    # --- A5: the tab strip agrees with what is on disk ---------------------
    if pagemeta is not None:
        order = pagemeta.get("pageOrder") or []
        for ghost in [p for p in order if p not in page_names]:
            findings.append(Finding(
                ERROR, "pages.order", "pages.json",
                "pageOrder lists %r, which has no folder" % ghost))
        for orphan in sorted(page_names - set(order)):
            findings.append(Finding(
                ERROR, "pages.order", "pages.json",
                "page %r is not in pageOrder" % orphan,
                "it lands at the end of the tab strip regardless of where the "
                "sidebar puts it, so navigation and ordering disagree."))
        active = pagemeta.get("activePageName")
        if order and active != order[0]:
            findings.append(Finding(
                WARN, "pages.active", "pages.json",
                "opens on %r, which is not the first page (%r)" % (active, order[0]),
                "Desktop writes whichever page you last looked at. Set it back "
                "before committing, or everyone opens on your working page."))


# --------------------------------------------------------------------------

ROOT = [""]


def rel(path):
    try:
        return os.path.relpath(path, ROOT[0])
    except ValueError:
        return path


def find_project(start):
    if start.lower().endswith(".pbip"):
        return os.path.dirname(os.path.abspath(start))
    start = os.path.abspath(start)
    for base, dirs, files in os.walk(start):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".pbi")]
        if any(f.lower().endswith(".pbip") for f in files):
            return base
    return None


def collect(project):
    report = model = None
    for d in os.listdir(project):
        full = os.path.join(project, d)
        if d.endswith(".Report") and os.path.isdir(full):
            report = full
        elif d.endswith(".SemanticModel") and os.path.isdir(full):
            model = full
    visuals, pages, pagemeta = [], [], None
    if report:
        pages_dir = os.path.join(report, "definition", "pages")
        for base, _dirs, files in os.walk(pages_dir):
            for f in files:
                if f not in ("visual.json", "page.json"):
                    continue
                p = os.path.join(base, f)
                try:
                    doc = json.load(io.open(p, encoding="utf-8"))
                except ValueError as exc:
                    doc = {"__parse_error__": str(exc)}
                (visuals if f == "visual.json" else pages).append((p, doc))
        meta = os.path.join(pages_dir, "pages.json")
        if os.path.isfile(meta):
            try:
                pagemeta = json.load(io.open(meta, encoding="utf-8"))
            except ValueError:
                pagemeta = None
    return report, model, visuals, pages, pagemeta


def main():
    ap = argparse.ArgumentParser(description="Validate a PBIP project offline.")
    ap.add_argument("path", nargs="?", default=".", help="a .pbip file or a folder to search")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--quiet", action="store_true", help="errors only")
    # Run layer 1 alone, so the gap between the official schemas and this tool
    # can be measured instead of taken on trust. Chapter 05 asks the reader to
    # break a field-well name and compare the two runs: the schemas pass it,
    # the full tool names it. Without this flag that comparison is a claim.
    ap.add_argument("--schema-only", action="store_true",
                    help="layer 1 only - validate against the Microsoft schemas "
                         "and stop, skipping the field-note rules and the "
                         "reference checks")
    # Layer 4 checks the frame rather than the wiring, so a chapter that is
    # deliberately mid-layout can turn it off without losing layers 1-3.
    ap.add_argument("--no-appearance", action="store_true",
                    help="skip layer 4 - the canvas, navigation, grid, palette "
                         "and page-order checks")
    args = ap.parse_args()

    project = find_project(args.path)
    if not project:
        print("no .pbip found under %s" % os.path.abspath(args.path))
        return 2
    ROOT[0] = project

    report, model_dir, visuals, pages, pagemeta = collect(project)
    findings = []

    for p, d in visuals + pages:
        if "__parse_error__" in d:
            findings.append(Finding(ERROR, "json.invalid", rel(p), d["__parse_error__"]))
    visuals = [(p, d) for p, d in visuals if "__parse_error__" not in d]
    pages = [(p, d) for p, d in pages if "__parse_error__" not in d]

    model = read_model(model_dir) if model_dir else {"tables": {}, "measures": {},
                                                     "columns": {}, "coltypes": {},
                                                     "datacategory": {}}
    check_schema(visuals, findings)
    if not args.schema_only:
        check_rules(visuals, findings)
        check_references(visuals, model, findings)
        if not args.no_appearance:
            check_appearance(pages, pagemeta, visuals, model, findings)

    if args.json:
        print(json.dumps({"project": project, "visuals": len(visuals),
                          "findings": [f.as_dict() for f in findings]}, indent=2))
    else:
        order = {ERROR: 0, WARN: 1, INFO: 2}
        findings.sort(key=lambda f: (order[f.level], f.rule, f.where))
        print("%s  -  %d visuals, %d tables, %d measures"
              % (os.path.basename(project), len(visuals),
                 len(model["tables"]), len(model["measures"])))
        shown = [f for f in findings if not (args.quiet and f.level != ERROR)]
        if not shown:
            # "nothing to fix before opening Desktop" was a promise this tool
            # cannot keep. No layer reads what a measure RETURNS, so a card whose
            # payload is Base64 behind a ;utf8, prefix passes all four layers and
            # renders 23 empty tiles - which is exactly the exercise the SVG
            # chapter sets, and run 5 watched it print this sentence on a report
            # it had deliberately broken. With --schema-only it is worse again:
            # three of the four layers never ran at all.
            #
            # So report what WAS checked, and name what was skipped. The reader
            # keeps the information and loses the reassurance, which is the right
            # way round for a checking tool.
            if args.schema_only:
                print("\nno findings - but only layer 1 ran, so layers 2 to 4 "
                      "have not looked at this report")
            elif args.no_appearance:
                print("\nno findings from layers 1 to 3 - layer 4 (appearance) "
                      "was skipped")
            else:
                print("\nno findings - all four layers ran. None of them reads "
                      "what a measure returns, so this is not a promise that the "
                      "report renders")
        for f in shown:
            print("\n%-5s %s" % (f.level, f.rule))
            print("      %s" % f.where)
            print("      %s" % f.message)
            if f.hint:
                print("      -> %s" % f.hint)
        n_e = sum(1 for f in findings if f.level == ERROR)
        n_w = sum(1 for f in findings if f.level == WARN)
        print("\n%d error(s), %d warning(s)" % (n_e, n_w))

    return 1 if any(f.level == ERROR for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())

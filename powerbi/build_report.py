"""Generate the PBIR report definition for Ultimate F1 Dashboard.

Rebuilds every page under "Ultimate F1 Dashboard.Report/definition/pages" from
this one description, so layout changes are edits here rather than hand-patched
JSON. Power BI Desktop must be CLOSED while this runs, then reopen the .pbip.

    python build_report.py

Schema versions are pinned to what this Desktop build writes:
visualContainer 2.11.0, page 2.1.0, pagesMetadata 1.1.0.
Desktop rewrites visualContainer to its own version on save, so if a diff shows
that number changing, update it here rather than reverting it.

PBIR has no master-page concept, so the sidebar is emitted per page.
"""
import csv
import hashlib
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_DEF = os.path.join(HERE, "Ultimate F1 Dashboard.Report", "definition")
PAGES_DIR = os.path.join(REPORT_DEF, "pages")

V_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.11.0/schema.json"
P_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PM_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"

W, H = 1920, 1080
SIDE_W = 228
CX = 252                      # content left edge
CW = W - CX                   # content runs to the right edge of the canvas
HEAD_Y, HEAD_H = 28, 46
BODY_Y = 104
# Content runs to the very bottom edge, with no bottom margin: the page is
# seamless, so there is no page boundary for a margin to sit against, and the
# reclaimed 32px goes to the visuals that were always cut off.

INK = "#1A1D23"
MUTED = "#5A6472"
FAINT = "#8A93A2"
LINE = "#E4E8EE"

# CANVAS is declared but never actually painted: the page background is set to
# 100% transparency, which is what removes the drop shadow. The ground you see
# is whatever shows through, and that renders white.
CANVAS = "#F4F6F9"

# So the rail carries the tint - on a white ground it is what makes the sidebar
# read as a panel at all.
PANEL = "#F4F6F9"
ACCENT = "#E8002D"

# Rail metrics. Slicer heights are derived, not guessed: a list slicer spends
# about 36px on its title block, 23px per item row and 8px of bottom padding.
# Undershoot that and Power BI silently adds a scrollbar.
NAV_Y0, NAV_H, NAV_STEP = 122, 30, 34
SLICER_TITLE_BLOCK, SLICER_ITEM, SLICER_PAD = 36, 23, 10


def slicer_height(items):
    return SLICER_TITLE_BLOCK + items * SLICER_ITEM + SLICER_PAD


PAGES = [
    ("pg01Schedule", "Schedule"),
    ("pg02Results", "Results"),
    ("pg03DriverStandings", "Driver Standings"),
    ("pg04ConstructorStandings", "Constructor Standings"),
    ("pg05Drivers", "Drivers"),
    ("pg06Teams", "Teams"),
]

# --------------------------------------------------------------------------
# expression helpers
# --------------------------------------------------------------------------


def lit(value):
    return {"expr": {"Literal": {"Value": value}}}


def s_lit(text):
    """String literal - PBIR wraps these in single quotes inside the value."""
    return lit("'%s'" % text)


def colour(hex_value):
    return {"solid": {"color": lit("'%s'" % hex_value)}}


def col(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def meas(entity, prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def proj(field, entity, prop, display=None):
    # "active": true is what Desktop writes on every projection; it adds it back
    # on save if omitted, which shows up as noise in the next diff.
    p = {"field": field, "queryRef": "%s.%s" % (entity, prop), "nativeQueryRef": prop,
         "active": True}
    if display is not None:
        p["displayName"] = display
    return p


def pcol(entity, prop, display=None):
    return proj(col(entity, prop), entity, prop, display)


def pmeas(entity, prop, display=None):
    return proj(meas(entity, prop), entity, prop, display)


def fid(*parts):
    """Deterministic 20-hex filter/visual id so reruns produce stable files."""
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]


def eq_filter(entity, prop, literal, ordinal=0, is_measure=False):
    """Visual-level 'column equals value' filter, in PBIR's Advanced form."""
    src = entity[:1].lower()
    ref = {"Expression": {"SourceRef": {"Source": src}}, "Property": prop}
    side = {"Measure": ref} if is_measure else {"Column": ref}
    return {
        "name": fid(entity, prop, literal),
        "ordinal": ordinal,
        "field": meas(entity, prop) if is_measure else col(entity, prop),
        "type": "Advanced",
        "filter": {
            "Version": 2,
            "From": [{"Name": src, "Entity": entity, "Type": 0}],
            "Where": [{"Condition": {"Comparison": {
                "ComparisonKind": 0,
                "Left": side,
                "Right": {"Literal": {"Value": literal}},
            }}}],
        },
        "howCreated": "User",
    }


def visual(name, x, y, w, h, z, tab, vis, filters=None):
    v = {
        "$schema": V_SCHEMA,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": tab},
        "visual": vis,
    }
    if filters:
        v["filterConfig"] = {"filters": filters}
    return v


# --------------------------------------------------------------------------
# chrome
# --------------------------------------------------------------------------


def textbox(name, x, y, w, h, z, tab, runs):
    return visual(name, x, y, w, h, z, tab, {
        "visualType": "textbox",
        "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": runs}]}}]},
        "visualContainerObjects": {
            "background": [{"properties": {"show": lit("false")}}],
            "border": [{"properties": {"show": lit("false")}}],
        },
        "drillFilterOtherVisuals": True,
    })


def panel(name, x, y, w, h, z, tab, fill, radius=0):
    """Flat colour band - the rail ground and the hairline rule beside it.

    Built on a textbox rather than a shape. A shape visual paints nothing here:
    neither its own fill (with or without the state selector) nor its container
    background reaches the screen, and a whole-image colour search finds the
    requested tint nowhere. That went unnoticed for as long as the rail was
    white, because a shape that renders nothing looks identical to a white one.
    Textboxes are known to render - every label in the rail is one - and their
    container background is the property the theme uses to paint visuals."""
    return visual(name, x, y, w, h, z, tab, {
        "visualType": "textbox",
        "objects": {"general": [{"properties": {
            "paragraphs": [{"textRuns": [{"value": ""}]}]}}]},
        "visualContainerObjects": {
            "background": [{"properties": {
                "show": lit("true"),
                "color": colour(fill),
                "transparency": lit("0D"),
            }}],
            "border": [{"properties": {"show": lit("false")}}],
        },
        "drillFilterOtherVisuals": True,
    })


def nav_button(name, x, y, w, h, z, tab, label, target, active):
    """actionButton wired to PageNavigation - the shape Desktop itself writes."""
    fill = ACCENT if active else PANEL
    text = "#FFFFFF" if active else MUTED
    return visual(name, x, y, w, h, z, tab, {
        "visualType": "actionButton",
        "objects": {
            "icon": [
                {"properties": {"shapeType": s_lit("blank")}, "selector": {"id": "default"}},
                {"properties": {"show": lit("false")}},
            ],
            "text": [
                {"properties": {"show": lit("true")}},
                {"properties": {
                    "text": s_lit(label),
                    "fontSize": lit("11D"),
                    "fontColor": {"solid": {"color": lit("'%s'" % text)}},
                    "horizontalAlignment": s_lit("left"),
                    "leftMargin": lit("14D"),
                }, "selector": {"id": "default"}},
            ],
            "fill": [
                {"properties": {"show": lit("true")}},
                {"properties": {
                    "fillColor": {"solid": {"color": lit("'%s'" % fill)}},
                    "transparency": lit("0D"),
                }, "selector": {"id": "default"}},
            ],
            "outline": [{"properties": {"show": lit("false")}}],
        },
        "visualContainerObjects": {
            "visualLink": [{"properties": {
                "show": lit("true"),
                "type": s_lit("PageNavigation"),
                "navigationSection": s_lit(target),
            }}],
            "background": [{"properties": {"show": lit("false")}}],
            "border": [{"properties": {"show": lit("false")}}],
        },
        "drillFilterOtherVisuals": True,
    })


def sidebar(active_page):
    """Sidebar ground, wordmark and the six navigation buttons."""
    out = [
        panel("v01SidebarPanel", 0, 0, SIDE_W, H, 100, 0, PANEL),
        # 3px in MUTED, not a 1px hairline in LINE. With the canvas transparent
        # the rail has no background tint, so this rule is the only thing
        # separating navigation from content - it has to carry that job. MUTED
        # is already the ink of the nav labels and slicer titles, so the divider
        # belongs to the palette rather than introducing a colour of its own.
        #
        # Width is load-bearing for the colour: at 2px the rule straddled pixel
        # boundaries and anti-aliased to #96A7BD - the set colour blended half
        # into white - so it read as a washed-out hairline whatever hex it was
        # given. 3px renders the actual colour.
        panel("v02SidebarRule", SIDE_W - 3, 0, 3, H, 101, 1, INK),
        textbox("v03Wordmark", RAIL_X, 28, 190, 56, 200, 2, [
            {"value": "ULTIMATE", "textStyle": {
                "fontFamily": "Segoe UI", "fontSize": "13pt", "fontWeight": "bold",
                "color": INK}},
            {"value": "  F1", "textStyle": {
                "fontFamily": "Segoe UI", "fontSize": "13pt", "fontWeight": "bold",
                "color": ACCENT}},
        ]),
        textbox("v04WordmarkSub", RAIL_X, 88, 190, 26, 201, 3, [
            {"value": "SEASON DASHBOARD", "textStyle": {
                "fontFamily": "Segoe UI", "fontSize": "9pt", "color": MUTED}},
        ]),
    ]
    y = NAV_Y0
    for i, (page_name, label) in enumerate(PAGES):
        out.append(nav_button(
            "v%02dNav%02d" % (5 + i, i + 1), 12, y, SIDE_W - 24, NAV_H,
            300 + i, 4 + i, label, page_name, page_name == active_page))
        y += NAV_STEP
    # Same treatment as the SEASON DASHBOARD eyebrow, so the rail has two
    # clearly labelled zones rather than one undifferentiated stack.
    fx, fy, fw, fh = FILTERS_LABEL_BOX
    out.append(textbox("v12FiltersLabel", fx, fy, fw, fh, 203, 19, [
        {"value": "FILTERS", "textStyle": {
            "fontFamily": "Segoe UI", "fontSize": "9pt", "color": MUTED}},
    ]))
    return out


def header(title, subtitle):
    """Page title and standfirst.

    A subtitle says what the page is FOR, never what its cards CONTAIN. The
    distinction is not stylistic: the cards are written by whoever is doing the
    course, and three of these once described the reference's versions instead -
    naming colours the palette does not contain, promising averages the card
    prompt does not ask for, and asserting the exact status strings a measure
    would emit. Each was false against a correctly-built card, and nothing
    catches it, because no check here reads English.

    If a sentence here would stop being true when somebody writes a different
    measure, it belongs in the measure's own doc comment instead."""
    return [
        textbox("v20Header", CX, HEAD_Y, 900, HEAD_H, 210, 30, [
            {"value": title, "textStyle": {
                "fontFamily": "Segoe UI", "fontSize": "21pt", "fontWeight": "bold",
                "color": INK}},
        ]),
        textbox("v21Sub", CX, HEAD_Y + 44, 900, 26, 211, 31, [
            {"value": subtitle, "textStyle": {
                "fontFamily": "Segoe UI", "fontSize": "9pt", "color": MUTED}},
        ]),
    ]


def slicer(name, box, z, tab, entity, prop, title, selected=None):
    """A list slicer.

    Two things here are easy to get wrong and both render an empty control:

    * data.mode must be 'Basic'. Season and Round are int64, and Power BI
      defaults a slicer over a numeric column to the range slider - which shows
      no items at all in a short box, so the slicer looks broken rather than
      misconfigured.
    * general.orientation is 0 for a vertical list. There is no orientation 2.

    Give it room, too: a list needs roughly 40px of chrome plus a row per item.
    """
    x, y, w, h = box
    general = {"orientation": lit("0D")}
    if selected is not None:
        general.update(selection(entity, prop, selected))
    return visual(name, x, y, w, h, z, tab, {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [pcol(entity, prop)]}}},
        "objects": {
            "data": [{"properties": {"mode": s_lit("Basic")}}],
            "general": [{"properties": general}],
            # fontColor is pinned deliberately. Slicer items are the only
            # thing in the report that inherited "Second-level elements", and
            # that token is now set to the wallpaper colour to kill the dotted
            # page outline - inheriting it would paint these invisible.
            "items": [{"properties": {
                "fontColor": {"solid": {"color": lit("'%s'" % INK)}},
                "textSize": lit("9D"),
                "padding": lit("3D"),
            }}],
            "header": [{"properties": {
                "show": lit("false"),
                "textSize": lit("9D"),
            }}],
        },
        "visualContainerObjects": {
            # Matches the navigation buttons - same 11pt, same MUTED ink - so a
            # filter title and a nav label read as the same class of control.
            "title": [{"properties": {
                "show": lit("true"), "text": s_lit(title),
                "fontSize": lit("11D"),
                "fontColor": {"solid": {"color": lit("'%s'" % MUTED)}},
                "alignment": s_lit("left"),
            }}],
            # The theme gives every visual a rounded border. On the white rail
            # that boxes each slicer in for no reason, so slicers opt out.
            "border": [{"properties": {"show": lit("false")}}],
            "background": [{"properties": {"show": lit("false")}}],
        },
        "drillFilterOtherVisuals": True,
    })


def season_slicer(name="v22SeasonSlicer", z=500, tab=40):
    """Season slicer, preselected to the newest season in the data."""
    return slicer(name, SEASON_BOX, z, tab, "Race", "Season", "Season",
                  selected="%dL" % SEASON)


def country_slicer(name="v23CountrySlicer", z=501, tab=41):
    """Country list under the Season filter in the rail."""
    return slicer(name, COUNTRY_BOX, z, tab, "Race", "Country", "Country")


def card_grid(name, x, y, w, h, z, tab, entity, prop, svg_table, svg_measure,
              columns, rows, sort=None, filters=None):
    """A grid of SVG cards, drawn on the Button Slicer (advancedSlicerVisual).

    This is the visual that renders an SVG measure as the tile itself. The new
    Card visual cannot: its image binding wants a static resource, and every
    attempt to point one at a measure came back blank. The Button Slicer takes
    the measure directly on objects.image.image.

    Three details are load-bearing:

    * the image selector needs the dataViewWildcard entry. Without it the image
      binds to a single item rather than to every tile.
    * layout carries columnCount AND rowCount, so the grid is stated outright
      rather than derived - this is the visual's own grid, not small multiples.
    * label.show false is honoured here, which it is not on a Card. That is what
      keeps the SVG unlabelled, so the card is purely the artwork.

    It is a slicer, so clicking a tile filters the page. On these three pages
    nothing else is bound to that field, so the click reads as a highlight.

    There is a theme dependency: tiles paint with "Second-level elements"
    (foregroundNeutralSecondary). Point that token at a background colour and
    every tile silently turns invisible - see the README."""

    def plain(field, ent, pr):
        return {"field": field, "queryRef": "%s.%s" % (ent, pr),
                "nativeQueryRef": pr}

    def off(obj):
        return [{"properties": {"show": lit("false")}, "selector": {"id": "default"}}]

    # Tiles otherwise follow the Values field - alphabetical by code, which puts
    # ALB before VER regardless of the championship.
    query = {"queryState": {
        "Values": {"projections": [plain(col(entity, prop), entity, prop)]},
    }}
    if sort:
        # A slicer will only sort by something it actually queries, so the
        # ranking measure rides along in Tooltips purely to be sortable.
        fld = sort["sort"][0]["field"]
        if "Measure" in fld:
            prop = fld["Measure"]["Property"]
            query["queryState"]["Tooltips"] = {
                "projections": [plain(fld, svg_table, prop)]
            }
        query["sortDefinition"] = sort

    return visual(name, x, y, w, h, z, tab, {
        "visualType": "advancedSlicerVisual",
        "query": query,
        "objects": {
            "image": [{
                "properties": {"image": {"expr": {"Measure": {
                    "Expression": {"SourceRef": {"Entity": svg_table}},
                    "Property": svg_measure}}}},
                "selector": {
                    "data": [{"dataViewWildcard": {"matchingOption": 1}}],
                    "id": "default",
                    "hierarchyMatching": 1,
                },
            }],
            "layout": [{"properties": {
                "showFixedSize": lit("false"),
                "autoGrid": lit("true"),
                "columnCount": lit("%dL" % columns),
                "rowCount": lit("%dL" % rows),
            }}],
            "selection": [{"properties": {
                "singleSelect": lit("false"),
                "strictSingleSelect": lit("false"),
            }}],
            # the SVG carries the whole card, so the tile's own chrome goes.
            # value matters twice over: it prints the key under each tile, and
            # the space it reserves squeezes the image and clips the artwork.
            # The visual's own accent bar stays off. A tile-edge bar sits behind
            # the image anyway - the SVG is 408x153 in a 411x163 cell - so each
            # card draws its accent itself, which also keeps it identical to the
            # race cards.
            "accentBar": off("accentBar"),
            "label": off("label"),
            # value takes its show WITHOUT a selector. With selector id default
            # - which is what label needs - it is ignored, and the key keeps
            # printing under every tile.
            "value": [{"properties": {"show": lit("false")}}],
            "background": off("background"),
            "shapeCustomRectangle": [{
                "properties": {"rectangleRoundedCurve": lit("7L")},
                "selector": {"id": "default"},
            }],
        },
        # the field name would otherwise sit above the grid as a heading
        "visualContainerObjects": {
            "title": [{"properties": {"show": lit("false")}}],
        },
        "drillFilterOtherVisuals": True,
    }, filters)


def sort_by(field, direction="Ascending"):
    """Default sort order for a visual. Without one a table falls back to the
    first column, which left the standings sorted alphabetically by driver with
    the position column reading 15, 1, 11, 16 ..."""
    return {"sort": [{"field": field, "direction": direction}], "isDefaultSort": True}


def table(name, x, y, w, h, z, tab, projections, filters=None, title=None,
          image_height=None, image_width=560, hide_headers=False,
          column_widths=None, sort=None):
    # A grand total means nothing here - it would sum points across drivers.
    # The property is total.totals, not total.show.
    objects = {"total": [{"properties": {"totals": lit("false")}}]}
    if hide_headers:
        # There is no columnHeaders.show for tableEx - a table always shows its
        # headers. Desktop strips the property on save, so setting it only
        # produced a misleading diff. The blank displayName on the projection is
        # what actually keeps a card table's header quiet.
        objects["columnHeaders"] = [{"properties": {"fontSize": lit("9D")}}]
    if image_height:
        # imageHeight/imageWidth live on grid, not values - under values they
        # are silently ignored and the image renders at zero height.
        objects["grid"] = [{"properties": {
            "imageHeight": lit("%dD" % image_height),
            "imageWidth": lit("%dD" % image_width),
            "gridVertical": lit("false"),
            "gridHorizontal": lit("false"),
            "rowPadding": lit("4D"),
        }}]
    elif hide_headers:
        objects["grid"] = [{"properties": {
            "gridVertical": lit("false"),
            "gridHorizontal": lit("false"),
            "rowPadding": lit("6D"),
        }}]
    if column_widths:
        objects["columnWidth"] = [
            {"properties": {"value": lit("%sD" % width)},
             "selector": {"metadata": ref}}
            for ref, width in column_widths
        ]
    query = {"queryState": {"Values": {"projections": projections}}}
    if sort:
        query["sortDefinition"] = sort
    vis = {
        "visualType": "tableEx",
        "query": query,
        "objects": objects,
        "drillFilterOtherVisuals": True,
    }
    if title:
        vis["visualContainerObjects"] = {"title": [{"properties": {
            "show": lit("true"), "text": s_lit(title), "fontSize": lit("11D"),
            "fontColor": {"solid": {"color": lit("'%s'" % INK)}},
        }}]}
    return visual(name, x, y, w, h, z, tab, vis, filters)


def matrix(name, x, y, w, h, z, tab, rows, columns, values, title=None, filters=None):
    vis = {
        "visualType": "pivotTable",
        "query": {"queryState": {
            "Rows": {"projections": rows},
            "Columns": {"projections": columns},
            "Values": {"projections": values},
        }},
        "objects": {
            "grid": [{"properties": {
                "gridVertical": lit("true"),
                "gridHorizontal": lit("true"),
                "rowPadding": lit("2D"),
            }}],
            "values": [{"properties": {"fontSize": lit("9D")}}],
            "columnHeaders": [{"properties": {"fontSize": lit("9D")}}],
            "rowHeaders": [{"properties": {"fontSize": lit("9D")}}],
            "subTotals": [{"properties": {
                "rowSubtotals": lit("false"),
                "columnSubtotals": lit("false"),
            }}],
        },
        "drillFilterOtherVisuals": True,
    }
    if title:
        vis["visualContainerObjects"] = {"title": [{"properties": {
            "show": lit("true"), "text": s_lit(title), "fontSize": lit("11D"),
            "fontColor": {"solid": {"color": lit("'%s'" % INK)}},
        }}]}
    return visual(name, x, y, w, h, z, tab, vis, filters)


def card(name, x, y, w, h, z, tab, entity, prop, label):
    return visual(name, x, y, w, h, z, tab, {
        "visualType": "cardVisual",
        "query": {"queryState": {"Data": {"projections": [pmeas(entity, prop)]}}},
        "objects": {
            "cards": [{"properties": {
                "showLabel": lit("true"),
                "labelFontSize": lit("9D"),
            }}],
        },
        "visualContainerObjects": {"title": [{"properties": {
            "show": lit("true"), "text": s_lit(label), "fontSize": lit("10D"),
            "fontColor": {"solid": {"color": lit("'%s'" % FAINT)}},
        }}]},
        "drillFilterOtherVisuals": True,
    })


def latest_season():
    """Newest season present in the exported data. The Season slicer defaults to
    it, so the report opens on the current championship the way the HTML does -
    and adding 2027 only means re-running the export and this script.

    Deliberately tolerant about the header's case and the file's absence. This
    script ships from the `start` checkpoint, so it can be run before there is any
    exported data, and every participant's exporter names its columns differently -
    season, Season, SEASON have all been seen. Retargeting the FIELD references
    below is the chapter's exercise; guessing a CSV header is not, and a KeyError
    at import time would teach nothing.
    """
    path = os.path.join(HERE, "data", "Race.csv")
    if not os.path.isfile(path):
        sys.exit("no powerbi/data/Race.csv yet - the semantic model chapter writes "
                 "the CSVs this report reads. Run your exporter first.")
    with io.open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        sys.exit("powerbi/data/Race.csv has a header but no rows")
    col = next((k for k in rows[0] if k and k.strip().lower() == "season"), None)
    if not col:
        sys.exit("no season column in powerbi/data/Race.csv - found: %s"
                 % ", ".join(k for k in rows[0] if k))
    return max(int(r[col]) for r in rows if r[col])


SEASON = latest_season()


def selection(entity, prop, literal):
    """A slicer's SELECTED value.

    This lives on the slicer's own general.filter property - not in the visual's
    filterConfig. A categorical filter in filterConfig is the "Filters on this
    visual" well: it restricts which values the slicer lists and selects
    nothing, so no filter ever reaches the page. Shape verified against a
    Desktop-authored slicer."""
    src = entity[:1].lower()
    # Note the double nesting: the general.filter *property* holds an object
    # whose own "filter" key carries the semantic filter. One level less and
    # Desktop ignores it silently, which looks exactly like no selection.
    return {"filter": {"filter": {
        "Version": 2,
        "From": [{"Name": src, "Entity": entity, "Type": 0}],
        "Where": [{"Condition": {"In": {
            "Expressions": [{"Column": {
                "Expression": {"SourceRef": {"Source": src}}, "Property": prop}}],
            "Values": [[{"Literal": {"Value": literal}}]],
        }}}],
    }}}


# Sidebar geometry. Everything in the rail shares one left edge and width so the
# wordmark, nav labels, filter titles and footnote line up on a single margin.
RAIL_X, RAIL_W = 20, 188
NAV_BOTTOM = NAV_Y0 + NAV_STEP * (len(PAGES) - 1) + NAV_H   # 322 with six pages

# The FILTERS eyebrow plus a gap is what separates navigation from filters - the
# two do different things and previously ran together as one list.
#
# Two sizes here are load-bearing. The label needs 26px, not 20: a 7pt run in a
# 20px textbox gets clipped to fragments. And a slicer draws its title hard
# against its own top edge, so the eyebrow needs a real gap below it or the two
# title-weight rows collide.
FILTERS_LABEL_BOX = (RAIL_X, NAV_BOTTOM + 24, 190, 26)               # 346 - 372
SEASON_BOX = (RAIL_X, NAV_BOTTOM + 62, RAIL_W, slicer_height(2))     # 384 - 476
# Country takes the whole remaining rail rather than its derived height: 22
# items land within a pixel of the estimate, and the spare margin is what keeps
# a slightly larger real row pitch from bringing the scrollbar back.
_COUNTRY_Y = NAV_BOTTOM + 166
COUNTRY_BOX = (RAIL_X, _COUNTRY_Y, RAIL_W, H - _COUNTRY_Y - 24)      # 488 - 1056

# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------


def page_schedule():
    return sidebar("pg01Schedule") + header(
        "Schedule",
        "Every round of the season, with the next race and the completed ones marked."
    ) + [
        season_slicer(),
        card_grid("v30RaceCards", CX, BODY_Y, CW, H - BODY_Y, 2000, 50,
                  "Race", "Race Key", "Session Result", "Race Card (svg)", 3, 8,
                  sort=sort_by(col("Race", "Race Key"))),
    ]


def page_results():
    half = (CW - 24) // 2
    grid_y = BODY_Y + 372
    return sidebar("pg02Results") + header(
        "Results",
        "Round-by-round winners and pole sitters, and every driver's points per round."
    ) + [
        season_slicer(),
        table("v30Winners", CX, BODY_Y, half, 348, 2000, 50,
              # The measure is load-bearing, not decoration: with only dimension
              # columns from different tables, SUMMARIZECOLUMNS returns the full
              # cross join and the fact filter does not constrain it (552 rows
              # instead of 12). The measure must come from the same fact as the
              # filter - one from the other fact re-expands it.
              [pcol("Race", "Season"), pcol("Race", "Round"),
               pcol("Race", "Race Name"),
               pcol("Driver", "Driver Name"), pcol("Team", "Team Name"),
               pmeas("Session Result", "Points (pts)")],
              filters=[eq_filter("Session Result", "Position", "1L", 0),
                       eq_filter("Session", "Session", "'Race'", 1)],
              title="Race winners",
              sort=sort_by(col("Race", "Round"))),
        table("v31Poles", CX + half + 24, BODY_Y, half, 348, 2001, 51,
              [pcol("Race", "Season"), pcol("Race", "Round"),
               pcol("Race", "Race Name"),
               pcol("Driver", "Driver Name"), pcol("Team", "Team Name"),
               pmeas("Qualifying Result", "Poles (#)")],
              filters=[eq_filter("Qualifying Result", "Qualifying Position", "1L", 0)],
              title="Pole sitters",
              sort=sort_by(col("Race", "Round"))),
        # Runs to the very bottom edge: with the page seamless there is no page
        # boundary for a margin to sit against, so the reclaimed 32px goes to
        # the grid, which is the one visual here that is always cut off.
        matrix("v32PointsByRound", CX, grid_y, CW, H - grid_y, 2002, 52,
               [pcol("Driver", "Driver Name")],
               [pcol("Race", "Season"), pcol("Race", "Round")],
               [pmeas("Session Result", "Points By Round (txt)")],
               title="Points by round - the reason is shown where a driver was not classified"),
    ]


def page_driver_standings():
    return sidebar("pg03DriverStandings") + header(
        "Driver Standings",
        "Championship order, with points gained in the latest round in context."
    ) + [
        season_slicer(),
        country_slicer(),
        table("v30Standings", CX, BODY_Y, CW, H - BODY_Y, 2000, 50, [
            pmeas("Session Result", "Rank Drivers by Points (pos)", "Pos"),
            pcol("Driver", "Driver Name", "Driver"),
            pcol("Driver", "Driver Code", "Code"),
            # Team as a measure, not a column: a mid-season switcher would
            # otherwise occupy one standings row per team.
            pmeas("Session Result", "Team (txt)", "Team"),
            pmeas("Session Result", "Points (pts)"),
            pmeas("Session Result", "Points Δ RoR (pts)"),
            pmeas("Session Result", "Wins (#)"),
            pmeas("Session Result", "Podiums (#)"),
            pmeas("Qualifying Result", "Poles (#)"),
            pmeas("Session Result", "Average Finish (pos)"),
            pmeas("Qualifying Result", "Average Qualifying (pos)"),
        ], sort=sort_by(meas("Session Result", "Rank Drivers by Points (pos)"))),
    ]


def page_constructor_standings():
    return sidebar("pg04ConstructorStandings") + header(
        "Constructor Standings",
        "The same picture at team level, summing both cars."
    ) + [
        season_slicer(),
        country_slicer(),
        table("v30Standings", CX, BODY_Y, CW, H - BODY_Y, 2000, 50, [
            pmeas("Session Result", "Rank Teams by Points (pos)", "Pos"),
            pcol("Team", "Team Name", "Constructor"),
            pmeas("Session Result", "Points (pts)"),
            pmeas("Session Result", "Points Δ RoR (pts)"),
            pmeas("Session Result", "Wins (#)"),
            pmeas("Session Result", "Podiums (#)"),
            pmeas("Qualifying Result", "Poles (#)"),
            pmeas("Session Result", "Average Finish (pos)"),
        ], sort=sort_by(meas("Session Result", "Rank Teams by Points (pos)"))),
    ]


def page_drivers():
    return sidebar("pg05Drivers") + header(
        "Drivers",
        "One card per driver, in championship order. The API serves no photos, so the code leads."
    ) + [
        season_slicer(),
        card_grid("v30DriverCards", CX, BODY_Y, CW, H - BODY_Y, 2000, 50,
                  "Driver", "Driver Code", "Session Result", "Driver Card (svg)", 4, 6,
                  sort=sort_by(meas("Session Result", "Rank Drivers by Points (pos)"))),
    ]


def page_teams():
    return sidebar("pg06Teams") + header(
        "Teams",
        "One card per constructor in championship order, in its own livery colour."
    ) + [
        season_slicer(),
        card_grid("v30TeamCards", CX, BODY_Y, CW, H - BODY_Y, 2000, 50,
                  "Team", "Team Name", "Session Result", "Team Card (svg)", 3, 4,
                  sort=sort_by(meas("Session Result", "Rank Teams by Points (pos)"))),
    ]


BUILDERS = {
    "pg01Schedule": page_schedule,
    "pg02Results": page_results,
    "pg03DriverStandings": page_driver_standings,
    "pg04ConstructorStandings": page_constructor_standings,
    "pg05Drivers": page_drivers,
    "pg06Teams": page_teams,
}

# Adding a page is three edits - a tuple in PAGES, a builder function, an entry
# in BUILDERS - and two of the three already fail loudly if you forget them. A
# missing BUILDERS entry raises KeyError on the lookup below; a builder you never
# wrote raises NameError right here. The third fails SILENTLY: leave the PAGES
# tuple out and the loop simply never visits the page, the builder sits
# unreferenced, and the summary line reads exactly like a correct run. Run 5 did
# that, saw "6 pages ... 0 invalid", exit 0, and only noticed because somebody
# counted. Make the silent one loud, so all three behave the same way.
_orphan_pages = [p for p, _ in PAGES if p not in BUILDERS]
_orphan_builders = [b for b in BUILDERS if b not in {p for p, _ in PAGES}]
if _orphan_pages or _orphan_builders:
    sys.exit(
        "PAGES and BUILDERS disagree, so the report would be built wrong:\n"
        + "".join("  in PAGES with no builder:   %s\n" % p for p in _orphan_pages)
        + "".join("  in BUILDERS with no page:   %s\n" % b for b in _orphan_builders)
        + "every page needs a tuple in PAGES and an entry in BUILDERS, "
          "keyed by the same id.")


def write_json(path, payload):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def main():
    if not os.path.isdir(REPORT_DEF):
        raise SystemExit("report definition not found: %s" % REPORT_DEF)

    # Rebuild from scratch so removed visuals actually disappear.
    if os.path.isdir(PAGES_DIR):
        try:
            shutil.rmtree(PAGES_DIR)
        except OSError as exc:
            raise SystemExit(
                "cannot rewrite the report definition: %s\n"
                "Power BI Desktop still has the project open - close it first, "
                "then re-run this script and reopen the .pbip." % exc)
    os.makedirs(PAGES_DIR)

    total_visuals = 0
    for page_name, display in PAGES:
        page_dir = os.path.join(PAGES_DIR, page_name)
        visuals_dir = os.path.join(page_dir, "visuals")
        os.makedirs(visuals_dir)
        write_json(os.path.join(page_dir, "page.json"), {
            "$schema": P_SCHEMA,
            "name": page_name,
            "displayName": display,
            "displayOption": "FitToPage",
            "width": W,
            "height": H,
            # The canvas is fully TRANSPARENT and the wallpaper carries the
            # colour. An opaque canvas is drawn as a page floating on the
            # wallpaper, complete with the rounded edge and drop shadow;
            # letting the wallpaper show straight through is what removes
            # them. Painting both the same colour does not - the shadow is
            # drawn regardless of whether the two colours match.
            # Canvas fully transparent so the wallpaper shows straight through:
            # an opaque canvas is drawn as a page floating on the wallpaper and
            # keeps its drop shadow no matter how well the colours match. The
            # dotted outline this used to introduce is handled by the theme's
            # "Second-level elements" token - the two fixes only work together.
            "objects": {"background": [{"properties": {
                "color": colour(CANVAS),
                "transparency": lit("100D"),
            }}]},
        })
        vis = BUILDERS[page_name]()
        names = [v["name"] for v in vis]
        if len(names) != len(set(names)):
            raise SystemExit("duplicate visual name on %s" % page_name)
        for v in vis:
            vdir = os.path.join(visuals_dir, v["name"])
            os.makedirs(vdir)
            write_json(os.path.join(vdir, "visual.json"), v)
        total_visuals += len(vis)
        print("  %-26s %2d visuals" % (page_name, len(vis)))

    write_json(os.path.join(PAGES_DIR, "pages.json"), {
        "$schema": PM_SCHEMA,
        "pageOrder": [p for p, _ in PAGES],
        "activePageName": PAGES[0][0],
    })

    # Parse everything back to catch malformed output before Desktop sees it.
    bad = 0
    checked = 0
    for root, _dirs, files in os.walk(PAGES_DIR):
        for f in files:
            if f.endswith(".json"):
                p = os.path.join(root, f)
                checked += 1
                try:
                    json.load(io.open(p, encoding="utf-8"))
                except ValueError as exc:
                    bad += 1
                    print("  INVALID %s: %s" % (p, exc))
    print("%d pages, %d visuals, %d JSON files checked, %d invalid"
          % (len(PAGES), total_visuals, checked, bad))
    if bad:
        raise SystemExit("fix invalid JSON before opening in Desktop")


if __name__ == "__main__":
    main()

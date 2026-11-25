"""Pre-flight check for the Ultimate F1 Dashboard course.

Run this BEFORE the course day. Forty minutes of install debugging at 09:00
ruins a one-day class, and every prerequisite here is something that cannot be
fixed quickly on the morning: an install behind a proxy, a Desktop that needs a
restart, an authentication flow that needs a browser.

    python check_setup.py

Exit code 0 means you are ready. Anything else means read the output - each
failure says what to do about it.

This script only reads. It installs nothing, changes nothing, and needs no
network.
"""
import glob
import os
import platform
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results = []


def record(level, name, detail, fix=None):
    results.append((level, name, detail, fix))


def run(cmd):
    """Return (ok, first line of output). Never raises."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False, ""
    out = (p.stdout or p.stderr or "").strip().split("\n")
    return p.returncode == 0, out[0] if out and out[0] else ""


def run_lines(cmd):
    """Like run(), but every line rather than the first.

    run() returning one line is right for a version string and wrong for a
    list. Asking it for `git tag` yielded a single tag, so a repository with
    all five checkpoints present reported four of them missing - a check that
    fails a correctly configured machine, which is worse than no check."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False, []
    return p.returncode == 0, [l.strip() for l in (p.stdout or "").split("\n") if l.strip()]


# --------------------------------------------------------------------------

def check_python():
    v = sys.version_info
    got = "%d.%d.%d" % (v.major, v.minor, v.micro)
    if v >= (3, 9):
        record(PASS, "Python", got)
    else:
        record(FAIL, "Python", "%s - too old" % got,
               "Install Python 3.9 or newer from python.org, then re-run this "
               "with the new interpreter.")


def check_jsonschema():
    """Deliberately a FAIL, not a WARN.

    pbir_lint runs without jsonschema. It simply drops its schema layer and
    still prints a clean result - so a participant would pass a weaker check
    and never know. That is exactly the kind of silent degradation this course
    teaches people to distrust, so it must not be shipped in the setup."""
    try:
        import jsonschema                                    # noqa: F401
        try:                     # jsonschema.__version__ is deprecated and warns
            from importlib.metadata import version
            ver = version("jsonschema")
        except Exception:
            ver = "installed"
        record(PASS, "jsonschema", ver)
    except ImportError:
        record(FAIL, "jsonschema", "not installed",
               'Run:  %s -m pip install jsonschema\n'
               "        Without it pbir_lint still runs but silently checks "
               "less, which is worse than failing." % os.path.basename(sys.executable))


def check_git():
    ok, out = run(["git", "--version"])
    if ok:
        record(PASS, "git", out)
    else:
        record(FAIL, "git", "not found on PATH",
               "Install Git from git-scm.com. Checkpoint recovery during the "
               "day uses it, so this one is not optional.")


def check_claude():
    """Accept either the CLI or the desktop app.

    Both are fine for this course. An earlier version tested only for `claude`
    on PATH and failed a machine that had the desktop app installed and working
    - a pre-flight check that tells you to reinstall software you already have
    is worse than no check at all."""
    ok, out = run(["claude", "--version"])
    if ok:
        record(PASS, "Claude Code", "CLI - %s" % out)
    else:
        home = os.path.expanduser("~")
        app_dirs = [os.path.join(home, "AppData", "Roaming", "Claude"),
                    os.path.join(home, "AppData", "Local", "Programs", "Claude"),
                    os.path.join(home, "Library", "Application Support", "Claude")]
        if any(os.path.isdir(p) for p in app_dirs):
            record(PASS, "Claude Code", "desktop app")
        else:
            record(FAIL, "Claude Code", "neither the CLI nor the desktop app found",
                   "Install Claude Code. Either the CLI (`claude --version` must "
                   "work in a new terminal) or the desktop app is fine - the "
                   "course works with both.")
            return

    # Authentication cannot be proven without spending a request, so check for
    # the credential store instead and say plainly that this is weaker.
    home = os.path.expanduser("~")
    creds = [os.path.join(home, ".claude", ".credentials.json"),
             os.path.join(home, ".claude", "config.json"),
             os.path.join(home, ".claude.json")]
    if any(os.path.isfile(p) for p in creds):
        record(PASS, "Claude Code sign-in", "credentials present")
    else:
        record(WARN, "Claude Code sign-in", "no credential file found",
               "Open Claude Code once and complete the sign-in. This check only "
               "looks for the file, so treat a PASS here as 'probably fine' "
               "rather than proof.")


def check_npx():
    """Node is a real prerequisite now, and it is not implied by anything else.

    The semantic model chapter's second gate - "the model loads" - is answered by
    the Power BI Modeling MCP server, which .mcp.json starts with npx. Claude Code
    does NOT bring Node with it: the native installer puts `claude` in
    ~/.local/bin and never touches npm. So a machine can pass every other check
    here and still have no way to run that gate.

    A FAIL rather than a WARN, for the same reason as jsonschema: without it the
    gate does not fail, it silently does not exist.

    Resolved with shutil.which rather than by running it. On Windows npx is
    npx.CMD, and subprocess cannot launch a .cmd from a bare name without a
    shell - so `run(["npx", "--version"])` reports "not found on PATH" on a
    machine where npx is installed and working. That is the failure mode this
    file keeps having to be taught to avoid: a pre-flight check that tells you to
    install software you already have."""
    import shutil
    path = shutil.which("npx")
    if path:
        ok, out = run([path, "--version"])
        # The label said "npx (Node)" and printed NPX's version, which reads as
        # Node's. Somebody already made that mistake: run 1's environment row in
        # rehearsal-log.md records "Node 11.19.0", a version that reached
        # end-of-life in 2019 - it was npx 11.19.0 beside Node v24. Print both,
        # so the row cannot be misread. Node is resolved separately because a
        # machine can have npx on PATH without node beside it.
        node = shutil.which("node")
        if node:
            node_ok, node_out = run([node, "--version"])
            if node_ok:
                out = "npx %s, node %s" % (out, node_out)
        record(PASS, "npx + node", out if ok else path)
        return
    record(FAIL, "npx + node", "npx not found on PATH",
           "Install Node.js LTS from nodejs.org and re-open your terminal.\n"
           "        The semantic model chapter uses it to start the Power BI\n"
           "        Modeling MCP server, which is how you check that a model\n"
           "        loads without opening Desktop. Nothing else needs it.")


def check_mcp_declared():
    """The server has to be declared where Claude Code will look for it.

    Checked separately from npx because they fail differently: no Node means it
    cannot start, no .mcp.json means nothing asks it to."""
    p = os.path.join(HERE, ".mcp.json")
    if not os.path.isfile(p):
        record(FAIL, "MCP declared", ".mcp.json missing",
               "This ships with the repository. Re-clone, or check out a "
               "checkpoint again.")
        return
    try:
        import json
        with open(p) as fh:
            cfg = json.load(fh)
        srv = cfg.get("mcpServers", {}).get("powerbi-modeling-mcp")
        if not srv:
            record(FAIL, "MCP declared", "powerbi-modeling-mcp not in .mcp.json",
                   "The file is present but does not declare the server.")
            return
        pinned = [a for a in srv.get("args", []) if "powerbi-modeling-mcp@" in a]
        # Declared, not authenticated. Nothing here can tell whether the sign-in
        # has happened - that needs a browser and a running session - so the
        # label says "declared" and Before You Start carries the sign-in step.
        record(PASS, "MCP declared", pinned[0] if pinned else "declared, unpinned")
    except Exception as exc:
        record(FAIL, "MCP declared", ".mcp.json unreadable: %s" % exc,
               "It should be valid JSON. Re-clone if you have edited it.")


def check_desktop():
    if platform.system() != "Windows":
        record(WARN, "Power BI Desktop", "not checked on %s" % platform.system(),
               "Desktop is Windows-only. Chapters 04 and 05 need it.")
        return
    # The Store build lives under C:\Program Files\WindowsApps, which is
    # ACL-protected: listing it raises PermissionError for a normal user, so
    # globbing finds nothing even when Desktop is installed and working. Ask
    # the package manager instead, and keep the glob for the MSI build.
    ok, ver = run(["powershell.exe", "-NoProfile", "-Command",
                   "Get-AppxPackage -Name Microsoft.MicrosoftPowerBIDesktop "
                   "| Select-Object -ExpandProperty Version"])
    if ok and ver:
        record(PASS, "Power BI Desktop", "Microsoft Store build %s" % ver)
        check_store_pbip()
        return

    found = []
    for pat in (r"C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
                r"C:\Program Files (x86)\Microsoft Power BI Desktop\bin\PBIDesktop.exe"):
        found.extend(glob.glob(pat))
    if found:
        record(PASS, "Power BI Desktop", "installer build - %s" % found[0])
        return

    record(FAIL, "Power BI Desktop", "not found",
           "Install Power BI Desktop. Chapters 04 and 05 open it to check the "
           "numbers and the render.")


def check_store_pbip():
    """Test whether the Store package declares .pbip, rather than assume it.

    This used to WARN on every Store install that the build registers no .pbip
    association. That was a warning fired by what is installed, not by what is
    true: Desktop 2.159 (Store) declares .pbip in its package manifest and a
    double-click opens the project. `assoc .pbip` cannot see a packaged app's
    associations at all (it is just as blank for .pbix), so the manifest is
    what to read. WARN only when the manifest really leaves .pbip out."""
    ok, ans = run(["powershell.exe", "-NoProfile", "-Command",
                   "$p = Get-AppxPackage -Name Microsoft.MicrosoftPowerBIDesktop; "
                   "if ((Get-AppxPackageManifest $p).OuterXml -match "
                   "'uap:FileType>[.]pbip<') { 'yes' } else { 'no' }"])
    if ok and ans == "yes":
        record(PASS, "Desktop .pbip association", "declared by the Store package")
    elif ok and ans == "no":
        record(WARN, "Desktop .pbip association", "not declared by this Store build",
               "Double-clicking a .pbip may open a blank Untitled report with no "
               "error. Open projects with File > Open inside Desktop instead.")
    else:
        record(WARN, "Desktop .pbip association", "could not read the package manifest",
               "If a double-click on a .pbip ever opens a blank Untitled report, "
               "close it and use File > Open inside Desktop. Nothing is broken.")


def check_repo():
    if not os.path.isdir(os.path.join(HERE, ".git")):
        record(FAIL, "Teaching repo", "this folder is not a git clone",
               "Clone the course repository and run this script from inside it.")
        return
    record(PASS, "Teaching repo", HERE)

    _ok, tags = run_lines(["git", "-C", HERE, "tag", "-l"])
    # after-report-bug belongs on this list: without it chapter 06 has no
    # exercise, and that is not something to discover at 15:00 on the day.
    wanted = ["start", "after-data", "after-html", "after-model", "after-report",
              "after-report-bug"]
    missing = [t for t in wanted if t not in tags]
    if missing:
        record(FAIL, "Checkpoint tags", "missing: %s" % ", ".join(missing),
               "Run:  git fetch --tags\n"
               "        The tags are how you rejoin if a chapter goes wrong.")
    else:
        record(PASS, "Checkpoint tags", "%d present" % len(tags))


def check_vendored_tooling():
    wanted = {
        "scripts/pbir_lint.py": "the report linter",
        "scripts/tmdl_lint.py": "the model linter",
        "references/json-schemas": "the bundled Microsoft schemas",
        ".claude/skills": "the in2Facts skills",
    }
    missing = [p for p in wanted if not os.path.exists(os.path.join(HERE, p.replace("/", os.sep)))]
    if missing:
        record(FAIL, "Course tooling", "missing: %s" % ", ".join(missing),
               "These ship inside the repo - nothing to install. If they are "
               "absent the clone is incomplete or out of date: git pull.")
    else:
        record(PASS, "Course tooling", "linters, schemas and skills present")


def check_data():
    """Count the seasons, and say so if there are more than the repo ships.

    This used to PASS on any non-zero count. A stray data/raw-2024.json sat in a
    folder and reported "3 season snapshot(s)" as a pass, and everything
    downstream quietly changed with it: export_csv.py and build.py both discover
    seasons by globbing data/raw-*.json, so an extra file adds a season to every
    CSV, every total and every line of output. The data chapter's exercise prints
    exact figures on the grounds that the data is frozen, and those figures stop
    matching.

    A WARN, not a FAIL. The pinned files are the ones git tracks; an extra one is
    the participant's own, and the data chapter's second exercise invites them to
    think about exactly this, so somebody may have added one deliberately. What
    they need is to be told, not stopped.
    """
    raw = sorted(os.path.basename(p)
                 for p in glob.glob(os.path.join(HERE, "data", "raw-*.json")))
    if not raw:
        record(FAIL, "Course data", "data/raw-*.json not found",
               "The pinned data ships in the repo. If it is missing the clone "
               "is incomplete: git pull.")
        return

    ok, tracked = run_lines(["git", "-C", HERE, "ls-files", "data/raw-*.json"])
    pinned = sorted(os.path.basename(p) for p in tracked) if ok else []
    extra = [f for f in raw if pinned and f not in pinned]

    if extra:
        record(WARN, "Course data",
               "%d season(s), %d not from the repo: %s"
               % (len(raw), len(extra), ", ".join(extra)),
               "Those files are not part of the pinned data, and everything\n"
               "        reads the whole folder - so your exports, totals and\n"
               "        output will differ from the figures printed in the\n"
               "        manual. Move them elsewhere to follow the course as\n"
               "        written, or keep them and expect your own numbers.")
    else:
        record(PASS, "Course data", "%d season snapshot(s)" % len(raw))


def check_linters_actually_run():
    """The end-to-end check. Everything above can pass while this still fails."""
    lint = os.path.join(HERE, "scripts", "pbir_lint.py")
    if not os.path.isfile(lint):
        return
    ok, out = run([sys.executable, lint, "--help"])
    if ok:
        record(PASS, "Linters run", "pbir_lint responds")
    else:
        record(FAIL, "Linters run", "pbir_lint could not start",
               "Usually a Python version or a missing dependency. The line "
               "above this one normally says which.")


# --------------------------------------------------------------------------

def main():
    print("Ultimate F1 Dashboard - course pre-flight check")
    print("%s, Python %d.%d\n" % (platform.system(),
                                  sys.version_info.major, sys.version_info.minor))

    for fn in (check_python, check_jsonschema, check_git, check_claude,
               check_npx, check_mcp_declared, check_desktop, check_repo,
               check_vendored_tooling, check_data, check_linters_actually_run):
        try:
            fn()
        except Exception as exc:                      # never crash on a check
            record(FAIL, fn.__name__, "check itself failed: %s" % exc,
                   "Report this - the check is at fault, not necessarily you.")

    width = max(len(n) for _, n, _, _ in results)
    for level, name, detail, _ in results:
        print("  %-4s  %-*s  %s" % (level, width, name, detail))

    fixes = [(n, f) for lv, n, _, f in results if f and lv != PASS]
    if fixes:
        print("\n" + "-" * 68)
        for name, fix in fixes:
            print("\n%s" % name)
            for line in fix.split("\n"):
                print("  %s" % line)

    n_fail = sum(1 for lv, _, _, _ in results if lv == FAIL)
    n_warn = sum(1 for lv, _, _, _ in results if lv == WARN)
    print("\n" + "-" * 68)
    if n_fail:
        print("NOT READY - %d must be fixed%s."
              % (n_fail, ", %d worth reading" % n_warn if n_warn else ""))
        print("Fix these before the course day, not on it.")
    elif n_warn:
        print("READY - %d note(s) above worth reading, nothing blocking." % n_warn)
    else:
        print("READY - everything checks out.")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())

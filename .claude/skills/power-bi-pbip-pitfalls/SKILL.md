---
name: power-bi-pbip-pitfalls
description: in2Facts field notes on authoring PBIP projects by hand, covering TMDL syntax, validating a semantic model without opening Desktop, launching Desktop from a script, and what Desktop writes back into your files. Use this skill EVERY TIME you hand-edit TMDL, generate or regenerate a PBIP project, script Power BI Desktop, or commit a PBIP folder to git. Trigger phrases include 'TMDL error', 'UnknownKeyword', 'InvalidLineType', 'description is not a supported property', 'validate TMDL', 'ConnectFolder', 'pbip will not open', 'opens blank', 'Untitled Power BI Desktop', 'WinError 32', 'file in use by another process', 'pbi folder', 'gitignore pbip', or a PBIP diff where every file looks changed. Confirmed against Power BI Desktop 2.156, Microsoft Store build.
---

# PBIP Project Pitfalls

Findings from hand-authoring a PBIP project and driving Power BI Desktop from a
script. Confirmed against **Desktop 2.156, Microsoft Store build**; some of this
is build-specific.

---

## TMDL comment syntax is narrower than it looks

Three separate parse failures in a row came from this. TMDL accepts far less
than the surrounding formats suggest.

| Want | Correct | Wrong |
|---|---|---|
| Describe an object | `///` comment **above** the object | a `description:` property |
| A plain, non-doc comment | *there isn't one* | `//` |
| Comment a relationship | *not possible* | `///` — relationships have no Description in the object model |

Indentation is **tabs**.

```tmdl
	/// Championship points scored, summing race and sprint sessions.
	measure 'Points (pts)' = SUM('Session Result'[Points])
		formatString: #,##0.##
		displayFolder: 01 Base Measures
```

The errors you will see, in the order they appear as you fix each one:

```
UnknownKeyword    — description is not a supported property in the current context
InvalidLineType   — Unexpected line type: Other!    (this is the // comment)
```

---

## Validate TMDL without opening Desktop

The Power BI Modeling MCP's **`ConnectFolder`** parses a `*.SemanticModel`
directory and reports the **exact file, line and reason**:

```
ConnectFolder  folderPath: C:\...\Ultimate F1 Dashboard.SemanticModel
→ TMDL Format Error: Parsing error type - UnknownKeyword
  Document - './tables/Qualifying Result'   Line Number - 57
```

Far faster than a Desktop round-trip for syntax work. A successful connect
reports what loaded — `tablesLoaded`, `measuresLoaded`, `relationshipsLoaded` —
which is a cheap structural check as well.

**`pbi-cli` cannot do this.** It attaches to a *running* Desktop instance over
the local Analysis Services port and cannot author or parse a project from
nothing. Use it for live model work (`pbi dax execute`, `pbi measure get`,
`pbi table refresh`), not for validating files.

---

## A double-click on a `.pbip` can open a blank Untitled report

### Symptom

Double-clicking a `.pbip`, or handing it to a launcher, opens a **blank Untitled
report** — with no error at all. Seen on 2.156 (Store). On 2.159 (Store) a
double-click opens the project normally.

### Do not diagnose it with `assoc`

`assoc .pbip` returns nothing on a Store install, but so does `assoc .pbix`: it
cannot see a packaged app's associations. Read the package manifest instead:

```powershell
(Get-AppxPackageManifest (Get-AppxPackage -Name Microsoft.MicrosoftPowerBIDesktop)).OuterXml -match 'uap:FileType>[.]pbip<'
```

`True` means the build declares `.pbip`. Do not tell anyone the association is
missing without this check.

### Rule

If it opens blank, pass the path directly to the executable:

```
C:\Program Files\WindowsApps\Microsoft.MicrosoftPowerBIDesktop_<version>_x64__8wekyb3d8bbwe\bin\pbidesktop.exe  "<path>\Project.pbip"
```

or use **File → Open** inside Desktop.

Cold start is slow — allow a minute before concluding it failed. Poll for the
window title rather than sleeping a fixed interval.

---

## Close Desktop before regenerating, and guard the rmtree

Desktop holds a lock on the report definition:

```
WinError 32 — The process cannot access the file because it is being used by another process
```

A generator that rebuilds pages from scratch **will delete hand-built work**.
Two habits:

- Catch the `OSError` and print an instruction, not a stack trace:
  *"Power BI Desktop still has the project open — close it first, then re-run."*
- **Commit any hand-built visual verbatim before running the generator.** When
  you need a working example from Desktop's UI, that commit is the only copy.

---

## Desktop writes UI state back into the report definition

Merely opening a project produces changes on disk. Seen in practice:

- A **slicer selection** persisted into `visual.json` as `filterConfig` plus
  `objects.general.filter` — a click on a tile in a Button Slicer card grid
- **`activePageName`** rewritten in `pages.json` to whatever page was last shown
- `$schema` bumped to Desktop's own `visualContainer` version
- `z` / `tabOrder` renumbered, keys reordered, trailing newline dropped

### Rule

**Diff semantically before committing after a Desktop session** — compare parsed
JSON, not text. Key reordering alone makes nearly every file look changed:

```python
json.loads(git_show_head_version) != json.loads(current_file)
```

On a 102-file diff this reduced it to the 2 files that had actually changed.

Treat what Desktop *removed* as a free validation signal: those properties were
invalid.

---

## Gitignore `.pbi/` with an unanchored pattern

```gitignore
# Correct — matches at any depth
.pbi/

# Never matches: * does not cross a path separator
*.Report/.pbi/
```

`.pbi/` holds per-machine UI settings (`localSettings.json`) and a binary model
cache (`cache.abf`). Neither belongs in the repo.

Keep `diagramLayout.json` tracked — it is the model diagram arrangement and is
worth sharing.

---

## A PBIP diff where every file looks changed is usually line endings

Open a PBIP project in Desktop and save, and `git status` can list a dozen files
as modified while `git diff` shows one or two. That is not corruption and it is
not Desktop rewriting everything: it is **CRLF**.

Desktop writes Windows line endings. A repository with `* text=auto eol=lf` in
`.gitattributes` stores LF, so git's clean filter converts the working tree back
to LF before comparing — the content matches, and `git diff` correctly shows
nothing. The files still appear in `git status` because their size on disk no
longer matches the index entry, which is what git checks first.

**Do not reason about it. Ask git, with the one command that answers:**

```powershell
git ls-files --eol -- "path/to/file.json"
```

```text
i/lf    w/crlf  attr/text eol=lf       definition.pbir
```

`i/` is the index, `w/` is the working tree, `attr/` is the rule being applied.
`i/lf w/crlf` with an `eol=lf` attribute means the difference is line endings
alone and the content is identical. If `i/` and `w/` agree, the modification is
something else and this is not your answer.

To clear the noise once the content is confirmed identical:

```powershell
git add --renormalize .
```

**Why this earns a section.** The failure mode is not the diff, it is the
explanation. Faced with twelve modified files and two diffs, it is easy to
produce a fluent account that fits half the evidence — "git does not count CRLF
as a change, so those files are missing from `--stat`" explains the empty diff
and contradicts the `git status` listing that prompted the question. One
command settles what a paragraph of reasoning cannot.

**What it is not.** This is only line endings. Desktop genuinely does rewrite
report definition files on save — see *Desktop writes UI state back into the
report definition* above — and those changes are real content and will show in
`git diff`. The two happen together, which is exactly why the eol check is worth
running before deciding which you are looking at.

## Related skills

- `power-bi-dax-pitfalls` — the model-side traps that fail silently
- `pbi-report-builder` — PBIR report JSON, and its own silent failure modes
- `pbip-dependency-analyzer` — what breaks if you delete something

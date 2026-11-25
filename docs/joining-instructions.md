# Before you arrive

Check the items below before the course — there's no time to fix installs
on the day.

## Overview

| What | Check | Why |
| --- | --- | --- |
| Claude Code, authenticated | Installed, logged in, responds to `claude --version` | The course runs through it |
| Python 3.9+ | `python --version` shows 3.9 or newer | Runs the course's helper tools |
| `jsonschema` | Loads without error | Needed for full file error-checking |
| git | Installed | Lets you undo mistakes / reset to a checkpoint |
| Node.js LTS | `npx --version` shows a number | Starts the Power BI model checker used in the semantic model chapter |
| Teaching repo, cloned | Folder downloaded, checkpoint tags present | Ships all other tooling |
| Power BI Desktop | Installed, opens, two options set (below) | Needed for two chapters |

## How to check each one

All steps use **PowerShell**: press the Windows key, type `PowerShell`,
open it. Copy and paste each command shown below into that window, then
press Enter. Nothing below deletes or changes anything — worst case you see
an error and ask for help.

### 1. Claude Code

```powershell
claude --version
```

Expect a version number. Then open Claude Code and confirm you're signed
in, not shown a login screen (the desktop app is fine too instead of the
command line).

**If "not recognized":** in the same PowerShell window, copy and paste this,
then press Enter:

```powershell
Test-Path "$env:USERPROFILE\.local\bin\claude.exe"
```

- `False` → install it:
  ```powershell
  irm https://claude.ai/install.ps1 | iex
  ```
- `True` → it's installed but not found yet. Copy and paste these two lines
  one at a time, pressing Enter after each:
  ```powershell
  $currentPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
  ```
  ```powershell
  [Environment]::SetEnvironmentVariable('PATH', "$currentPath;$env:USERPROFILE\.local\bin", 'User')
  ```
- Either way: close the PowerShell window, open a new one, retry.

### 2. Python 3.9+

```powershell
python --version
```

Expect `Python 3.x.x` with x ≥ 9.

**If it fails:** in the same PowerShell window, copy and paste this, then
press Enter:

```powershell
Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python" -Filter python.exe -Recurse -ErrorAction SilentlyContinue | Select-Object FullName
```

- Prints a path (e.g. `...\Python313\python.exe`) → installed, not found
  yet. Copy and paste these two lines one at a time, pressing Enter after
  each (swap in your folder name):
  ```powershell
  $currentPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
  ```
  ```powershell
  [Environment]::SetEnvironmentVariable('PATH', "$currentPath;$env:LOCALAPPDATA\Programs\Python\Python313", 'User')
  ```
- Prints nothing → not installed. Get it from
  [python.org](https://python.org) — it's free, and the default install
  option ("Install Now") installs just for you, no administrator rights
  needed. Tick **"Add python.exe to PATH"** on the first install screen.
- Either way: close the PowerShell window, open a new one, retry.

### 3. `jsonschema`

```powershell
python -m pip show jsonschema
```

Expect version details, no error.

**If it fails:** it's free, and installs into your own Python setup — no
administrator rights needed:

```powershell
python -m pip install jsonschema
```

then retry.

### 4. git

Just the software — no GitHub account or repository of your own needed.

```powershell
git --version
```

Expect something like `git version 2.44.0`.

**If it fails:** install from [git-scm.com](https://git-scm.com) — it's free,
and no administrator rights are needed (choose "Only for me" if the
installer asks). Defaults are fine otherwise. Then retry in a new terminal
window.

### 5. Node.js

You will never write any JavaScript on this course. Node is here for one job: in
the semantic model chapter it starts a small Microsoft program that checks your
Power BI model
loads correctly, without you having to open Power BI Desktop to find out. That
check saves a great deal of waiting, which is why it is worth one install.

```powershell
npx --version
```

Expect a number such as `10.9.2`.

**If it fails:** install the **LTS** version from
[nodejs.org](https://nodejs.org) — free, and the default options are correct.
Close your terminal window and open a new one afterwards, or the change to your
PATH will not have taken effect yet.

**Note for a corporate machine:** the first time that check runs, it
downloads the Microsoft program from the internet. It is about 40 MB and happens
once. If your network blocks it, tell us before the course rather than on the
day.

### 6. Course material, cloned

This is the folder you will work in all day. Getting it is two commands, and
they work from wherever PowerShell happens to be open.

1. Copy and paste this, then press Enter. It takes a few seconds.

   ```powershell
   git clone https://github.com/in2facts/in2fa-matl-pbi-with-claude.git C:\training\in2fa-matl-pbi-with-claude
   ```

   The path on the end is where the folder goes. `C:\training` does not need to
   exist first — git creates it. Please use exactly this location: the course
   manual assumes it, and a short path outside OneDrive avoids a whole class of
   problem on the day.

2. Move into the folder:

   ```powershell
   cd C:\training\in2fa-matl-pbi-with-claude
   ```

   Check it worked by looking at the text before the `>` in PowerShell:

   ```
   PS C:\training\in2fa-matl-pbi-with-claude>
   ```

   Nearly every command in the course must run from inside this folder. If you
   are somewhere else, git answers `fatal: not a git repository`, which always
   means the same thing — wrong folder, not a wrong command.

3. Confirm the checkpoints came with it:

   ```powershell
   git tag
   ```

   Expect six lines: `start`, `after-data`, `after-html`, `after-model`,
   `after-report`, `after-report-bug`. These are the recovery points the course uses
   whenever something goes wrong, so they matter.

**If `git tag` prints nothing:** still inside the folder, run

```powershell
git fetch --tags
```

and try `git tag` again.

**If you already have the folder from somewhere else** — a USB stick, a zip file
— check that it is a real clone and not an extracted copy. Open it in File
Explorer, turn on "Show hidden items" (View menu) and look for a `.git` folder.
No `.git` means it was unzipped, the checkpoints are missing, and the recovery
the course relies on will not work. Rename that folder to keep anything you have
started, then follow step 1 above.

No GitHub account or sign-in is needed to clone it. If the clone is refused, the
repository has not been opened up yet — tell us rather than trying to work
around it.

### 7. Power BI Desktop

Open it as usual; confirm no errors, note the version (Help > About).

Then set two options, once. Both are under **File > Options and settings >
Options**, in the **Global** section on the left:

| Option | Where | Set it to | Why |
| --- | --- | --- | --- |
| **Enhanced DAX Time Intelligence** | Preview features | Ticked | Your agent may build calendar-based time intelligence in the semantic model chapter, and Desktop opens such a model only with this preview on |
| **Auto date/time for new files** | Data Load, under Time intelligence | Unticked | Left on, Desktop adds a hidden date table behind every date column, on top of the one you build |

Click **OK**, then close and reopen Desktop: a preview feature only takes effect
after a restart. To verify, open the same dialog again and check both boxes are
as in the table. `check_setup.py` cannot check these for you: they live in
Desktop's own settings, not in the repository.

**If a double-click ever opens a blank *Untitled* report** instead of the
project, with no error, close it and use **File > Open** inside Desktop —
nothing is broken. `check_setup.py` reports whether your build declares the
`.pbip` association.

**If it fails:** install from the Microsoft Store or
[powerbi.microsoft.com](https://powerbi.microsoft.com).

## Also worth knowing

- **You do need internet during the course** — Claude Code sends your
  prompts to Anthropic's servers, so it won't work offline. The season data
  needs nothing beyond the initial download, but the semantic model chapter
  fetches a small
  Microsoft program once, the first time it checks your model (about 40 MB).
  So two things reach the internet during the day rather than one, and both
  matter on a locked-down company network.
- **Time/space:** all of the above is small and quick — well under half an
  hour if everything goes cleanly.
- **Still stuck?** Contact **Alain Pieters (in2Facts)**,
  [alain@in2facts.com](mailto:alain@in2facts.com), ideally a few days
  before the course.

"""Opt-in conversion of a slide app file to a one-slide-per-page PDF, by driving PowerPoint or Keynote.

The skill only calls this when the person asks for automatic conversion; exporting the PDF yourself is the default.
"""
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .detect import RefusedError

MAC_APPS = {"PowerPoint": Path("/Applications/Microsoft PowerPoint.app"), "Keynote": Path("/Applications/Keynote.app")}
TIMEOUT = 300
OLD_TEMP = 24 * 3600
EXPORT_YOURSELF = "export a PDF from your slide app instead, one slide per page, as the guide shows"
PERMISSION = ("macOS did not allow Claude to control {app}. To allow it, open System Settings, Privacy and Security, "
              "Automation, and turn on {app} under the app you run Claude Code in. Or export the PDF yourself, as the guide shows.")
MAC_SCRIPTS = {
    "PowerPoint": """on run argv
	with timeout of 300 seconds
		tell application "Microsoft PowerPoint"
			open POSIX file (item 1 of argv)
			set p to active presentation
			save p in POSIX file (item 2 of argv) as save as PDF
			close p saving no
		end tell
	end timeout
end run""",
    "Keynote": """on run argv
	with timeout of 300 seconds
		tell application "Keynote"
			launch
			delay 2
			set d to open POSIX file (item 1 of argv)
			export d to POSIX file (item 2 of argv) as PDF with properties {PDF image quality:Best, skipped slides:false}
			close d saving no
		end tell
	end timeout
end run""",
}
WINDOWS_SCRIPT = """param([string]$Src, [string]$Out)
$app = New-Object -ComObject PowerPoint.Application
$deck = $app.Presentations.Open($Src, $true, $false, $false)
$deck.SaveAs($Out, 32)
$deck.Close()
"""


def find_converters() -> list:
    if sys.platform == "darwin":
        return [name for name, path in MAC_APPS.items() if path.exists()]
    if sys.platform == "win32":
        import winreg
        try:
            winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "PowerPoint.Application")
            return ["PowerPoint"]
        except OSError:
            return []
    return []


def sweep_old_temp(now: float | None = None) -> None:
    """Remove this plugin's temporary folders that are more than a day old, and nothing else."""
    now = now or time.time()
    for folder in Path(tempfile.gettempdir()).glob("slide-handouts-*"):
        try:
            if folder.is_dir() and now - folder.stat().st_mtime > OLD_TEMP:
                shutil.rmtree(folder, ignore_errors=True)
        except OSError:
            pass


def _run(app: str, src: Path, out: Path) -> subprocess.CompletedProcess:
    # Paths go in as arguments, never pasted into the script text.
    if sys.platform == "win32":
        script = out.parent / "convert.ps1"
        script.write_text(WINDOWS_SCRIPT, encoding="utf-8")
        command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), str(src), str(out)]
        return subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT)
    return subprocess.run(["osascript", "-", str(src), str(out)], input=MAC_SCRIPTS[app],
                          capture_output=True, text=True, timeout=TIMEOUT)


def _landing(src: Path) -> Path:
    """A name beside the deck that cannot be an existing file. Sandboxed PowerPoint and Keynote can write
    where the deck already is, but not to the system temp folder."""
    while True:
        path = src.with_name(f"{src.stem} (slide-handouts conversion {secrets.token_hex(3)}).pdf")
        if not path.exists():
            return path


def convert(src: Path) -> tuple:
    """Return (PDF inside a new temporary folder, app name). Nothing is left or replaced beside the source."""
    src = Path(src).resolve()
    if not src.exists():
        raise RefusedError(f"{src.name} was not found.")
    apps = find_converters()
    if src.suffix.lower() == ".key":
        apps = [a for a in apps if a == "Keynote"]
    if not apps:
        raise RefusedError(f"No app that can convert {src.name} is installed here, so {EXPORT_YOURSELF}.")
    sweep_old_temp()
    work = Path(tempfile.mkdtemp(prefix="slide-handouts-"))
    out = work / f"{src.stem}.pdf"
    errors = []
    for app in apps:
        landing = _landing(src)
        try:
            result = _run(app, src, landing)
        except subprocess.TimeoutExpired:
            result = None
            errors.append(f"{app} did not finish within {TIMEOUT} seconds. It may be waiting for you to allow "
                          "access to the folder, in a Grant File Access window")
        if landing.exists():
            shutil.move(str(landing), str(out if result and result.returncode == 0 else work / landing.name))
        if result is None:
            continue
        if result.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return out, app
        text = (result.stderr or result.stdout or "").strip()
        if "-1743" in text or "Not authorized to send Apple events" in text:
            raise RefusedError(PERMISSION.format(app=app))
        errors.append(f"{app}: {text or 'no PDF was written'}")
    raise RefusedError(f"Could not convert {src.name} ({'; '.join(errors)}), so {EXPORT_YOURSELF}.")

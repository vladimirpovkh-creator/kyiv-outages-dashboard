"""Syntax-check all inline dashboard JavaScript using the GitHub runner's Node.js."""
from html.parser import HTMLParser
from pathlib import Path
import subprocess

class InlineScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and "src" not in dict(attrs):
            self.active = True
            self.scripts.append("")

    def handle_data(self, data):
        if self.active:
            self.scripts[-1] += data

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

parser = InlineScripts()
parser.feed((Path(__file__).resolve().parent.parent / "index.html").read_text(encoding="utf-8"))
if not parser.scripts:
    raise RuntimeError("No inline scripts found")
for i, script in enumerate(parser.scripts, 1):
    if not script.strip():
        continue
    proc = subprocess.run(["node", "--check"], input=script, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"Inline JS block {i} failed syntax check: {proc.stderr}")
print(f"Syntax OK: {len(parser.scripts)} inline scripts")

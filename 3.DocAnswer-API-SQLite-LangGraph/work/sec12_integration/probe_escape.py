"""Confirm what the rendered page actually contains, without shell quoting interference."""
import io
from pathlib import Path

page = io.open("deliverables/answer_view.html", encoding="utf-8").read()
needle = "<script>alert"
print("needle:", needle)
print("present:", needle in page)
print("double escaped:", "&lt;" in page)
index = page.find("alert")
print("context:", repr(page[index - 40:index + 30]))
print("raw script tag count:", page.count("<script>alert"))

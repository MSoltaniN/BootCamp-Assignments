"""Quick probe: how many pages and extractable characters does each PDF fixture have?"""
from pathlib import Path

from pypdf import PdfReader

for pdf in sorted(Path("datasets/01_Corpus/pdf_fixtures").glob("*.pdf")):
    reader = PdfReader(str(pdf))
    texts = [(page.extract_text() or "") for page in reader.pages]
    print(pdf.name, "pages:", len(reader.pages), "chars:", sum(len(t) for t in texts),
          "per_page:", [len(t) for t in texts])

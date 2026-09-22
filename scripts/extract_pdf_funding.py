import os
import fitz  # PyMuPDF

pdf_path = None
for root, dirs, files in os.walk("."):
    for f in files:
        if "GG1633934" in f and "application" in f.lower() and f.endswith(".pdf"):
            pdf_path = os.path.join(root, f)
            break
    if pdf_path:
        break

print("Found PDF path:", pdf_path)
if pdf_path:
    doc = fitz.open(pdf_path)
    full_text = "\n".join([page.get_text() for page in doc])
    lines = full_text.splitlines()
    for i, line in enumerate(lines):
        if any(term in line.lower() for term in ("5150", "4250", "ddf", "world fund", "financing", "contributions", "sources of funding")):
            start = max(0, i - 4)
            end = min(len(lines), i + 8)
            print(f"--- Line {i} ---")
            for j in range(start, end):
                print(f"  {lines[j]}")


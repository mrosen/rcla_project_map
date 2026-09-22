import fitz

doc = fitz.open("/home/msr/rcla_project_map/projects/GG1633934/GG1633934_Application.pdf")
for i, page in enumerate(doc):
    txt = page.get_text()
    for line in txt.splitlines():
        if any(term in line.lower() for term in ("financing", "budget summary", "fund summary", "contributions summary", "sources of funding", "district designated fund")):
            print(f"Page {i+1}: {line}")


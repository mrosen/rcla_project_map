import fitz

doc = fitz.open("/home/msr/rcla_project_map/projects/GG1633934/GG1633934_Application.pdf")
for i, page in enumerate(doc):
    txt = page.get_text()
    if any(k in txt.lower() for k in ("financing", "budget", "funding", "contributions", "world fund")):
        print(f"\n=================== PAGE {i+1} ===================")
        print(txt)


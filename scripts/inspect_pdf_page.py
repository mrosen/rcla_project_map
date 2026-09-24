import fitz

doc = fitz.open("/home/msr/rcla_project_map/projects/GG2091778/GG2091778_Application.pdf")
for i in range(min(3, len(doc))):
    print(f"=== PAGE {i+1} ===")
    print(doc[i].get_text())


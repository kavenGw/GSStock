import re
D = r"C:\Users\kaven\AppData\Local\Temp\claude\D--Git-stock\fd1e95ea-a731-4d24-9be7-a25651cc0a6f\scratchpad"
t = open(D + r"\H1_2026_report.txt", encoding="utf-8").read()
parts = re.split(r'<<<PAGE (\d+)>>>', t)
pages = {int(parts[i]): parts[i+1] for i in range(1, len(parts), 2)}
for n in (92, 93, 109):
    print("===== PAGE %d =====" % n)
    print(pages[n])

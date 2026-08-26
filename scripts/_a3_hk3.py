D = r"C:\Users\kaven\AppData\Local\Temp\claude\D--Git-stock\fd1e95ea-a731-4d24-9be7-a25651cc0a6f\scratchpad"
lines = open(D + r"\hd_hk_a1.txt", encoding="utf-8").read().split("\n")
print("\n".join(lines[5140:5195]))
print("\n@@@@@@@@@@ search 用途/計劃 @@@@@@@@@@")
for i,l in enumerate(lines):
    if ("用途" in l and "[編纂]" in l) or "未來計劃" in l:
        print(i, l.strip()[:160])

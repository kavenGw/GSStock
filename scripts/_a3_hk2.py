D = r"C:\Users\kaven\AppData\Local\Temp\claude\D--Git-stock\fd1e95ea-a731-4d24-9be7-a25651cc0a6f\scratchpad"
lines = open(D + r"\hd_hk_a1.txt", encoding="utf-8").read().split("\n")
for a,b,lbl in [(7100,7260,"CAPACITY"),(2370,2400,"CAP2"),(5150,5185,"FUNDS"),(3795,3820,"CAP3")]:
    print("========== %s (L%d-%d) ==========" % (lbl,a,b))
    print("\n".join(lines[a:b]))

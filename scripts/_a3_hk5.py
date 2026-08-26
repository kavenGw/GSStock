D = r"C:\Users\kaven\AppData\Local\Temp\claude\D--Git-stock\fd1e95ea-a731-4d24-9be7-a25651cc0a6f\scratchpad"
lines = open(D + r"\hd_hk_a1.txt", encoding="utf-8").read().split("\n")
for kw in ["高速網絡交換機","AI服務器","五大客戶","最大客戶","毛利率","1.6T","800G","3.2T","CPO","共封裝"]:
    idx = [i for i,l in enumerate(lines) if kw in l]
    print("### %-12s %3d hits: %s" % (kw, len(idx), idx[:16]))

import re
D = r"C:\Users\kaven\AppData\Local\Temp\claude\D--Git-stock\fd1e95ea-a731-4d24-9be7-a25651cc0a6f\scratchpad"
t = open(D + r"\hd_hk_a1.txt", encoding="utf-8").read()
print("LEN", len(t))
lines = t.split("\n")
for kw in ["產能利用率","产能利用率","利用率","所得款項用途","募集資金","募资","設計產能","设计产能"]:
    idx = [i for i,l in enumerate(lines) if kw in l]
    print("### %s -> %d hits: %s" % (kw, len(idx), idx[:12]))

D = r"C:\Users\kaven\AppData\Local\Temp\claude\D--Git-stock\fd1e95ea-a731-4d24-9be7-a25651cc0a6f\scratchpad"
lines = open(D + r"\hd_hk_a1.txt", encoding="utf-8").read().split("\n")
import re
# find revenue-by-application table: look for lines with 高速網絡交換機 near numeric columns
for i,l in enumerate(lines):
    if "高速網絡交換機" in l and i>9500:
        print(i, "|", l.strip()[:140])
print("---- print 9930-10010 ----")
print("\n".join(lines[9930:10010]))

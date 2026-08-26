D = r"C:\Users\kaven\AppData\Local\Temp\claude\D--Git-stock\fd1e95ea-a731-4d24-9be7-a25651cc0a6f\scratchpad"
lines = open(D + r"\hd_hk_a1.txt", encoding="utf-8").read().split("\n")
print("=========== 客户集中度 L7705-7740 ===========")
print("\n".join(lines[7705:7742]))
print("\n=========== 分应用收入 L9130-9200 ===========")
print("\n".join(lines[9130:9200]))

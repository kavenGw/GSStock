import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import urllib.request
raw = urllib.request.urlopen('http://qt.gtimg.cn/q=sz002851', timeout=10).read().decode('gbk')
f = raw.split('"')[1].split('~')
print('name=', f[1], 'price=', f[3], 'prev=', f[4], 'PE_TTM=', f[39], 'mktcap_yi=', f[45], 'PB=', f[46])

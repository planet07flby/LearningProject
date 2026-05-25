# SEFetch/tests/test_fetcher.py
import sys
from pathlib import Path

# 将 sharpedge 根目录加入搜索路径（向上两级：tests -> SEFetch -> sharpedge）
sys.path.insert(0, str(Path(__file__).parent.parent))

from SEFecth import get_data

print(get_data(code='000001', start='20200101', end='20200131', adj='qfq', package='bs').head())
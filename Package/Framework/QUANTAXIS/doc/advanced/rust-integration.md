# Rust集成

**版本**: 2.1.0-alpha2
**作者**: @yutiansut @quantaxis
**更新日期**: 2025-10-25

QUANTAXIS 2.1.0引入了Rust集成，通过QARS2（QUANTAXIS Rust）实现100倍性能提升。

---

## 🚀 核心优势

### 性能提升

- **数据处理**: 100x faster than pure Python
- **指标计算**: 向量化计算，SIMD优化
- **内存效率**: 更低的内存占用

### 主要组件

- **qars2**: Rust核心库
- **PyO3绑定**: Python-Rust互操作
- **Apache Arrow**: 零拷贝数据交换

---

## 📦 安装

```bash
# 安装QARS2
pip install qars2

# 或从源码编译
git clone https://github.com/QUANTAXIS/QARS2.git
cd QARS2
cargo build --release
```

---

## 💡 使用示例

### 1. 高性能数据处理

```python
import qars2
import pandas as pd

# 传统方式
data = pd.read_csv('stock_data.csv')
ma = data['close'].rolling(20).mean()  # 慢

# Rust加速方式
ma_fast = qars2.ma(data['close'].values, 20)  # 100x faster
```

### 2. QADataFrame集成

```python
from QUANTAXIS import QA_DataStruct_Stock_day
import qars2

# 加载数据
data = QA.QA_fetch_stock_day('000001', '2020-01-01', '2024-12-31')

# 使用Rust计算指标
df_rust = qars2.QADataFrame(data)
ma5 = df_rust.ma(5)
ma20 = df_rust.ma(20)
```

### 3. 因子计算

```python
# Python方式（慢）
def calculate_momentum(df, period=20):
    return (df['close'] / df['close'].shift(period) - 1) * 100

# Rust方式（快）
momentum = qars2.momentum(df['close'].values, period=20)
```

---

## 🔧 高级特性

### Arrow格式数据交换

```python
import pyarrow as pa
import qars2

# 转换为Arrow Table（零拷贝）
arrow_table = pa.Table.from_pandas(df)

# Rust处理
result = qars2.process_arrow(arrow_table)

# 转回Pandas
result_df = result.to_pandas()
```

### 并行计算

```python
# 多标的并行计算
codes = ['000001', '000002', '600000']
results = qars2.parallel_process(codes, func=calculate_indicators)
```

---

## 📊 性能对比

| 操作 | Python | Rust | 加速比 |
|------|--------|------|--------|
| MA计算 | 100ms | 1ms | 100x |
| 数据加载 | 500ms | 10ms | 50x |
| 因子计算 | 1000ms | 15ms | 67x |

---

## 🔗 相关资源

- **QARS2项目**: https://github.com/QUANTAXIS/QARS2
- **性能优化**: [性能优化指南](performance-tuning.md)

---

**作者**: @yutiansut @quantaxis
**最后更新**: 2025-10-25

[返回高级功能](../README.md)

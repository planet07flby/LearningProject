# 测试指南

**版本**: 2.1.0-alpha2
**作者**: @yutiansut @quantaxis
**更新日期**: 2025-10-25

本文档介绍QUANTAXIS的测试体系，包括单元测试、集成测试和策略测试。

---

## 🎯 测试体系概览

### 测试金字塔

```
        ┌─────────────┐
        │  E2E测试    │  少量
        ├─────────────┤
        │  集成测试    │  适量
        ├─────────────┤
        │  单元测试    │  大量
        └─────────────┘
```

### 测试类型

1. **单元测试**: 测试单个函数/类
2. **集成测试**: 测试模块间交互
3. **策略测试**: 测试交易策略
4. **性能测试**: 测试系统性能
5. **回归测试**: 确保向后兼容

---

## 🧪 单元测试

### 1. 使用pytest

```python
# tests/test_datafetch.py
import pytest
import pandas as pd
import QUANTAXIS as QA


class TestDataFetch:
    """数据获取测试"""
    
    def test_fetch_stock_day(self):
        """测试获取股票日线"""
        data = QA.QA_fetch_stock_day(
            code='000001',
            start='2024-01-01',
            end='2024-01-31'
        )
        
        assert data is not None
        assert isinstance(data, pd.DataFrame)
        assert len(data) > 0
        assert 'open' in data.columns
        assert 'close' in data.columns
    
    def test_fetch_invalid_code(self):
        """测试无效代码"""
        data = QA.QA_fetch_stock_day(
            code='INVALID',
            start='2024-01-01',
            end='2024-01-31'
        )
        
        assert data is None or len(data) == 0
    
    @pytest.mark.parametrize("code,expected", [
        ('000001', True),
        ('600000', True),
        ('INVALID', False)
    ])
    def test_multiple_codes(self, code, expected):
        """参数化测试多个股票代码"""
        data = QA.QA_fetch_stock_day(code, '2024-01-01', '2024-01-31')
        
        if expected:
            assert data is not None and len(data) > 0
        else:
            assert data is None or len(data) == 0


class TestIndicators:
    """指标计算测试"""
    
    def test_ma_calculation(self):
        """测试MA计算"""
        data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        ma5 = QA.MA(data, 5)
        
        assert len(ma5) == len(data)
        assert ma5.iloc[4] == 3.0  # (1+2+3+4+5)/5
        assert ma5.iloc[-1] == 8.0  # (6+7+8+9+10)/5
    
    def test_macd_calculation(self):
        """测试MACD计算"""
        data = QA.QA_fetch_stock_day('000001', '2024-01-01', '2024-12-31')
        macd = QA.MACD(data['close'])
        
        assert 'DIF' in macd.columns
        assert 'DEA' in macd.columns
        assert 'MACD' in macd.columns
        assert len(macd) == len(data)


# 运行测试
# pytest tests/test_datafetch.py -v
```

### 2. Mock和Fixture

```python
# tests/conftest.py
import pytest
import pandas as pd
from unittest.mock import Mock, patch


@pytest.fixture
def sample_stock_data():
    """股票数据fixture"""
    dates = pd.date_range('2024-01-01', periods=100)
    data = pd.DataFrame({
        'open': 10 + pd.Series(range(100)) * 0.1,
        'high': 11 + pd.Series(range(100)) * 0.1,
        'low': 9 + pd.Series(range(100)) * 0.1,
        'close': 10 + pd.Series(range(100)) * 0.1,
        'volume': 1000000
    }, index=dates)
    return data


@pytest.fixture
def mock_mongodb():
    """Mock MongoDB连接"""
    with patch('pymongo.MongoClient') as mock_client:
        mock_db = Mock()
        mock_client.return_value.__getitem__.return_value = mock_db
        yield mock_db


# tests/test_strategy.py
from QUANTAXIS.QAStrategy import QAStrategyCtaBase


class TestStrategy:
    """策略测试"""
    
    def test_strategy_init(self, sample_stock_data):
        """测试策略初始化"""
        strategy = QAStrategyCtaBase(
            code='000001',
            frequence='1day',
            start='2024-01-01',
            end='2024-12-31'
        )
        
        assert strategy.code == '000001'
        assert strategy.frequence == '1day'
        assert strategy.init_cash == 1000000
    
    def test_strategy_with_mock_data(self, sample_stock_data, mock_mongodb):
        """使用Mock数据测试策略"""
        # 配置Mock返回值
        mock_mongodb.stock_day.find.return_value = sample_stock_data.to_dict('records')
        
        # 测试策略逻辑
        strategy = QAStrategyCtaBase(code='000001')
        # ... 测试代码
```

### 3. 测试覆盖率

```bash
# 安装coverage
pip install pytest-cov

# 运行测试并生成覆盖率报告
pytest --cov=QUANTAXIS --cov-report=html

# 查看报告
open htmlcov/index.html

# 覆盖率要求
# 核心模块: > 80%
# 工具函数: > 90%
```

---

## 🔗 集成测试

### 1. 数据库集成测试

```python
# tests/integration/test_database.py
import pytest
from pymongo import MongoClient
import QUANTAXIS as QA


class TestDatabaseIntegration:
    """数据库集成测试"""
    
    @pytest.fixture(scope='class')
    def mongodb_client(self):
        """MongoDB测试客户端"""
        client = MongoClient('mongodb://localhost:27017/')
        db = client.quantaxis_test
        
        yield db
        
        # 清理测试数据
        client.drop_database('quantaxis_test')
    
    def test_save_and_fetch(self, mongodb_client):
        """测试保存和获取数据"""
        # 保存数据
        test_data = {
            'code': 'TEST001',
            'date': '2024-01-01',
            'close': 10.0
        }
        mongodb_client.stock_day.insert_one(test_data)
        
        # 获取数据
        result = mongodb_client.stock_day.find_one({'code': 'TEST001'})
        
        assert result is not None
        assert result['code'] == 'TEST001'
        assert result['close'] == 10.0
    
    def test_data_consistency(self, mongodb_client):
        """测试数据一致性"""
        # 写入数据
        codes = ['000001', '000002', '600000']
        for code in codes:
            QA.QA_SU_save_stock_day(code, mongodb_client)
        
        # 验证数据
        for code in codes:
            data = QA.QA_fetch_stock_day(code, '2024-01-01', '2024-12-31')
            assert data is not None
            assert len(data) > 0
```

### 2. API集成测试

```python
# tests/integration/test_api.py
import requests
import pytest


class TestAPIIntegration:
    """API集成测试"""
    
    BASE_URL = 'http://localhost:8010'
    
    @pytest.fixture(scope='class')
    def auth_token(self):
        """获取认证令牌"""
        response = requests.post(
            f'{self.BASE_URL}/api/login',
            json={'username': 'test', 'password': 'test123'}
        )
        return response.json()['token']
    
    def test_get_stock_data(self, auth_token):
        """测试获取股票数据API"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        response = requests.get(
            f'{self.BASE_URL}/api/stock/000001',
            headers=headers,
            params={'start': '2024-01-01', 'end': '2024-12-31'}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'code' in data
        assert 'data' in data
        assert len(data['data']) > 0
    
    def test_submit_order(self, auth_token):
        """测试提交订单API"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        order = {
            'code': '000001',
            'direction': 'BUY',
            'volume': 100,
            'price': 10.0
        }
        
        response = requests.post(
            f'{self.BASE_URL}/api/order',
            headers=headers,
            json=order
        )
        
        assert response.status_code == 200
        result = response.json()
        assert 'order_id' in result
```

---

## 📊 策略测试

### 1. 回测测试

```python
# tests/test_backtest.py
from QUANTAXIS.QAStrategy import QAStrategyCtaBase
import QUANTAXIS as QA


class TestBacktest:
    """回测测试"""
    
    def test_simple_ma_strategy(self):
        """测试简单MA策略"""
        
        class SimpleMAStrategy(QAStrategyCtaBase):
            def user_init(self):
                self.ma_period = 20
            
            def on_bar(self, bar):
                market_data = self.get_code_marketdata(bar.code)
                if len(market_data) < self.ma_period:
                    return
                
                close_prices = [x['close'] for x in market_data]
                ma = sum(close_prices[-self.ma_period:]) / self.ma_period
                
                positions = self.acc.positions
                if bar.close > ma and bar.code not in positions:
                    self.BuyOpen(bar.code, 1)
                elif bar.close < ma and bar.code in positions:
                    self.SellClose(bar.code, 1)
        
        # 运行回测
        strategy = SimpleMAStrategy(
            code='rb2501',
            frequence='5min',
            start='2024-01-01',
            end='2024-12-31',
            init_cash=1000000
        )
        strategy.run_backtest()
        
        # 验证结果
        acc = strategy.acc
        assert acc.balance > 0
        assert acc.total_return is not None
        assert len(acc.trades) > 0
    
    def test_strategy_metrics(self):
        """测试策略指标"""
        strategy = create_test_strategy()
        strategy.run_backtest()
        acc = strategy.acc
        
        # 基本指标
        assert acc.sharpe_ratio is not None
        assert acc.max_drawdown is not None
        assert acc.win_rate >= 0 and acc.win_rate <= 1
        
        # 收益率
        total_return = (acc.balance / acc.init_cash - 1) * 100
        assert total_return >= -100  # 最大亏损100%
```

### 2. 策略压力测试

```python
# tests/test_stress.py
import pytest


class TestStrategyStress:
    """策略压力测试"""
    
    @pytest.mark.parametrize("code", [
        'rb2501', 'cu2512', 'au2512', 'ag2512'
    ])
    def test_multiple_products(self, code):
        """测试多个品种"""
        strategy = create_test_strategy(code=code)
        strategy.run_backtest()
        
        assert strategy.acc.balance > 0
    
    def test_long_period(self):
        """测试长周期回测"""
        strategy = create_test_strategy(
            start='2020-01-01',
            end='2024-12-31'  # 5年数据
        )
        strategy.run_backtest()
        
        # 验证数据完整性
        assert len(strategy.market_data) > 1000
    
    def test_high_frequency(self):
        """测试高频数据"""
        strategy = create_test_strategy(
            frequence='1min',  # 1分钟数据
            start='2024-01-01',
            end='2024-01-31'
        )
        strategy.run_backtest()
        
        # 验证性能
        assert strategy.execution_time < 60  # 应在60秒内完成
```

---

## ⚡ 性能测试

### 1. 基准测试

```python
# tests/test_performance.py
import time
import pytest


class TestPerformance:
    """性能测试"""
    
    def test_data_fetch_performance(self, benchmark):
        """测试数据获取性能"""
        def fetch_data():
            return QA.QA_fetch_stock_day(
                '000001',
                '2024-01-01',
                '2024-12-31'
            )
        
        # pytest-benchmark
        result = benchmark(fetch_data)
        assert result is not None
    
    def test_indicator_calculation_performance(self):
        """测试指标计算性能"""
        data = QA.QA_fetch_stock_day('000001', '2020-01-01', '2024-12-31')
        
        start = time.time()
        ma20 = QA.MA(data['close'], 20)
        elapsed = time.time() - start
        
        # 应在100ms内完成
        assert elapsed < 0.1
    
    def test_backtest_performance(self):
        """测试回测性能"""
        strategy = create_test_strategy()
        
        start = time.time()
        strategy.run_backtest()
        elapsed = time.time() - start
        
        # 1年分钟数据应在30秒内完成
        assert elapsed < 30
```

### 2. 内存测试

```python
# tests/test_memory.py
import psutil
import gc


class TestMemory:
    """内存测试"""
    
    def test_memory_leak(self):
        """测试内存泄漏"""
        process = psutil.Process()
        
        # 初始内存
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # 运行多次
        for _ in range(100):
            strategy = create_test_strategy()
            strategy.run_backtest()
            del strategy
        
        # 清理后内存
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024
        
        # 内存增长应小于50MB
        memory_growth = final_memory - initial_memory
        assert memory_growth < 50
```

---

## 🔄 持续集成

### 1. GitHub Actions配置

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      mongodb:
        image: mongo:5.0
        ports:
          - 27017:27017
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.8
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run tests
        run: |
          pytest --cov=QUANTAXIS --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          file: ./coverage.xml
```

### 2. 预提交钩子

```bash
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
  
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  
  - repo: https://github.com/PyCQA/pylint
    rev: v2.17.4
    hooks:
      - id: pylint

# 安装
pip install pre-commit
pre-commit install

# 运行所有文件
pre-commit run --all-files
```

---

## 📝 测试最佳实践

### 1. 测试原则

```python
# ✅ 测试应该快速
def test_fast():
    """单个测试应在1秒内完成"""
    result = calculate_simple_metric()
    assert result > 0

# ✅ 测试应该独立
def test_independent():
    """不依赖其他测试的结果"""
    data = create_test_data()  # 每个测试创建自己的数据
    result = process(data)
    assert result is not None

# ✅ 测试应该可重复
def test_repeatable():
    """多次运行结果相同"""
    # 使用固定种子
    np.random.seed(42)
    result = generate_random_data()
    assert len(result) == 100

# ❌ 避免测试依赖
def test_bad_1():
    global shared_data
    shared_data = fetch_data()  # 不要这样做

def test_bad_2():
    # 依赖test_bad_1
    process(shared_data)  # 不要这样做
```

### 2. 测试命名

```python
# ✅ 清晰的测试命名
def test_fetch_stock_returns_dataframe_with_valid_code():
    """测试：使用有效代码获取股票数据应返回DataFrame"""
    pass

def test_strategy_raises_error_with_invalid_frequence():
    """测试：使用无效频率创建策略应抛出错误"""
    pass

# ❌ 不清晰的命名
def test_1():
    pass

def test_it_works():
    pass
```

---

## 🔗 相关资源

- **代码规范**: [代码规范文档](code-standards.md)
- **性能优化**: [性能优化指南](../advanced/performance-tuning.md)
- **pytest文档**: https://docs.pytest.org/

---

## 📝 总结

测试指南要点：

✅ **完整覆盖**: 单元测试 + 集成测试 + E2E测试  
✅ **自动化**: CI/CD + 预提交钩子  
✅ **性能监控**: 基准测试 + 内存测试  
✅ **高质量**: 覆盖率 > 80% + 快速 + 独立  
✅ **持续改进**: 定期review + 重构测试  

---

**作者**: @yutiansut @quantaxis
**最后更新**: 2025-10-25

[返回开发指南](../README.md)

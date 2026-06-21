# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## 项目概述

`difoss-stock-util` 是一个 Python 量化金融工具库，面向 A 股市场。提供证券代码解析与标准化、金融数据 SQLAlchemy ORM 模型、CLI/REPL 交互框架、TDX（通达信）数据解析、xtquant/miniQMT 对接、以及 Rich 终端 UI 组件。

## 构建 / 测试 / 代码检查

本项目没有正式的构建系统（无 `setup.py`、`pyproject.toml`、`Makefile`）。库通过 `sys.path` 或本地包方式直接导入使用。

- **安装核心依赖**：`pip install -r difoss_stock_util/requirements.txt`
- **直接运行脚本**：`python <script.py>`（多数模块在 `if __name__ == "__main__"` 中包含内联测试代码）
- **运行 REPL 演示**：`python click_util_history_demo.py`
- **临时测试**：`python test/t_stock.py`、`python test/t_log.py`
- **代码检查/格式化**：未配置任何 linter 或 formatter（无 `.flake8`、`.pylintrc`、`pyproject.toml`）

## 架构

### 包入口

`difoss_stock_util/__init__.py` 通过 `from .xxx import *` 重导出所有子模块。版本号为 `1.0.0`。使用者通过 `from difoss_stock_util import *` 获取全部功能。

### 核心模块

| 模块 | 职责 |
|---|---|
| `security_util.py` | `SecurityCode` 类 — 解析并标准化沪深北港各市场的股票/期货/期权代码。`MetadataEnumType` 元类和枚举（`SecurityType`、`MarketType`、`DividendType`）。 |
| `stock_util.py` | 基于 `chinese_calendar` 的交易日计算、`TradingInfo` 类、选股/筛选工具。 |
| `db_util.py` | SQLAlchemy ORM 基础设施。`BaseModel` 继承体系（见下文）、`DatabaseManager` 单例（按数据库 URL 区分，线程安全 `__new__` + `Lock`）。 |
| `click_util.py` | REPL/CLI 框架（约 33KB）。`repl_cli_main()`、`run_modern_repl()`、`auto_register_commands()`、`ConfirmableOption`、`with_field_filter_options`。基于 `click` + `prompt_toolkit`。 |
| `color_log_util.py` | 基于 `click.style` 的彩色日志。快捷函数：`T`（trace）、`D`（debug）、`I`（info）、`W`（warning）、`E`（error）。全局 `__printable` 标志可抑制所有输出。 |
| `util.py` | 通用工具：装饰器（`@trace`、`@timing`）、YAML+.env 配置解析、字典操作函数。 |
| `time_util.py` | 日期/时间辅助装饰器和 `TimeUtils` 类。 |
| `xtquant_util.py` | xtquant/miniQMT 连接管理、行情数据获取、数据格式转换。 |

### 子包

- **`tdx_util/`** — 通达信数据：`.ebk` 板块文件读写、行业树 XML 解析、`tdxhy.cfg` 股票行业映射、`infoharbor_block.dat` 解析、基于 ta-lib 的技术分析函数封装。
- **`rich_util/`** — Rich 终端 UI：DataFrame 转 Rich Table 渲染、pip 风格进度条、多种枚举式进度条变体。
- **`metric_data/`** — SQLAlchemy ORM 模型：`HistoryData1D`（日线 K 线）、`SLBDetail`（扫雷宝风险筛查）、`StockInstrumentDetail`。

### ORM 模型继承体系（`db_util.py`）

```
Base (declarative_base)
 └─ BaseModel          — to_dict、CRUD 辅助、带变更检测的 upsert、通过 _snake_case 自动生成 __tablename__
     └─ BaseModelWithID     — 添加自增 `id` 主键
     └─ BaseModelHistory    — 添加 `created_at`、`updated_at` 时间戳
         └─ BaseSecurityModel    — 添加 `ExchangeID`、`InstrumentID`，按证券键 upsert
             └─ BaseSecurityModelWithID — 在 BaseSecurityModel 基础上添加 `id`
```

`DatabaseManager` 按数据库 URL 实现单例模式。通过 `db_manager.session_context()` 上下文管理器获取会话。

### SecurityCode 设计（`security_util.py`）

`SecurityCode` 接收代码字符串，根据前缀模式自动识别市场（SH/SZ/BJ/HK）和证券类型（股票/指数/期货/期权）。它会标准化代码（如 `sh.000001` → 上海指数），处理期货（`eb05.DF`）和期货期权（`m2612-P-3000.DF`），并通过 `BJ_change_code_2025_10_09.py` 支持北交所新旧代码迁移。

### REPL/CLI 框架模式（`click_util.py`）

通过定义 `@click.command()` 函数，然后调用 `repl_cli_main(doc=..., prompt=..., find_caller_cmds=True)` 即可构建交互式工具。命令自动注册并生成首字母缩写。功能包括：prompt_toolkit 历史持久化、Choice 感知的 Tab 补全、`!行号` 重新执行历史命令、Ctrl+C 分级处理、用于危险操作的 `ConfirmableOption`。

参考 `click_util_history_demo.py` 了解最小使用模式，参考 `click_util【功能说明】.md` 了解完整中文开发指南。

### 日志规范（`color_log_util.py`）

```python
I("消息", key1=value1, key2=value2)     # INFO（黄色）
D("调试信息", var=val)                   # DEBUG（青色）
W("警告", reason=msg)                    # WARNING（品红）
E("错误", code=errno)                    # ERROR（亮红）
T("追踪", detail=obj)                    # TRACE（亮绿）
```

输出格式：`[LEVEL] 消息 key1=value1, key2=value2`。使用 `set_printable(False)` 可全局关闭输出。

## 编码约定

- 每个文件头部都包含 `#!python` / `# encoding: utf-8` / `# author: DifossChen`（或 `DifossChan`）
- 每个模块显式定义 `__all__`
- 全项目使用中文注释和文档
- 线程安全按需使用 — 仅在 `DatabaseManager` 中使用了 `Lock`
- 未配置类型检查器；类型注解存在但不完全一致

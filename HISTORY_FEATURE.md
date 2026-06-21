# REPL 历史命令功能说明

## 功能概述

在 `click_util.py` 中添加了 REPL（Read-Eval-Print Loop）交互模式的历史命令管理功能。用户可以通过 `history` 命令（或其缩写 `h`）来查看和翻阅在交互模式下输入的所有历史命令。

## 核心改动

### 1. 新增 `history` 命令函数

```python
@click.command()
@click.option('-n', '--number', type=int, default=None, help='显示最后 N 条历史记录，默认显示全部')
@click.option('-a', '--all', is_flag=True, help='显示所有历史记录（包括行号）')
def history(number, all):
    """查看 REPL 历史命令"""
```

**功能特性：**
- 读取 `.xxx.history` 文件显示历史命令
- 支持 `-n/--number` 选项限制显示条数
- 支持 `-a/--all` 选项以带行号的格式显示
- 自动提示"暂无历史记录"（当文件不存在或为空时）
- 显示总计行数

**使用示例：**
```bash
> history              # 显示所有历史命令
> history -n 10        # 显示最后 10 条命令
> history --all        # 显示所有命令（带行号）
> h                    # 缩写形式
> h -n 5 --all         # 结合选项
```

### 2. 新增历史文件管理

#### 全局变量
```python
HISTORY_FILE = None  # type: str | None
```
用于存储当前 REPL 会话的历史文件路径。

#### 历史文件位置规则
- 文件名格式：`.{caller_filename}.history`
- 存储位置：当前工作目录（由调用者所在目录决定）

**示例：**
- 调用者：`tdxdata_repl.py` → 历史文件：`.tdxdata_repl.history`
- 调用者：`slb_cmd.py` → 历史文件：`.slb_cmd.history`

### 3. 修改 `repl_cli_main` 函数

#### 获取调用者信息
```python
import inspect
caller_frame = inspect.currentframe().f_back
caller_filename = Path(caller_frame.f_code.co_filename).stem
HISTORY_FILE = Path.cwd() / f'.{caller_filename}.history'
```
通过 inspect 模块获取调用者的文件名，并构造历史文件路径。

#### 设置历史支持
在交互模式启动前调用：
```python
_setup_history_for_repl()
```

### 4. 新增 `_setup_history_for_repl()` 辅助函数

```python
def _setup_history_for_repl():
    """为 REPL 配置历史文件"""
```

**功能：**
1. 使用 Python 的 `readline` 模块（在支持的平台上）
2. 启动时读取现有历史记录（如果文件存在）
3. 使用 `atexit` 注册保存函数，在程序退出时保存历史
4. 优雅处理 `readline` 不可用的情况（如 Windows）

**工作流程：**
```
REPL启动
  ↓
_setup_history_for_repl() 被调用
  ↓
加载现有的 .xxx.history 文件到 readline
  ↓
注册 atexit 回调函数
  ↓
REPL运行，用户输入命令
  ↓
用户输入的命令被 readline 自动记录
  ↓
REPL退出时，atexit 回调函数保存历史到 .xxx.history 文件
```

## 使用示例

### 基本使用

```bash
$ python tdxdata_repl.py
交互模式 (输入 help 查看命令，exit 退出)
> symbol sh000001
# ... 执行命令 ...

> symbol sh000002
# ... 执行命令 ...

> history
symbol sh000001
symbol sh000002

> exit
```

### 高级用法

```bash
# 显示最后 5 条命令
> history -n 5

# 显示所有命令并带行号
> history --all
    1 │ symbol sh000001
    2 │ symbol sh000002
    3 │ status
    4 │ quote 000001 000002 000003
    5 │ history

总计 5 条命令
```

### 文件持久化

每次退出 REPL 时，历史记录自动保存到隐藏文件：

```bash
$ ls -la
...
-rw-r--r--  1 user  group  1234 May  8 12:34 .tdxdata_repl.history
-rw-r--r--  1 user  group  5678 May  8 12:34 .slb_cmd.history
...
```

## 技术细节

### 依赖模块
- `readline`：提供 REPL 历史记录功能（Unix/Linux/macOS）
- `pathlib.Path`：文件路径操作
- `inspect`：获取调用者信息
- `atexit`：程序退出时保存历史

### 跨平台兼容性

- **Unix/Linux/macOS**：完整支持，使用 readline 自动管理历史
- **Windows**：
  - 如果安装了 `pyreadline` 或 `prompt_toolkit`，可以使用
  - 如果未安装，历史功能降级但程序仍可正常运行
  - 建议安装 `pyreadline`：`pip install pyreadline`

### 线程安全性

- `readline` 模块在单线程 REPL 中是安全的
- 如果在多线程环境中使用，建议在 REPL 之外处理线程管理

## 与现有功能的整合

### 与缩写系统的结合

```python
# history 命令自动获得 'h' 缩写
@click.command()
@click.option('-n', '--number', type=int, default=None)
@click.option('-a', '--all', is_flag=True)
def history(number, all):
    """查看 REPL 历史命令"""
```

通过 `command_with_abbrev` 装饰器或自动缩写系统，`history` 命令自动生成 `h` 缩写。

### 与命令注册系统的结合

`history` 命令与其他命令一样通过 `auto_register_commands()` 自动注册，无需额外配置。

## 故障排除

### 问题：历史文件未创建
**原因：**
- REPL 中未执行任何命令
- readline 模块不可用

**解决：**
- 在 REPL 中执行至少一条命令后退出
- 检查 `readline` 是否正确安装

### 问题：Windows 下不保存历史
**原因：**
- Windows 默认不包含 readline

**解决：**
```bash
pip install pyreadline
# 或
pip install prompt_toolkit
```

### 问题：历史文件过大
**原因：**
- 长期使用累积的命令过多

**解决：**
- 手动删除 `.xxx.history` 文件，重新开始记录
- 或定期清理：`cat /dev/null > .xxx.history`

## 相关配置

### 环境变量
- `HISTFILE`：如果设置，readline 会使用此路径代替默认位置（当前实现覆盖此设置）

### 配置选项（未来扩展）
考虑的增强功能：
- 配置最大历史条数限制
- 支持历史搜索功能
- 支持历史导出为 JSON/CSV
- 支持多个 REPL 会话的共享历史

## 总结

此功能提供了：
1. ✅ 自动历史记录保存到 `.xxx.history` 文件
2. ✅ 交互式 `history` 命令查看历史
3. ✅ 支持行号、条数限制等多种显示选项
4. ✅ 跨平台兼容性（Unix/Linux/macOS/Windows）
5. ✅ 与现有 click 命令系统无缝集成
6. ✅ 优雅的错误处理和降级机制

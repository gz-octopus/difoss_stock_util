# 交互式命令行 (REPL) 开发指南

本框架旨在帮助开发者基于 `click` 快速构建一个具有命令自动补全、历史记录落盘、子命令参数提示及异常处理能力的交互式工具。

## 第一部分：`click_util` 核心功能说明

`click_util` 是本框架的引擎，它封装了 `click` 和 `prompt_toolkit`，将原本静态的命令行工具转换为强大的交互式 Shell。

### 1. 核心特性

- **交互式 Shell (REPL)**：通过 `run_modern_repl` 启动一个持续运行的循环，支持用户连续输入命令。
- **命令自动发现 (Auto Registration)**：支持根据模块自动加载命令，无需手动逐个注册。
- **智能参数补全**：
  - **Choice 类型自动提示**：自动识别 `click.Choice` 定义的选项（如 `zb`, `xg`），无需硬编码。
  - **上下文感知**：根据当前输入的参数，提供精准的补全，并过滤掉 `is_flag=True` 导致的 `true/false` 布尔值干扰。
- **历史记录落盘**：自动保存用户的每一次有效输入到指定文件，程序退出后再启动依然可用。
- **鲁棒性异常处理**：
  - **Ctrl+C 处理**：支持“命令执行中中断但不退出”、“空提示符下重置整行”、“无任务时退出”的三重逻辑。
  - **自动拦截**：通过 `!行号` 快速执行历史记录中的命令。

## 第二部分：以 `mt5_repl.py` 为例构建 REPL

要构建一个带有历史记录和丰富补全的工具，你只需要关注两件事：**定义命令** 和 **启动 REPL**。

### 1. 编写命令 (Define)

在 `mt5_repl.py` 中，你可以像写普通 `click` 命令一样定义功能。

```python
import click
from difoss_stock_util.click_util import *

# --------------------------------------------------------------------------------
# 全局变量
CONSOLE = Console()
CFG = None

# --------------------------------------------------------------------------------
# 常规函数
# ======================
# 初始化
def init(_ctx: click.Context):
    global CFG, CONSOLE

    config_path = 'config.yaml' # TODO：添加参数进行更新配置文件即可，无需在 repl/cli 入口参数填写。

    _ctx.ensure_object(dict)
    _ctx.obj['config_path'] = config_path
    _ctx.obj['console'] = CONSOLE
    if not CFG:
        CFG = read_yaml_config(config_path)
    _ctx.obj['cfg'] = CFG

    try:
        # 1. 初始化
        if not mt5.initialize():
            print(f"❌ MT5 初始化失败, 错误码 = {mt5.last_error()}")
            return
        click.echo("✅ MT5 初始化成功")
    except Exception as e:
        CONSOLE.print_exception(extra_lines=5, show_locals=True)


def destroy(_ctx: click.Context):
    mt5.shutdown()

# 只需要定义 click.command
@click.command()
@click.option('--stock', '-s', help='股票代码')
def query(stock):
    """查询股票信息"""
    print(f"正在查询: {stock}")


# ======================
# main（根据参数决定模式）
if __name__ == '__main__':
    repl_cli_main(doc='MT5 数据工具', prompt='mt5> ', on_init=init, on_destroy=destroy, console=CONSOLE)
```

### 2. 构建并启动 REPL (Build & Run)

利用 `click_util` 提供的初始化工具，可以便捷地启动交互模式。

Python

```python
from difoss_stock_util.click_util import run_modern_repl

def main():
    # 1. 创建你的命令组
    group = cli 
    
    # 2. 准备上下文 (obj用于在命令间共享数据，如 MT5 实例)
    ctx = click.Context(group)
    ctx.obj = {'console': Console()} # 注入 rich 控制台
    
    # 3. 启动 REPL
    # prompt: 提示符
    # hist_file: 历史记录保存路径
    run_modern_repl(group, ctx, prompt="mt5> ", hist_file="mt5_history.txt")

if __name__ == '__main__':
    main()
```

### 为什么这样做最便捷？

1. **代码即补全**：你不需要编写任何补全逻辑。只要你定义了 `click.option(type=click.Choice(...))`，`click_util` 就会自动将其加入补全列表。
2. **统一的上下文**：通过 `ctx.obj`，你可以将 MT5 终端的连接句柄、配置文件 (`config.yaml`) 共享给所有命令，避免在每个函数中重复初始化。
3. **零基础学习曲线**：对于已有 `click` 经验的开发者，迁移到这个 REPL 架构只需要更改入口点 (`run_modern_repl`)，现有的命令逻辑无需任何修改。
4. **历史命令重用**：在 `mt5> ` 提示符下，输入 `h` 即可看到所有历史行号，通过 `!行号` 即可复用复杂的查询参数，极大提升了调试和分析效率。

### 开发提示

- **关于异常**：如果你的命令执行时触发了错误，`click_util` 内部已经捕获了 `Exception` 并通过 `console.print_exception()` 输出，这会展示报错代码的上下文，非常有利于排查 MT5 API 调用错误。
- **关于实时显示**：如果你的 `mt5_repl` 需要实时显示行情流，请确保在命令中捕获 `KeyboardInterrupt`，这样按 `Ctrl+C` 时程序只会停止行情流，而不会直接闪退。
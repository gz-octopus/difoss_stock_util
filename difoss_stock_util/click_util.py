#!python3
# encoding: utf-8
# author: DifossChen
# version: v1.3.6
# changes:
# - v0.1.10 (2026-05-07): 初始版本，提供基础的命令注册和交互式 REPL 功能
# - v1.0.0 (2026-05-15): 使用 vscode 原生 CHAT（Agent: Code Block），重构交互模式，使用 click.shell 原生试图支持历史命令（落盘）和 prompt 提示。
#  【缺陷】click.shell 的历史命令功能存在严重缺陷（无法落盘历史命令）；
#  【缺陷】prompt 也无法有效提示子命令。
# - v1.1.0 (2026-05-16): 使用 Google gemini 继续完善 repl_cli_main，并重构历史命令和子命令参数提示（prompt）功能。
#   使用 prompt_toolkit 驱动交互式终端，成功实现历史命令落盘、打字自动提示、异常安全补全等功能。
#   【缺陷】目前历史命令文件中会包含所有输入的命令（包括无效命令和选项命令），后续版本计划优化为仅记录成功执行的非黑名单命令。
# - v1.3.2 (2024-05-17): 引入现代交互库（click_repl），
#   【修复】仅成功执行的非黑名单命令记录问题
#   【修复】对不存在命令时 prompt_toolkit 的异常处理进行了增强，避免因补全器访问不存在的命令属性而导致的崩溃。
#   ```python
#   # =========================================================================
#    # 核心修复：定义一个安全的补全器，捕获并吞掉因输入不存在的命令或非法参数引发的后台 click 异常
#    # =========================================================================
#    class SafeClickCompleter(ClickCompleter):
#        def get_completions(self, document, complete_event):
#            try:
#                # yield from 能够代理子生成器，并捕获子生成器执行期间抛出的所有异常
#                yield from super().get_completions(document, complete_event)
#            except Exception:
#                return  # 发生异常时直接优雅退出（停止产生提示），从而保护事件循环不崩溃`
#   ```
#   【新增】history 命令支持清空历史记录功能。
#   【缺陷】子命令参数提示选项只能提示 true/false（纵使使用了 click.Choice）。
# - v1.3.2 (2026-05-19): 修复子命令参数提示选项只能提示 true/false 的问题，增强了对 click.Choice 类型选项的提示支持
# （使用 AutoChoiceCompleter 类替代 SafeClickCompleter）。
#   【修复】借鉴 SafeClickCompleter，改良出 SafAutoChoiceCompleter，在增强对 click.Choice 的支持的同时，保留了异常安全的特性，从而实现了既能正确提示 Choice 定义的选项值，又能优雅处理用户输入不存在的命令或非法参数时引发的异常，避免了之前版本中因补全器访问不存在的命令属性而导致的崩溃问题。
#   【修复】手动修复 completions 列表产生时没有强制转换成 str 类型的问题，从而避免了当 Choice 定义的选项值不是字符串时，提示功能失效的问题。
# - v1.3.3 (2026-05-25): 修复 Ctrl+C 的问题（在执行子命令或提示符后有字符时，不作退出）。
# - v1.3.4 (2026-05-26): 添加字段过滤功能的装饰器。
# - v1.3.5 (2026-05-28):
# 【新增】history 命令支持通过 "!行号" 的方式执行历史命令。
# 【修复】history 命令显示历史记录时的行号错误问题，现在以历史文件中行号的倒序显示（保持bash习惯）。
# - v1.3.6 (2026-06-08)
# 【添加】history 命令新增支持 --contain/-c 参数（--clear参数的短参数-c废弃），用于根据该参数过滤历史命令。
# - v1.3.7 (2026-06-26)
# 【添加】子命令管道(|) 的功能


__all__ = [
    'confirmable_option',
    'ConfirmableOption',
    'DATETIME',
    'split_comma',
    'split_comma_upper',
    'split_comma_lower',
    'split_comma_stocks',
    'split_comma_datetime',
    'split_comma_int',
    'has_chinese',
    'CommaSeparatedList',
    'auto_register_commands',
    'repl_cli_main',
    'command_with_abbrev',
    'with_field_filter_options',
]

import click
import click_shell
from datetime import datetime
from typing import Optional, Callable, List, Dict
import typing as t
import importlib
from types import ModuleType
import os
from pathlib import Path

from .color_log_util import *
from .time_util import TimeUtils
from .rich_util.rich_table import *
from .security_util import SecurityCode
# from .util import trace_func

from rich.console import Console
import pandas as pd
import sys
import re
import functools

# 引入现代交互库
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import ThreadedCompleter
from prompt_toolkit.completion import Completion
from prompt_toolkit.key_binding import KeyBindings
from click_repl import ClickCompleter
import shlex

# ---------------------------------------------------------------------------------------------
# Globals
DOC = None  # type: str | None
SUB_COMMANDS_DF = None # type: pd.DataFrame | None
REGISTERED_CMDS = dict()
HISTORY_FILE = None  # type: str | None

# ---------------------------------------------------------------------------------------------
class ConfirmableOption(click.Option):
    """支持二次确认的选项类"""

    def __init__(self, *args, **kwargs):
        self.confirm_message = kwargs.pop('confirm_message', None)
        self.confirm_prompt = kwargs.pop('confirm_prompt', "Are you sure you want to continue?")
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        value = opts.get(self.name)

        if value and self.confirm_message:
            if not click.confirm(self.confirm_message):
                ctx.fail("Operation cancelled by user")

        return super().handle_parse_result(ctx, opts, args)

def confirmable_option(*args, **kwargs):
    """装饰器函数，用于创建可确认的选项"""
    def decorator(f):
        param_decls = args or kwargs.pop('param_decls', None)
        return click.option(
            *param_decls,
            cls=ConfirmableOption,
            **kwargs
        )(f)
    return decorator


class DateTimeType(click.ParamType):
    """自定义日期时间类型"""
    name = "datetime"

    def __init__(self):
        pass

    def convert(self, value: str, param: Optional[click.Parameter], ctx: Optional[click.Context]) -> datetime:
        if isinstance(value, datetime):
            return value
        res = TimeUtils.str_to_datetime(value)
        return res or (param and param.default)


DATETIME = DateTimeType()

def split_comma(ctx: click.Context, param: click.Parameter, value) -> list[str]:
    """将逗号分隔的字符串拆分为列表，同时支持多个值"""
    if not value:
        return []

    result = set()

    if isinstance(value, str):
        value = [value] if value else []

    for v in value:
        # 如果值中包含逗号，进一步分割
        if isinstance(v, str) and ',' in v:
            result.update([v.strip() for v in v.split(',') if v.strip()])
        else:
            result.add(v)

    return list(result)

def split_comma_upper(ctx: click.Context, param: click.Parameter, value) -> list[str]:
    result = split_comma(ctx, param, value)
    result = [r.upper() for r in result]
    return result

def split_comma_lower(ctx: click.Context, param: click.Parameter, value) -> list[str]:
    result = split_comma(ctx, param, value)
    result = [r.lower() for r in result]
    return result

def split_comma_int(ctx: click.Context, param: click.Parameter, value) -> list[int]:
    result = split_comma(ctx, param, value)
    int_result = []
    for r in result:
        try:
            int_result.append(int(r))
        except ValueError:
            raise click.BadParameter(f"无法将 '{r}' 转换为整数")
    return int_result

def split_comma_stocks(ctx: click.Context, param: click.Parameter, value) -> list[str]:
    """将逗号分隔的字符串拆分为股票列表，同时支持多个值"""
    res = []
    str_list = split_comma(ctx, param, value)
    for stock in str_list:
        try:
            code = SecurityCode(stock.upper())
            # I(short_code=code.short_code, market_code=code.market_code, typeOfMarketCode=type(code.market_code))
            res.append(code.full_code)
        except TypeError:
            # TODO: 这里捕获的异常类型需要根据 SecurityCode 的实现来确定，可能是 ValueError 或其他
            res.append(stock.upper())
    return res


def split_comma_datetime(ctx: click.Context, param: click.Parameter, value) -> list[datetime]:
    """将逗号分隔的字符串拆分为日期时间列表，同时支持多个值"""
    res = []
    str_list = split_comma(ctx, param, value)
    for dt in str_list:
        dt_obj = TimeUtils.str_to_datetime(dt)
        if dt_obj:
            res.append(dt_obj)
    return res


class CommaSeparatedList(click.ParamType):
    """逗号分隔的列表参数类型"""
    name = "comma_list"

    def convert(self, value, param, _ctx: click.Context):
        if not value:
            return []

        if isinstance(value, str):
            value = [value] if value else []

        # 如果值已经是列表（来自 nargs=-1）
        if isinstance(value, (tuple, list)):
            result = []
            for v in value:
                if isinstance(v, str) and ',' in v:
                    result.extend([item.strip() for item in v.split(',') if item.strip()])
                else:
                    result.append(v)
            return result
        else:
            return [value]


def has_chinese(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))


def _convert_to_mapping_df(registered_names: dict[str, dict]):
    """转换为简洁的命令映射表"""
    mapping_data = []

    for cmd_name, cmd_info in registered_names.items():
        # 只处理完整命令（is_full_name = True）
        is_full_name = cmd_info.get('is_full_name', False)
        if is_full_name:
            full_cmd = cmd_info['cmd']
            help_text = cmd_info['help']
            abbrev = cmd_info.get('abbrev', '')

            mapping_data.append({
                '完整命令': full_cmd,
                '缩写命令': abbrev,
                '功能说明': help_text
            })
    df = pd.DataFrame(mapping_data)
    if df.empty:
        return df
    return df.sort_values('完整命令')


def _show_registered_cmds():
    global REGISTERED_CMDS, DOC
    mapping_df = _convert_to_mapping_df(REGISTERED_CMDS)
    print_dataframe(mapping_df, title=f'{DOC}子命令', show_index=False)


@click.command()
def command():
    """显示支持的子命令"""
    _show_registered_cmds()


def command_with_abbrev(abbrev=None, **kwargs):
    """自定义命令装饰器，支持指定缩写

    Args:
        abbrev: 缩写名称
            - 如果为 None，使用默认逻辑（取每个单词首字母）
            - 如果为 ''，不创建缩写
            - 如果为字符串，使用指定的缩写
        **kwargs: 传递给 click.command 的其他参数
    """
    def decorator(f):
        # 将缩写信息存储到函数对象上
        f._cmd_abbrev = abbrev

        # 创建 click command
        cmd = click.command(**kwargs)(f)
        return cmd
    return decorator


@click.command()
@click.option('-n', '--number', type=int, default=30, help='显示最后 N 条历史记录')
@click.option('-a', '--all', 'all', is_flag=True, help='显示所有历史记录，相当于 --number 0')
@click.option('--clear', is_flag=True, help='清空历史文件记录')
@click.option('--contain', '-c', 'contain', type=str, help='查找含有字符串的历史记录')
@click.pass_context
def history(_ctx: click.Context,
            number: int,
            all: bool,
            clear: bool,
            contain: str):
    """查看 REPL 历史命令"""
    global HISTORY_FILE

    console = _ctx.obj.get('console', Console()) if _ctx and _ctx.obj else Console()

    # ---- 新增：清空历史记录逻辑 ----
    if clear:
        if HISTORY_FILE and Path(HISTORY_FILE).exists():
            try:
                # 以 'w' 方式打开会直接清空文件内容
                with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                    f.truncate(0)
                console.print('[green]历史文件记录已成功清空[/green]')
            except Exception as e:
                console.print(f'[red]清空历史记录失败: {e}[/red]')
        else:
            console.print('[yellow]历史记录文件不存在或本就为空[/yellow]')
        return

    # 优先使用内存中的历史记录，如果为空则尝试从文件读取
    lines = []
    if HISTORY_FILE and Path(HISTORY_FILE).exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                lines = [line.rstrip('\n') for line in f if line.strip()]
        except Exception:
            lines = []

    if not lines:
        console.print('[yellow]暂无历史记录[/yellow]')
        return

    _number_for_search = number
    if all:
        number = 0  # 显示所有记录
        _number_for_search = 0
    if contain:  # 需要查找的时候，也需要覆盖所有记录
        _number_for_search = 0

    # 逻辑修改：如果指定了 number，我们只取最后 N 条，但要保留它们的原始索引
    # enumerate 从 1 开始
    indexed_lines = list(enumerate(lines, 1))
    display_lines = indexed_lines[-_number_for_search:] if _number_for_search and _number_for_search > 0 else indexed_lines

    index_2_lines = {}

    # 显示带行号的格式
    for idx, line in display_lines:
        if contain:
            if  contain in line:
                index_2_lines.update({idx: line})
        else:
            index_2_lines.update({idx: line})

    for idx, line in index_2_lines.items():
        console.print(f'[dim]{idx:5d} │[/dim] {line}')

    console.print(f'\n[dim]总计 {len(lines)} 条命令。使用 "!行号" 执行历史记录。[/dim]')


def auto_register_commands(group: click.Group, cmds: dict[str, click.Command] = None, show_cmds = True):
    """帮助 click.Command 自动注册 module 中所有的子命令，并生成缩写"""

    if not cmds:
        cmds = {}

    cmds.update({'cmd': command, 'history': history}) # 添加内置的 cmd 和 history 命令

    try:
        global REGISTERED_CMDS
        for name, cmd in cmds.items():
            # 获取函数对象的 abbrev 属性（如果有）
            func = cmd.callback
            custom_abbrev = getattr(func, '_cmd_abbrev', None)

            # 注册全名（使用 kebab-case 风格）
            full_name = name.replace('_', '-')

            # 避免重复注册
            if full_name not in REGISTERED_CMDS:
                # DEBUG
                # I("➕ add_command（全名）", name=full_name)
                group.add_command(cmd, name=full_name)

                # 确定缩写
                if custom_abbrev == '':  # 空字符串表示无缩写
                    abbrev_valid = False
                    abbrev = ''
                elif custom_abbrev is not None:  # 指定了自定义缩写
                    abbrev = custom_abbrev
                    abbrev_valid = abbrev and abbrev != full_name and abbrev not in REGISTERED_CMDS
                else:  # None 表示使用默认逻辑
                    # 生成缩写：取每个单词首字母
                    abbrev = ''.join([word[0] for word in name.split('_') if word.strip()])
                    abbrev_valid = abbrev and abbrev != full_name and abbrev not in REGISTERED_CMDS
                abbrev_valid = abbrev and abbrev != full_name and abbrev not in REGISTERED_CMDS

                REGISTERED_CMDS[full_name] = {
                    'cmd': full_name,
                    'abbrev': abbrev if abbrev_valid else '',
                    'is_full_name': True,
                    'help': cmd.help,
                }

                if abbrev_valid:
                    # DEBUG
                    # I("➕ add_command（缩写）", name=abbrev)
                    group.add_command(cmd, name=abbrev)
                    REGISTERED_CMDS[abbrev] = {
                        'cmd': abbrev,
                        'full_name': full_name,
                        'is_full_name': False,
                        'help': cmd.help,
                    }

                    # print(f"✅ 注册命令: {full_name} ({abbrev})\t🍓 功能：{cmd.help.splitlines()[0]}")

    except Exception as e:
        raise e

    # 显示支持的命令
    if show_cmds:
        _show_registered_cmds()


# ---------------------------------------------------------------------------------------------
# 重构后的交互模式逻辑
# ---------------------------------------------------------------------------------------------
from prompt_toolkit.history import InMemoryHistory

def split_by_pipe(line: str) -> list[list[str]]:
    """按管道符 | 分割命令行，尊重引号内的 | 字面量。

    使用 shlex.shlex 词法分析器，引号内的 | 会被视为普通字符而不会被分割。

    >>> split_by_pipe('cmd --name "hello | world" | cmd2 -a b')
    [['cmd', '--name', 'hello | world'], ['cmd2', '-a', 'b']]

    >>> split_by_pipe('cmd1')            # 无管道 → 单段
    [['cmd1']]
    """
    lex = shlex.shlex(line, posix=True)
    lex.whitespace_split = True
    lex.commenters = ''

    segments = []
    current = []

    for token in lex:
        if token == '|':
            if current:
                segments.append(current)
                current = []
        else:
            current.append(token)

    if current:
        segments.append(current)

    # 确保至少返回一个空列表（输入为纯空白时）
    return segments if segments else [[]]


def _execute_pipe(pipe_segments: list[list[str]], group: click.Group, ctx: click.Context, console: Console):
    """
    管道链式执行引擎。

    上游命令返回的 dict 中每个 key 会自动匹配下游命令的 Click 参数名
    (param.name)，匹配成功且用户未显式传参时自动注入到下游 args。
    完整返回值同时存入 pipe_ctx_obj['_pipe_data'] 供下游命令显式读取
    （如 DataFrame 等复杂类型无法拼入命令行，只能通过此方式传递）。

    特性：
    - 克隆 ctx.obj 隔离管道内上下文，不污染主 REPL 的 obj
    - 通过 _pipe_producer 标志通知上游命令自动返回数据（无需 -sm）
    - 下游显式传参优先，不覆盖
    - 支持任意 key（stocks、codes、blocks...），无需修改管道引擎
    """
    # 1. 临时为管道环境克隆主上下文 obj，杜绝数据跨模块污染与持久化耦合
    pipe_ctx_obj = ctx.obj.copy() if ctx.obj else {}
    last_pipe_result = None  # 用于向后流转上游命令的 return 返回值

    for idx, args in enumerate(pipe_segments):
        if not args:
            continue

        # 2. 标记当前子命令是否是数据生产者（只要后面还有子命令，当前就是生产者）
        is_last = (idx == len(pipe_segments) - 1)
        pipe_ctx_obj['_pipe_producer'] = not is_last

        # 3. 🚀 通用注入：上游返回值 dict 的每个 key 自动匹配下游命令的 Click 参数名
        if idx > 0 and last_pipe_result and isinstance(last_pipe_result, dict):
            # 暴露完整返回值，供下游命令通过 ctx.obj['_pipe_data'] 显式读取
            pipe_ctx_obj['_pipe_data'] = last_pipe_result

            # 查找下游命令
            cmd_name = args[0]
            downstream_cmd = group.get_command(ctx, cmd_name)

            if downstream_cmd:
                # 收集下游命令中用户已显式传参的参数名（避免覆盖）
                explicit_names = set()
                for param in downstream_cmd.params:
                    if isinstance(param, click.Option) and any(o in args for o in param.opts):
                        explicit_names.add(param.name)

                for key, value in last_pipe_result.items():
                    if key in explicit_names:
                        continue
                    # 仅注入简单可迭代类型（list/set/tuple），DataFrame 等走 _pipe_data
                    if not isinstance(value, (list, set, tuple)) or not value:
                        continue

                    # 在下游命令的 params 中查找 param.name 匹配的 Option
                    for param in downstream_cmd.params:
                        if isinstance(param, click.Option) and param.name == key:
                            long_opt = next((o for o in param.opts if o.startswith('--')), param.opts[0])
                            args.extend([long_opt, ','.join(str(v) for v in value)])
                            break

        # 4. 顺序调用当前被动态注入参数后的 Click 链条
        try:
            # 必须维持 standalone_mode=False，Click 才会把函数的返回数据抛出来供下游消费
            last_pipe_result = group.main(
                args=args,
                standalone_mode=False,
                obj=pipe_ctx_obj
            )
        except click.Abort:
            # 用户主动中断（Ctrl+C），向上传播让 REPL 层处理
            raise
        except click.ClickException as e:
            # Click 参数校验等错误，显示后终止管道
            e.show()
            break
        except Exception:
            # 业务代码意外崩溃，打印完整堆栈便于定位
            console.print(f"[red]❌ 管道命令在第 {idx+1} 段 [bold]{args[0]}[/bold] 运行时异常[/red]")
            console.print_exception(extra_lines=5, show_locals=True)
            break

def run_modern_repl(group: click.Group, ctx: click.Context, prompt: str, hist_file: str, console: Console = None):
    """
    使用 prompt_toolkit 驱动的交互式终端
    实现：成功执行才保存历史、黑名单命令不进文件、打字自动提示、异常安全补全
    """
    if not console:
        console = Console()

    # 1. 确保历史文件目录存在
    hist_path = Path(hist_file)
    hist_path.parent.mkdir(parents=True, exist_ok=True)

    # 2. 初始化内存历史记录器
    history_obj = InMemoryHistory()

    # 启动时：手动从文件中预加载历史命令到内存（支持跨 session 翻页）
    if hist_path.exists():
        try:
            with open(hist_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line_cleaned = line.rstrip('\r\n')
                    if line_cleaned:
                        history_obj.append_string(line_cleaned)
        except Exception as e:
            console.print(f"[yellow]警告: 读取历史文件失败: {e}[/yellow]")


    # 3. 初始化补全器，增强对 click.Choice 的支持
    class SafAutoChoiceCompleter(ClickCompleter):
        def __init__(self, group, ctx=None):
            super().__init__(group, ctx)
            # 显式保存 group 和 ctx，解决 AttributeError
            self.group = group
            self.ctx = ctx

        def get_completions(self, document, complete_event):

            try:
                text_before = document.text_before_cursor
                args = text_before.split()

                # 1. 尝试从 Click 补全逻辑获取基础候选项
                completions = list(super().get_completions(document, complete_event))

                # 2. 增强逻辑：自动识别 Choice
                if args:
                    cmd_name = args[0]
                    # 找到当前命令对象
                    cmd = self.group.get_command(self.ctx, cmd_name)

                    if cmd and hasattr(cmd, 'params'):
                        last_token = args[-1]

                        # 遍历参数，查找 Choice
                        for param in cmd.params:
                            if last_token in param.opts or last_token in param.secondary_opts:
                                if isinstance(param.type, click.Choice):
                                    # 清空之前的模糊候选项，只保留 Choice 定义的值
                                    completions = [Completion(str(c), start_position=0) for c in param.type.choices]
                                    break

                # 3. 最终清洗：过滤掉所有布尔值干扰
                for c in completions:
                    if c.text in ('true', 'false', 'yes', 'no'):
                        continue
                    yield c

            except Exception:
                return  # 发生异常时直接优雅退出（停止产生提示），从而保护事件循环不崩溃`

    completer = ThreadedCompleter(SafAutoChoiceCompleter(group, ctx))

    # 创建自定义按键绑定
    kb = KeyBindings()

    @kb.add('c-c')
    def _(event):
        if not event.current_buffer.text:
            raise KeyboardInterrupt
        else:
            # 如果仅仅是在输入提示符下，重置当前行（模拟 shell 的 Ctrl+C）
            event.current_buffer.reset()
            # 或者 event.current_buffer.text = '' 清空内容
            # event.cli.print_text('\n') # 强制换行以实现视觉上的取消

    # 4. 初始化会话并绑定内存历史
    session = PromptSession(
        history=history_obj,
        completer=completer,
        key_bindings=kb,
        auto_suggest=AutoSuggestFromHistory(),
        complete_while_typing=True,
    )

    console.print(f"[bold green]进入交互模式[/bold green] (历史记录: {hist_file})")
    console.print("输入 [bold cyan]help[/bold cyan] 查看命令, [bold cyan]exit[/bold cyan] 退出\n")

    while True:
        try:
            text = session.prompt(prompt)

            if not text.strip():
                continue

            if str(text).lower() in ('exit', 'quit'):
                break

            text = str(text)

            # =========================================================================
            # 1. 拦截并处理 "!行号" 直接执行历史记录逻辑
            # =========================================================================
            if text.startswith('!'):
                try:
                    target_idx = int(text[1:])
                    hist_lines = Path(hist_file).read_text(encoding='utf-8').splitlines()
                    if 1 <= target_idx <= len(hist_lines):
                        text = hist_lines[target_idx - 1]
                        console.print(f"[blue]执行历史命令 #{target_idx}: {text}[/blue]")
                    else:
                        console.print(f"[red]无效的行号: {target_idx}[/red]，[yellow]行号范围：1 ~ {len(hist_lines)}[/yellow]")
                        continue
                except ValueError:
                    console.print(f"[red]错误: ! 后面必须接数字[/red]")
                    continue

            # =========================================================================
            # 2. 拦截并处理 临时匿名管道 "|" 运算逻辑
            # =========================================================================

            # 解析命令（支持管道 | 分割，自动处理引号内的 |）
            pipe_segments = split_by_pipe(text)


            # 提取第一条命令的首词，供历史记录过滤使用
            first_word = ''
            if pipe_segments and pipe_segments[0]:
                first_word = pipe_segments[0][0].strip().lower()

            if len(pipe_segments) == 1:
                # 无管道：单命令执行（与原有行为完全一致）
                group.main(args=pipe_segments[0],
                           standalone_mode=False, obj=ctx.obj)
            else:
                # 管道模式：依次执行各段命令，自动传递结果
                _execute_pipe(pipe_segments, group, ctx, console)

            # 成功执行的非黑名单命令才进行持久化记录
            excluded_cmds = {'history', 'h', 'cmd', 'c', 'help'}
            if first_word and first_word not in excluded_cmds:
                try:
                    with open(hist_path, 'a', encoding='utf-8') as f:
                        f.write(text + '\n')
                except Exception:
                    pass

        except (click.Abort):
            # 用户中断（如 Ctrl+C），安全退出当前命令执行，继续提示输入
            console.print("\n[yellow]已中断当前命令执行。[/yellow]")
            continue
        except (EOFError, KeyboardInterrupt):
            break
        except click.ClickException as e:
            # 真正的命令执行失败（前台），安全打印错误提示，不写历史文件
            e.show()
        except Exception as e:
            # 你的业务代码前台崩溃，不写历史文件
            console.print_exception()


def repl_cli_main(
    doc: str = None,
    prompt: str = '> ',
    hist_file: str | Path = None,
    cmd_filenames: list[str] | str = None,
    find_caller_cmds = False,
    on_init: callable = None,
    on_destroy: callable = None,
    console: Console = None
):
    if not console:
        console = Console()

    global DOC, HISTORY_FILE

    DOC = doc
    if DOC:
        console.print(f'[green]{DOC}[/green]')

    init_ctx = None

    import inspect
    caller_frame = inspect.currentframe().f_back

    try:
        # 获取调用者的文件名，用于配置历史文件
        caller_filename = Path(caller_frame.f_code.co_filename).stem
        HISTORY_FILE = Path.cwd() / f'.{caller_filename}.history'

        # 修复：正确判断是否有子命令（非选项参数）
        # 排除脚本名称本身，只取后面的参数
        args = sys.argv[1:]
        # 过滤掉选项参数（以 - 开头）及其值
        # 注意：需要处理 -c config.yaml 这种情况，但 -c 和它的值都应该被跳过
        non_option_args = []
        skip_next = False
        for i, arg in enumerate(args):
            if skip_next:
                skip_next = False
                continue
            if arg.startswith('-'):
                # 如果是选项，检查下一个参数是否为它的值（非选项）
                # 对于短选项如 -c，下一个参数通常是值
                # 对于长选项如 --config-path，同样处理
                if i + 1 < len(args) and not args[i + 1].startswith('-'):
                    skip_next = True
                continue
            non_option_args.append(arg)

        # 判断是否有子命令（非选项参数）
        has_subcommand = len(non_option_args) > 0

        # 收集命令
        cmds = {}
        if cmd_filenames:
            if isinstance(cmd_filenames, str):
                cmd_filenames = [cmd_filenames] # 确保是 list[str]
            for cmd_filename in cmd_filenames:
                    # 动态导入模块
                cmd_module = __import__(cmd_filename) # type: ModuleType

                if cmd_module:
                    # 获取 __all__ 列表（如果没有定义，则用 dir()）
                    exported_names = getattr(cmd_module, '__all__', None)
                    if exported_names is None:
                        # 如果没有 __all__，则查找所有 callable 且不是私有属性的对象
                        exported_names = [name for name in dir(cmd_module) if not name.startswith('_')]

                    for name in exported_names:
                        obj = getattr(cmd_module, name)

                        if callable(obj) and isinstance(obj, click.Command):
                            if name not in cmds: # 防止同名函数覆盖
                                cmds.update({name: obj}) # 检查是否为 click.Command 的构造函数（即调用后返回 Command）
                            else:
                                console.print(f"[W] 在 import {cmd_filename} 发现函数同名 {name}，引入会覆盖")

        else:
            find_caller_cmds = True # 无指定 cmd_filenames 时，直接查找调用层声明的 click.Command

        if find_caller_cmds:
            import inspect
            # 获取调用者的模块
            module_globals = caller_frame.f_globals
            cmds = { name: obj for name, obj in module_globals.items()
                if callable(obj) and isinstance(obj, click.Command) and not name.startswith('_')
            }

        # 创建根命令组
        @click.group(context_settings={'help_option_names': ['-?', '--help', '-h']})
        def main_group():
            pass

        init_ctx = click.Context(main_group, info_name=sys.argv[0])
        init_ctx.obj = {}  # 推荐使用 dict 存放共享数据
        if on_init:
            on_init(init_ctx)
        auto_register_commands(main_group, cmds, show_cmds=False)

        if has_subcommand:
            # 批处理模式
            main_group.main(args=sys.argv[1:], standalone_mode=True, obj=init_ctx.obj)
        else:
            # 交互模式：使用我们重构的现代 REPL
            _show_registered_cmds()
            run_modern_repl(main_group, init_ctx, prompt, str(HISTORY_FILE), console)

    except KeyboardInterrupt:
        console.print("\n[dim]正在退出...[/dim]")


    except Exception as e:
        console.print_exception(extra_lines=5, show_locals=True)

    finally:
        if on_destroy:
            on_destroy(init_ctx)


# 装饰器：为命令注入字段筛选相关的 options，并把一个通用的过滤 helper 放入 ctx.obj['list_field_filter']
def with_field_filter_options(func=None, *, en2cn_map, cn2en_map):
    """Decorator factory that injects field-filter options and a helper into ctx.obj.
    Can be used as `@with_field_filter_options` or `@with_field_filter_options(en2cn_map=..., cn2en_map=...)`.
    """
    def _decorate(f):
        f = click.option('-f', '--field', 'fields', multiple=True, callback=split_comma,
                         help='显示特定字段')(f)
        f = click.option('-fc', '--field-contain', 'field_contains', multiple=True, callback=split_comma,
                         help='字段包含特定字符串')(f)
        f = click.option('-t', '--translate', 'translate', type=click.Choice(['en', 'cn'], case_sensitive=False),
                         default='cn', help='翻译字段名称（en: 英文，cn: 中文）')(f)
        f = click.option('-sf', '--show-field', 'is_show_field', is_flag=True, help='显示字段信息')(f)

        @functools.wraps(f)
        @click.pass_context
        def wrapper(ctx: click.Context, *args, **kwargs):
            fields = kwargs.get('fields', []) or []
            field_contains = kwargs.get('field_contains', []) or []
            translate = kwargs.get('translate', 'cn')
            is_show_field = kwargs.get('is_show_field', False)

            CONSOLE = ctx.obj['console'] if hasattr(ctx, 'obj') and 'console' in ctx.obj else Console()

            # 允许从外部传入映射，否则回退到模块级常量
            en2cn = en2cn_map if en2cn_map is not None else {}
            cn2en = cn2en_map if cn2en_map is not None else {}

            def filter_list_of_dicts(list_dicts: List[dict], keep_non_empty=True):
                en_fields_to_show = set()

                # 处理显式字段
                for f0 in fields:
                    if has_chinese(f0):
                        f_en = cn2en.get(f0)
                        if f_en:
                            en_fields_to_show.add(f_en)
                    else:
                        if f0 in en2cn:
                            en_fields_to_show.add(f0)

                # 处理包含匹配
                if field_contains:
                    cn_items = list(cn2en.items())
                    en_keys = list(en2cn.keys())
                    for fc in field_contains:
                        fc_str = fc.strip()
                        if not fc_str:
                            continue
                        if has_chinese(fc_str):
                            for cn, en in cn_items:
                                if fc_str in cn:
                                    en_fields_to_show.add(en)
                        else:
                            fc_lower = fc_str.lower()
                            for en in en_keys:
                                if fc_lower in en.lower():
                                    en_fields_to_show.add(en)

                # 执行筛选与翻译
                if en_fields_to_show:
                    filtered = []
                    for d in list_dicts:
                        nd = {k: v for k, v in d.items() if k in en_fields_to_show and (not keep_non_empty or v)}
                        if nd:
                            filtered.append(nd)
                    list_dicts = filtered

                if translate and str(translate).lower() == 'cn':
                    list_dicts = [
                        {en2cn.get(k, k): v for k, v in d.items() if (not keep_non_empty or v)}
                        for d in list_dicts
                    ]

                return list_dicts

            ctx.obj = ctx.obj or {}
            ctx.obj['list_field_filter'] = filter_list_of_dicts

            ret = ctx.invoke(f, *args, **kwargs)

            # 如果被请求，装饰器负责显示字段信息（依赖被装饰函数返回样本列表或样本对象）
            if is_show_field and ret:
                    df_fields = pd.DataFrame({
                        'EN': list(en2cn.keys()),
                        'CN': list(en2cn.values())
                    })
                    print_dataframe(df=df_fields, title=f"字段信息（共 {len(en2cn.keys())} 字段）", printer=CONSOLE.print)

            return ret

        return wrapper

    # 支持不带参数直接使用的场景
    if func is None:
        return _decorate
    else:
        return _decorate(func)

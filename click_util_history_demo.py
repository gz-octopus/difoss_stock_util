#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示 click_util 的历史命令功能

使用示例：
    python click_util_history_demo.py          # 进入交互模式
    python click_util_history_demo.py hello    # 批处理模式

交互模式中的命令：
    > hello          # 执行 hello 命令
    > world          # 执行 world 命令
    > history        # 查看所有历史命令
    > history -n 5   # 查看最后 5 条历史命令
    > history --all  # 查看所有历史命令（带行号）
    > h              # history 的缩写
    > exit           # 退出交互模式
"""

import sys
sys.path.insert(0, r'd:\job_\open_source_\difoss-stock-util')

from difoss_stock_util.click_util import repl_cli_main, command_with_abbrev
import click


@command_with_abbrev(abbrev='h1')
@click.argument('name', default='World')
def hello(name):
    """问候命令"""
    print(f"Hello, {name}!")


@command_with_abbrev(abbrev='w')
def world():
    """世界命令"""
    print("Welcome to the world!")


@command_with_abbrev(abbrev=None)  # 使用默认缩写
@click.option('-c', '--count', type=int, default=3)
def greet(count):
    """多次问候"""
    for i in range(count):
        print(f"Greeting #{i+1}")


if __name__ == '__main__':
    repl_cli_main(
        doc='演示 REPL 历史命令功能',
        prompt='demo> ',
        find_caller_cmds=True  # 自动查找当前模块中的 click 命令
    )

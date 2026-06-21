# encoding: utf-8

import sys
from difoss_stock_util import *

if __name__ == '__main__':
    argv = sys.argv
    if len(argv) > 1:
        from difoss_stock_util.color_log_util import *

a = 12.3
b = [ x for x in range(10) ]
c = { x: f"{x*2}" for x in range(10) }

D(a=a, b=b, c=c)

# ------------------------------------------------------
import click

def safe_color_print(text, **style_args):
    """安全地输出带颜色的文本"""
    ctx = click.get_current_context(silent=True)
    
    # 如果有上下文且颜色被禁用，则不使用颜色
    if ctx and ctx.color == False:
        print(text)
    else:
        print(click.style(text, **style_args))

# 使用示例
safe_color_print("Hello World", fg="red", bold=True)

# ------------------------------------------------------
import os

def is_color_supported():
    # 检查是否明确禁用颜色
    if os.environ.get('NO_COLOR'):
        return False
    
    # 检查TERM环境变量
    term = os.environ.get('TERM', '')
    if term and term != 'dumb':
        return True
    
    # 检查平台
    if os.name == 'nt':  # Windows
        # Windows 10+ 支持颜色
        return True
    
    return False

if is_color_supported():
    print(click.style("颜色支持已启用", fg="cyan"))
else:
    print("颜色支持已禁用")
    
# ------------------------------------------------------
import colorama
from colorama import just_fix_windows_console

# 初始化colorama（会自动处理Windows控制台）
just_fix_windows_console()

def check_with_colorama():
    # colorama初始化后会设置适当的支持
    return True  # colorama会处理底层细节

if check_with_colorama():
    print(click.style("使用colorama确保颜色支持", fg="yellow"))
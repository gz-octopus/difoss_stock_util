#!python
# encoding: utf-8
# author: DifossChan
#

__all__ = (
    'get_printable',
    'set_printable',
    'colorful_key_value',
    'P', 'T', 'D', 'I', 'W', 'E',
    'print_error',
    'print_warning',
    'print_info',
    'print_debug',
    'print_trace',
    'print_xxx',
    'cursor_set_position',
    'cursor_set_x',
)

import json
import sys
import io
import click
from colorama import just_fix_windows_console

# 初始化colorama（会自动处理Windows控制台）
just_fix_windows_console()

__printable = True


def get_printable() -> bool:
    global __printable
    return __printable

def set_printable(d: bool):
    global __printable
    __printable = d

def colorful_key_value(k, v, key_color='bright_blue', value_color=None) -> str:
    return '%s=%s' % (click.style(str(k), fg=key_color), click.style(str(v), fg=value_color) if value_color else v)

def print_xxx(*args, **kwargs):
    must = kwargs.pop('_must', False)
    global __printable
    if must or __printable:
        color = kwargs.pop('_color', 'green')
        key_color = kwargs.pop('_key_color', 'bright_blue')
        value_color = kwargs.pop('_value_color', None)
        level = kwargs.pop('_level', 'DEBUG')
        file = kwargs.pop('_file', sys.stderr)
        indent = kwargs.pop('_indent', None)
        printer = kwargs.pop('_printer', print)

        printer('[%s]' % (click.style(level, fg=color),), *args,
              ', '.join([colorful_key_value(k, v if not indent else json.dumps(v, indent=indent, ensure_ascii=False), key_color, value_color)
                         for k, v in kwargs.items()]),
              file=file)

def print_error(*args, **kwargs):
    print_xxx(_level=kwargs.pop('_level', 'ERROR'),
              _color=kwargs.pop('_color', 'bright_red'),
              _file=kwargs.pop('_file', sys.stderr),
              *args, **kwargs)

def print_warning(*args, **kwargs):
    print_xxx(_level=kwargs.pop('_level', 'WARNING'),
              _color=kwargs.pop('_color', 'magenta'),
              _file=kwargs.pop('_file', sys.stdout),
              *args, **kwargs)

def print_info(*args, **kwargs):
    print_xxx(_level=kwargs.pop('_level', 'INFO'),
              _color=kwargs.pop('_color', 'yellow'),
              _file=kwargs.pop('_file', sys.stdout),
              *args, **kwargs)

def print_debug(*args, **kwargs):
    print_xxx(_level=kwargs.pop('_level', 'DEBUG'),
              _color=kwargs.pop('_color', 'cyan'),
              _file=kwargs.pop('_file', sys.stdout),
              *args, **kwargs)

def print_trace(*args, **kwargs):
    print_xxx(_level=kwargs.pop('_level', 'TRACE'),
              _color=kwargs.pop('_color', 'bright_green'),
              _file=kwargs.pop('_file', sys.stdout),
              *args, **kwargs)

# Shortest way to print log for difference type...
E = print_error
W = print_warning
I = print_info
D = print_debug
T = print_trace
P = print_xxx

# cursor
def cursor_set_position(x, y):
    return "\033[%d;%dH" % (y,x)

def cursor_set_x(x = 0):
    return "\033[;%dH"

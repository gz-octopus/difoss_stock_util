#!python
# encoding: utf-8
# author: DifossChan
#

__all__ = (
    'get_printable',
    'set_printable',
    'P', 'T', 'D', 'I', 'W', 'E',
    'print_error',
    'print_warning',
    'print_info',
    'print_debug',
    'print_trace',
    'print_xxx',
)

import json
import sys
import io

__printable = True


def get_printable() -> bool:
    global __printable
    return __printable

def set_printable(d: bool):
    global __printable
    __printable = d

def print_xxx(*args, **kwargs):
    must = kwargs.pop('_must', False)
    global __printable
    if must or __printable:
        level = kwargs.pop('_level', 'DEBUG')
        file = kwargs.pop('_file', sys.stderr)
        indent = kwargs.pop('_indent', None)

        print('[%s]' % (level,), *args,
              ', '.join(['%s=%s' % (k, v if not indent else json.dumps(v, indent=indent, ensure_ascii=False))
                         for k, v in kwargs.items()]),
              file=file)

def print_error(*args, **kwargs):
    print_xxx(_level=kwargs.pop('_level', 'ERROR'),
              _file=kwargs.pop('_file', sys.stderr),
              *args, **kwargs)

def print_warning(*args, **kwargs):
    print_xxx(_level=kwargs.pop('_level', 'WARNING'),
              _file=kwargs.pop('_file', sys.stdout),
              *args, **kwargs)

def print_info(*args, **kwargs):
    print_xxx(_level=kwargs.pop('_level', 'INFO'),
              _file=kwargs.pop('_file', sys.stdout),
              *args, **kwargs)

def print_debug(*args, **kwargs):
    print_xxx(_level=kwargs.pop('_level', 'DEBUG'),
              _file=kwargs.pop('_file', sys.stdout),
              *args, **kwargs)

def print_trace(*args, **kwargs):
    print_xxx(_level=kwargs.pop('_level', 'TRACE'),
              _file=kwargs.pop('_file', sys.stdout),
              *args, **kwargs)


# Shortest way to print log for difference type...
E = print_error
W = print_warning
I = print_info
D = print_debug
T = print_trace
P = print_xxx

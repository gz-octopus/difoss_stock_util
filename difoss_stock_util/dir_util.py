#!python
# -*- coding:utf-8 -*-
# author: difosschan
#

__all__ = ('walk', 'get_file_info')

import os
from typing import Tuple, List
# from .log_util import P

def get_file_info(fullname):
    (file_path, temp_filename) = os.path.split(fullname)
    (short_name, extension) = os.path.splitext(temp_filename)
    return {'short_name': short_name, 'extension': extension, 'path': file_path}

def walk_tail_recursive(input_dir: str, dirs=[], files=[],
             exclude_dirs=None,
             exclude_files=None,
             exclude_extensions=None,
             include_extensions=None):
    '''walk'''
    fileList = os.listdir(input_dir)

    for file in fileList:
        # P(file=file,  _level='WARN', _must=True, _file=None)
        filePath = os.path.join(input_dir, file)
        if os.path.isdir(filePath):
            if exclude_dirs and file in exclude_dirs:
                # P("IGNORE dir cause exclude-dirs", dir=file)
                continue
            dirs.append(filePath)
            walk_tail_recursive(filePath, dirs, files, exclude_dirs, exclude_files, exclude_extensions, include_extensions)

        elif os.path.isfile(filePath):
            ext = get_file_info(file)['extension']
            if exclude_files and file in exclude_files:
                # P("IGNORE file cause exclude-files", file=file)
                continue
            elif exclude_extensions and ext in exclude_extensions:
                # P("IGNORE file cause match exclude-extensions", file=file, ext=ext)
                continue

            if include_extensions and ext not in include_extensions:
                # P("IGNORE file cause not match include-extensions", file=file, ext=ext)
                continue
            files.append(filePath)


def walk(input_dir: str = './',
         exclude_dirs: list=None,
         exclude_files: list=None,
         exclude_extensions: list=None,
         include_extensions: list=None,
         without_root_path: bool = False,
         **kwargs) -> Tuple[List[str], List[str]]:

    dirs = []
    files = []
    input_dir = os.path.normpath(input_dir)

    walk_tail_recursive(input_dir, dirs, files, exclude_dirs, exclude_files, exclude_extensions, include_extensions)

    if without_root_path:
        dirs = [os.path.relpath(path, input_dir) for path in dirs]
        files = [os.path.relpath(path, input_dir) for path in files]

    return dirs, files

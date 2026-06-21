# encoding: utf-8

__all__ = [
    'trace_func',
    'trace_function',
    'create_limiter',
    'str_to_range',
    'read_yaml_config',
    'print_locals',
    'find_list_diff',
]

from typing import Callable, Any, Optional, Dict, Union
from .color_log_util import *
from .time_util import TimeUtils
import functools
import time
import yaml, re, os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False

def trace_func(func: Callable) -> Callable:
    """
    装饰器：在函数进入和退出时打印函数名
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        T(f"{func.__name__}", _level='ENTER')
        try:
            result = func(*args, **kwargs)
            T(f"{func.__name__}", _level='EXIT ')
            return result
        except Exception as e:
            E(f"{func.__name__}", exception=e, _level='EXIT ')
            raise

    return wrapper


def trace_function(func: Callable) -> Callable:
    """
    装饰器：在函数进入和退出时打印函数名和耗时
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        # 记录开始时间
        start_time = time.time()
        start_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))

        T(f"{func.__name__}", 开始时间=start_str, _level='ENTER')

        try:
            result = func(*args, **kwargs)

            # 记录结束时间
            end_time = time.time()
            end_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time))
            duration = end_time - start_time
            duration_str = TimeUtils.format_duration(duration)

            T(f"{func.__name__}", 结束时间=end_str, 耗时=duration_str, _level='EXIT ')
            return result

        except Exception as e:
            # 发生异常时也记录耗时
            end_time = time.time()
            duration = end_time - start_time
            duration_str = TimeUtils.format_duration(duration)

            E(f"{func.__name__}", 异常退出=end_str, 耗时=duration_str, _level='EXIT ')
            raise

    return wrapper


def create_limiter(count):
    """创建限制执行次数的限制器（count < 0 时不限制）
    """
    counter = 0
    def limiter():
        nonlocal counter
        if count < 0:
            return True

        if counter < count:
            counter += 1
            return True
        return False
    return limiter


def str_to_range(s: str, valid_range = (0, 100), sep = ',', maxsplit=-1, type_changer: Callable=int, order_sensitive=False) -> tuple[int]:
    valid_lower, valid_upper = valid_range
    range_vec = s.split(sep, maxsplit)
    if len(range_vec) == 1:
        lower = upper = type_changer(range_vec[0])
    elif len(range_vec) == 2:
        lower = type_changer(range_vec[0])
        upper = type_changer(range_vec[1])
    else:
        raise Exception(f"'{s}' 文本格式错误，应为逗号分隔的两个整数（如：0,30） 或者 单一整数（如：20）")

    if not order_sensitive:
        l = min(lower, upper)
        u = max(lower, upper)
        lower, upper = l, u

    if lower < valid_lower or lower > valid_upper or upper < valid_lower or upper > valid_upper:
        raise Exception("out of range")

    return lower, upper


class ConfigParser:
    def __init__(self, config: Union[Dict, str]):
        self.config = config

    def _expand_value(self, value: Any) -> Any:
        """递归展开配置值中的环境变量"""
        if isinstance(value, str):
            # 支持 ${VAR} 和 $VAR 两种格式
            def replace_match(match):
                var_name = match.group(1) or match.group(2)

                # 支持默认值：${VAR:-default}
                if ':-' in var_name:
                    var_name, default_value = var_name.split(':-', 1)
                    return os.getenv(var_name, default_value)

                # 支持必需变量：${VAR:?error message}
                if ':?' in var_name:
                    var_name, error_msg = var_name.split(':?', 1)
                    value = os.getenv(var_name)
                    if value is None:
                        raise ValueError(f"必需的环境变量缺失: {error_msg or var_name}")
                    return value

                # 普通变量
                return os.getenv(var_name) or match.group(0)

            # 匹配 ${VAR} 或 $VAR
            pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
            return re.sub(pattern, replace_match, value)

        elif isinstance(value, dict):
            return {k: self._expand_value(v) for k, v in value.items()}

        elif isinstance(value, list):
            return [self._expand_value(item) for item in value]

        else:
            return value

    def parse(self) -> Dict:
        """解析配置"""
        return self._expand_value(self.config)


def read_yaml_config(cfg_filepath='config.yaml') -> Optional[dict]:
    """读取yaml配置文件（支持环境变量和 .env 自动加载）

    在解析配置前自动加载配置文件同目录下的 .env 文件（如果存在）。
    需要 python-dotenv 包支持；无此包时仅使用系统环境变量。
    """
    if not cfg_filepath:
        cfg_filepath = 'config.yaml'

    # 自动加载配置文件同目录下的 .env
    if _HAS_DOTENV:
        cfg_path = Path(cfg_filepath).resolve()
        env_file = cfg_path.parent / '.env'
        if env_file.exists():
            load_dotenv(env_file)

    with open(cfg_filepath, 'r', encoding='utf-8') as stream:
        try:
            cfg_str = stream.read()
            cfg_dict = yaml.safe_load(cfg_str)
            parser = ConfigParser(cfg_dict)
            return parser.parse()

        except yaml.YAMLError as e:
            print(e)
    return None


import inspect
from typing import Optional, Callable, Any

def _add_type_to_key(k: str, v: Any):
    type_name = type(v).__name__
    return f'{k} ({type_name})'

def print_locals(
    show_null: bool = False,
    show_caller: bool = False,
    show_type: bool = False,
    show_private: bool = False,
    max_length: int = 14,
    include_module: bool = False,
    exclude_names: Optional[list] = None,
    printer: Optional[Callable] = None,
    frame_offset: int = 0  # 默认向上找一层
) -> None:
    """
    打印调用者的局部变量（或指定堆栈层的局部变量）

    Args:
        show_null: 是否显示空值（False=过滤空值）
        show_caller: 是否显示调用者信息
        show_type: 是否显示变量类型
        show_private: 是否显示私有变量
        max_length: 字符串最大显示长度
        include_module: 是否在调用者信息中包含模块名
        exclude_names: 要排除的变量名列表
        printer: 自定义打印函数，默认使用 print_info
        frame_offset: 堆栈层偏移，0=（调用 print_locals 的）当前函数，1=调用者，2=调用者的调用者

    用于替代：
    I(**{k:v for k,v in locals().items() if v}, _level='PARAMETER(OUTER)')

    """
    # 获取调用堆栈
    try:
        # 获取指定深度的帧
        frame = inspect.currentframe()
        for _ in range(frame_offset + 1):  # +1 因为要跳过当前函数本身
            if frame:
                frame = frame.f_back

        if not frame:
            if printer:
                printer("[WARNING] 无法获取调用堆栈信息")
            else:
                I("无法获取调用堆栈信息", _level="WARNING")
            return

        # 获取局部变量
        local_vars = frame.f_locals
        
        filtered_vars = {}
        if not show_null:
            # 过滤掉 None 或空值
            for k, v in local_vars.items():
                # 排除私有（如需要）
                if (not show_private) and k.startswith('_'):
                    continue
                # 处理排除的变量名
                if exclude_names and k in exclude_names:
                    continue
                if v:
                    # 如果是字符串且为空，跳过
                    if isinstance(v, str) and not v.strip():
                        continue
                    # 如果是容器且为空，跳过
                    elif hasattr(v, '__len__') and len(v) == 0:
                        continue

                    filtered_vars[_add_type_to_key(k, v) if show_type else k] = v
        else:
            for k, v in local_vars.items():
                # 排除私有（如需要）
                if (not show_private) and k.startswith('_'):
                    continue
                # 处理排除的变量名
                if exclude_names and k in exclude_names:
                    continue
                filtered_vars[_add_type_to_key(k, v) if show_type else k] = v

        if not filtered_vars:
            if printer:
                printer(f"[INFO] {frame.f_code.co_name} 没有可打印的局部变量")
            else:
                I(f" {frame.f_code.co_name} 没有可打印的局部变量", _level="INFO")
            return

        if max_length > 0:
            for name, value in filtered_vars.items():
                # 处理超长字符串
                if isinstance(value, (str, list, set)) and len(value) > max_length:
                    if isinstance(value, str):
                        truncated = value[:max_length] + f"...[{len(value)} chars]"
                        filtered_vars.update({name: truncated})
                    elif isinstance(value, (list)): # 处理超长数组
                        truncated = str(value[:max_length])[:-1] + f"... {len(value)} items]"
                        filtered_vars.update({name: truncated})
                    elif isinstance(value, set):
                        truncated = "{"+ ', '.join(list(value)[:max_length]) + f"... {len(value)} items]" + "}"
                        filtered_vars.update({name: truncated})

        # 获取调用者信息
        if show_caller:
            module_info = ""
            if include_module:
                module_name = frame.f_globals.get('__name__', '<module>')
                module_info = f"{module_name}."
                
            caller_info = f"{module_info}{frame.f_code.co_name}() in {frame.f_code.co_filename}:{frame.f_lineno}"
            if printer:
                printer(f"[PARAMETER] 局部变量 [来自 {caller_info}]")
            else:
                I(f"局部变量 [来自 {caller_info}]", _level='PARAMETER')

        if printer:
            printer(f"[PARAMETER] {filtered_vars}")
        else:
            I(**filtered_vars, _level='PARAMETER')
    finally:
        # 防止循环引用
        del frame


# 使用示例
def example_function(a, b, c=None):
    x = "test"
    y = None
    z = [1, 2, 3]

    # 基础用法：打印当前函数的局部变量
    print_locals(frame_offset=0)

    # 忽略空值，向上两层
    print_locals(frame_offset=2)

    # 增强版：显示类型，排除特定变量
    print_locals(
        exclude_names=['x'],  # 排除变量 x
        show_type=True,
        max_length=50
    )

# ---------------------------------------------------------------------------------------------------
def rename_dict_keys(data: dict, mapping: dict[str, str]):
    """直接重命名字典的key"""
    return {mapping.get(k, k): v for k, v in data.items()}


def rename_dict_keys_recursive(data: dict, mapping: dict[str, str], max_depth=10, current_depth=0):
    """递归重命名字典键，支持嵌套字典"""
    if current_depth >= max_depth:
        return data
    
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # 重命名当前键
            new_key = mapping.get(key, key)
            
            # 递归处理值
            if isinstance(value, (dict, list)):
                result[new_key] = rename_dict_keys_recursive(
                    value, mapping, max_depth, current_depth + 1
                )
            else:
                result[new_key] = value
        return result
    
    elif isinstance(data, list):
        return [
            rename_dict_keys_recursive(item, mapping, max_depth, current_depth + 1)
            for item in data
        ]
    
    else:
        return data


def rename_dict_keys_inplace(data: dict, mapping: dict[str, str]):
    """原地修改字典键"""
    keys_to_rename = list(data.keys())
    
    for old_key in keys_to_rename:
        if old_key in mapping:
            new_key = mapping[old_key]
            if new_key != old_key:
                data[new_key] = data.pop(old_key)
    
    return data

# ---------------------------------------------------------------------------------------------------

def find_list_diff(list1: list, list2: list):
    """使用集合找出差异（元素不重复的情况）"""
    set1 = set(list1)
    set2 = set(list2)
    
    # 找出差异
    only_in_list1 = set1 - set2
    only_in_list2 = set2 - set1
    common = set1 & set2
    
    return {
        'only_in_list1': sorted(only_in_list1),
        'only_in_list2': sorted(only_in_list2),
        'common': sorted(common),
        'is_equal': set1 == set2,
        'total_diff': len(only_in_list1) + len(only_in_list2)
    }


def t_print_locals():
    # 替换原来的复杂代码
    print_locals(show_null=True, frame_offset=0)

    # 或者使用增强版
    print_locals(
        show_null=True,
        show_type=True,
        max_length=100
    )

    # 原来的用法仍然有效
    print("-------------- example_function ---------------")
    example_function(1, "test")

if __name__ == "__main__":
    t_print_locals()

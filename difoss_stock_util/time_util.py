#!python
# encoding: utf-8
# author: DifossChen
#

__all__ = [
    'TimestampMixin',
    'IntegerDate', 'BigIntegerDateTime', 'TimeUtils',
]

from sqlalchemy import TypeDecorator, BigInteger, Integer
from datetime import datetime, timedelta, date
from typing import Optional, Union, List, ClassVar, TypeVar, Any, Callable
import functools
import time
import yaml, re, os

from difoss_stock_util.color_log_util import *

TIME_COUNT_FORMAT_DICT = {
    1: "%Y",
    2: "%Y-%m",
    3: "%Y-%m-%d",
    4: "%Y-%m-%d-%H",
    5: "%Y-%m-%d-%H-%M",
    6: "%Y-%m-%d-%H-%M-%S",
}
COUNT_REG = re.compile(r"\d{1,4}")

class TimestampMixin:
    """时间戳混合类，提供常用时间方法"""

    def to_datetime(self):
        """将时间戳转换为 datetime 对象"""
        if hasattr(self, 'Time'):
            return self.Time
        return None

    def to_iso_format(self):
        """转换为 ISO 格式字符串"""
        dt = self.to_datetime()
        return dt.isoformat() if dt else None

    def to_date_string(self):
        """转换为日期字符串 (YYYY-MM-DD)"""
        dt = self.to_datetime()
        return dt.strftime('%Y-%m-%d') if dt else None

    def is_same_day(self, other_timestamp):
        """判断是否同一天"""
        if not hasattr(self, 'Time') or not hasattr(other_timestamp, 'Time'):
            return False
        self_date = self.to_datetime().date()
        other_date = datetime.fromtimestamp(other_timestamp.Time / 1000.0).date()
        return self_date == other_date


class IntegerDate(TypeDecorator):
    """自定义：Integer（数据库内）与 date（内存）在 日期 中自动转换"""
    impl = Integer
    cache_ok = True

    # 特殊值常量
    INFINITE_DATE_INT: ClassVar[int] = 99999999
    INFINITE_DATE: ClassVar[date] = date(9999, 12, 31)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def date_to_int_not_throw(date_value: Optional[Union[date, str, int]]) -> Optional[int]:
        try:
            return IntegerDate.date_to_int(date_value)
        except Exception as e:
            return None

    @staticmethod
    def int_to_date_not_throw(int_value: Optional[int]) -> Optional[date]:
        try:
            return IntegerDate.int_to_date(int_value)
        except Exception as e:
            return None

    @staticmethod
    def date_to_int(date_value: Optional[Union[date, str, int]]) -> Optional[int]:
        """
        将日期转换为整数格式 YYYYMMDD

        参数:
            date_value: 可以是 date、字符串 'YYYY-MM-DD'、整数或 None

        返回:
            int: YYYYMMDD 格式的整数，或 99999999 表示无限大
        """
        if not date_value:
            return None

        # 如果已经是整数
        if isinstance(date_value, int):
            # 验证整数的有效性
            if date_value == IntegerDate.INFINITE_DATE_INT:
                return date_value
            elif 10000101 <= date_value <= 99991231:
                # 基本验证日期格式
                return date_value
            else:
                raise ValueError(f"Invalid date integer: {date_value}. Must be between 10000101 and 99991231, or 99999999 for infinite date.")

        # 如果是字符串
        elif isinstance(date_value, str):
            # 特殊处理 'infinite' 字符串
            if date_value.upper() in ('INFINITE', '9999-12-31', '99999999'):
                return IntegerDate.INFINITE_DATE_INT
            try:
                if '-' in date_value:
                    # 尝试解析 YYYY-MM-DD 格式
                    date_obj = datetime.strptime(date_value, '%Y-%m-%d').date()
                else:
                    # 尝试解析 YYYYMMDD 格式
                    date_obj = datetime.strptime(date_value, '%Y%m%d').date()
            except ValueError:
                raise ValueError(f"Invalid date string: {date_value}. Expected format: YYYY-MM-DD or YYYYMMDD")

        # 如果是 date 对象
        elif isinstance(date_value, date):
            date_obj = date_value

        else:
            raise TypeError(f"Unsupported type for date conversion: {type(date_value)}")

        # 检查是否为无限大日期
        if date_obj.year == 9999 and date_obj.month == 12 and date_obj.day == 31:
            return IntegerDate.INFINITE_DATE_INT

        # 转换为整数
        return date_obj.year * 10000 + date_obj.month * 100 + date_obj.day

    @staticmethod
    def int_to_date(int_value: Optional[int]) -> Optional[date]:
        """
        将整数转换为 date 或特殊标记

        参数:
            int_value: YYYYMMDD 格式的整数或 None

        返回:
            date 或字符串 'INFINITE'
        """
        if not int_value:
            return None

        if int_value == IntegerDate.INFINITE_DATE_INT:
            return IntegerDate.INFINITE_DATE

        # 解析整数为日期
        year = int_value // 10000
        month = (int_value % 10000) // 100
        day = int_value % 100

        # 验证日期有效性
        try:
            return date(year, month, day)
        except ValueError as e:
            raise ValueError(f"Invalid date integer: {int_value}. {e}")


    def process_bind_param(self, value: Any, dialect) -> Optional[int]:
        """
        将 Python 值转换为数据库值（写入数据库时调用）
        """
        if value is None:
            return None

        return self.date_to_int(value)

    def process_result_value(self, value: Any, dialect) -> Optional[date]:
        """
        将数据库值转换为 Python 值（从数据库读取时调用）

        注意：这里返回整数而不是 date，因为要求返回 int 值
        但提供选项可以返回 date
        """
        if value is None:
            return None

        # 如果值已经是整数，直接返回（根据要求）
        if isinstance(value, int):
            return value

        # 如果是字符串，尝试转换（某些数据库可能返回字符串）
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                # 可能是数据库格式的日期字符串
                try:
                    date_obj = datetime.strptime(value, '%Y-%m-%d').date()
                    if date_obj.year == 9999 and date_obj.month == 12 and date_obj.day == 31:
                        return self.INFINITE_DATE_INT
                    return date_obj.year * 10000 + date_obj.month * 100 + date_obj.day
                except ValueError:
                    raise ValueError(f"Cannot convert database value to date: {value}")

        # 其他情况，尝试转换为整数
        try:
            return int(value)
        except (ValueError, TypeError):
            raise TypeError(f"Unexpected type from database: {type(value)}")

    def process_literal_param(self, value: Any, dialect):
        """
        处理字面量参数（用于 SQL 编译）
        """
        return self.process_bind_param(value, dialect)

    @property
    def python_type(self):
        """
        定义 Python 端的数据类型
        """
        return int


class BigIntegerDateTime(TypeDecorator):
    """自定义类型：BigInteger 与 datetime 的自动转换"""

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value, dialect) -> Optional[int]:
        """将 datetime 转换为 BigInteger（存储到数据库）"""
        if value is None:
            return None
        elif isinstance(value, datetime):
            return int(value.timestamp() * 1000)
        elif isinstance(value, (int, float)):
            return int(value)
        elif isinstance(value, str):
            # 尝试解析字符串
            try:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return int(dt.timestamp() * 1000)
            except ValueError:
                raise ValueError(f"无法解析时间字符串: {value}")
        else:
            raise ValueError(f"不支持的时间格式: {type(value)}")

    def process_result_value(self, value, dialect) -> Optional[datetime]:
        """将 BigInteger 转换为 datetime（从数据库读取）"""
        if value is None:
            return None
        # 将毫秒级时间戳转换为 datetime
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000)
        return value  # 如果已经是 datetime 对象，直接返回


class TimeUtils:
    """时间工具类"""

    @staticmethod
    def datetime_to_ms(dt):
        """datetime 转换为毫秒时间戳"""
        if dt is None:
            return None
        if isinstance(dt, (int, float)):
            return int(dt)
        return int(dt.timestamp() * 1000)

    @staticmethod
    def ms_to_datetime(timestamp_ms: int):
        """毫秒时间戳转换为 datetime"""
        if timestamp_ms is None:
            return None
        return datetime.fromtimestamp(timestamp_ms / 1000.0)

    @staticmethod
    def now_ms():
        """当前时间的毫秒时间戳"""
        import time as _time
        return int(_time.time() * 1000)

    @staticmethod
    def today_start_ms():
        """今天开始的毫秒时间戳"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return TimeUtils.datetime_to_ms(today)

    @staticmethod
    def date_to_ms(date_str, format='%Y-%m-%d'):
        """日期字符串转换为毫秒时间戳"""
        dt = datetime.strptime(date_str, format)
        return TimeUtils.datetime_to_ms(dt)

    @staticmethod
    def ms_to_date_str(timestamp_ms, format='%Y-%m-%d'):
        """毫秒时间戳转换为日期字符串"""
        dt = TimeUtils.ms_to_datetime(timestamp_ms)
        return dt.strftime(format) if dt else None

    @staticmethod
    def str_to_datetime(date_str: str, format=None) -> Optional[datetime]:
        """日期字符串转换为 datetime 对象"""
        if not date_str:
            return None
        
        try:
            if format:
                return datetime.strptime(date_str, format)

            if '-' not in date_str and '/' not in date_str and date_str.isdigit():
                if len(date_str) == 8: # YYYYMMDD
                    if int(date_str) == IntegerDate.INFINITE_DATE_INT:
                        return IntegerDate.INFINITE_DATE
                    return datetime.strptime(date_str, '%Y%m%d')
                elif len(date_str) == 14: # YYYYMMDDHHmmSS
                    return datetime.strptime(date_str, '%Y%m%d%H%M%S')

            matches = COUNT_REG.findall(date_str)
            time_format = TIME_COUNT_FORMAT_DICT.get(len(matches), None)
            date_str = '-'.join(matches)
            if time_format:
                return datetime.strptime(date_str, time_format)

        except ValueError:
            raise

    @staticmethod
    def format_ms(timestamp_ms: int, format='%Y-%m-%d %H:%M:%S'):
        """格式化毫秒时间戳"""
        dt = TimeUtils.ms_to_datetime(timestamp_ms)
        return dt.strftime(format) if dt else None

    @staticmethod
    def format_datetime(dt: datetime, format='%Y-%m-%d %H:%M:%S'):
        return dt.strftime(format) if dt else None

    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        将秒数格式化为 x天x小时x分x秒x毫秒 的格式
        """
        # 使用timedelta来处理时间格式化
        td = timedelta(seconds=seconds)

        days = td.days
        hours, remainder = divmod(td.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = int(td.microseconds / 1000)

        parts = []
        if days > 0:
            parts.append(f"{days}天")
        if hours > 0:
            parts.append(f"{hours}小时")
        if minutes > 0:
            parts.append(f"{minutes}分")
        if seconds > 0 or (days == 0 and hours == 0 and minutes == 0):
            # 如果没有天、小时、分钟，或者秒数大于0，则显示秒
            parts.append(f"{seconds}秒")
        if milliseconds > 0: # and seconds < 1:
            # 如果总时间小于1秒，显示毫秒
            parts.append(f"{milliseconds}毫秒")

        return "".join(parts) if parts else "0毫秒"

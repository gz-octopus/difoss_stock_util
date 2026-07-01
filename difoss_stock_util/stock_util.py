# encoding: utf-8


__all__ = [
    'get_details',
    'calc_belong_trading_day',
    'is_trading_day',
    'calc_count_of_trading_days',
    'calc_next_trading_day',
    'calc_previous_trading_day',
    'TradingInfo',
    'is_st_stock',
]

import traceback
from .log_util import *
from .time_util import TimeUtils
from .security_util import *
from typing import List, Union, Dict, Tuple, Optional, ClassVar
from datetime import datetime, timedelta, date, time
from chinese_calendar import is_workday
from chinese_calendar.constants import holidays
from functools import lru_cache
import pandas as pd

MIN_YEAR, MAX_YEAR = min(holidays.keys()).year, max(holidays.keys()).year

def get_details(stock_codes=[], sectors=['沪深A股'], upper_limit=None,
                security_types: List[SecurityCode] = [SecurityType.STOCK]) -> Dict[str, Dict]:

    import xtquant.xtdata as xtdata
    xtdata.enable_hello = False

    code_2_detail = {}

    if not security_types:
        security_types = [] # 保证不空

    stocks: List[SecurityCode] = []
    for stock_code in stock_codes if stock_codes else []:
        if not isinstance(stock_code, SecurityCode):
            stocks.append(SecurityCode(stock_code))
        else:
            stocks.append(stock_code)

    if sectors:
        for sector in sectors:
            securities = xtdata.get_stock_list_in_sector(sector)

            print("[DEBUG] securities:", securities)

            # 仅保留证券类型为“股票”的标的，放入 stock_codes 中
            for security in securities if securities else []:
                code = SecurityCode(security)
                if code.security_type in security_types:
                    stocks.append(security)

            # 检测数量限制
            if upper_limit and len(code_2_detail) >= upper_limit:
                break

    for stock in stocks:
        detail = xtdata.get_instrument_detail(stock.full_code)

        code_2_detail.update({stock.full_code: detail})

    return code_2_detail

@lru_cache(maxsize=None)
def is_trading_day(d: date) -> bool:
    """判断给定日期是否为交易日"""
    # 2004~2025 的年份限制由 chinese_calendar 库而定，以后需要修改
    weather_workday = is_workday(d) if (d.year >= MIN_YEAR and d.year <= MAX_YEAR) else True
    return weather_workday and d.weekday() <= 4  # 如果是工作日或周一到周五

def calc_count_of_trading_days(start_date: date, end_date: date) -> int:
    """计算两个日期之间的交易日数量"""
    count = 0
    current_date = start_date
    while current_date <= end_date:
        if is_trading_day(current_date):
            count += 1
        current_date += timedelta(days=1)
    return count

def calc_next_trading_day(d: date, n=1) -> date:
    """获取下n个交易日（当n<0时表示向前倒推）"""
    passed = 0
    next_day = d

    while passed != n:  # 如果不是工作日，继续往后推
        next_day += timedelta(days=1) * (1 if n > 0 else -1)
        if is_trading_day(next_day):
            passed += (1 if n > 0 else -1)

    return next_day


def calc_previous_trading_day(d: date, n=1) -> date:
    """获取上n个交易日"""
    return calc_next_trading_day(d, -n)


def calc_belong_trading_day(dt: datetime, dividing_line=time(hour=9, minute=30)) -> Optional[date]:
    """计算 dt 所在的交易日

    把 dividing_line（默认为 9:30）认定为一天的交易日开始，在此前获取的分数都应该记录在上一个交易日（零点）的份上。
    故有如下规则：
    - 如果当前时间 < 上海时间的 9:30，时间记录成"昨天的零点"的时间戳
    - 否则记录成"今天的零点"的时间戳

    Args:
        dt (datetime): 数据获取的交易时间

    Returns:
        datetime: 所在的交易日
    """
    if isinstance(dt, date): # 预防外部直接把 date 传入来
        dt = datetime.combine(dt, time())
        
    dt_line = datetime.combine(dt.date(), dividing_line)

    if is_trading_day(dt):  # 如果是交易日
        if dt <= dt_line:
            return calc_previous_trading_day(dt.date())
        else:
            return dt.date()
    else:
        return calc_previous_trading_day(dt.date())


class TradingInfo:
    # TODO: 目前只提供日线推算（需要补全其他周期的时间、count 推算）
    #       通过添加 period 再根据不同的值（注意对齐开收盘时间）进行推算。

    ALLOW_PERIODS_MAP: ClassVar[dict] = {
        '1m': {'delta': pd.Timedelta(minutes=1), 'align': 'minute'},
        '5m': {'delta': pd.Timedelta(minutes=5), 'align': '5min'},
        '15m': {'delta': pd.Timedelta(minutes=15), 'align': '15min'},
        '30m': {'delta': pd.Timedelta(minutes=30), 'align': '30min'},
        '1d': {'delta': pd.Timedelta(days=1), 'align': 'day'},
        '1w': {'delta': pd.Timedelta(weeks=1), 'align': 'week'},
        '1mon': {'delta': pd.DateOffset(months=1), 'align': 'month'},
        '3mon': {'delta': pd.DateOffset(months=3), 'align': 'quarter'}
    }

    def __init__(self,
                start_time: Optional[Union[str, datetime]] = None,
                end_time: Optional[Union[str, datetime]] = None,
                count: Optional[int] = None,
                period: str = '1d',
                ):
        if period not in self.ALLOW_PERIODS_MAP:
            raise ValueError(f"Period '{period}' not allowed. Allowed periods: {list(self.ALLOW_PERIODS_MAP.keys())}")

        self.period = period
        self.start_time = start_time
        self.end_time = end_time
        self.count = count

        # Convert string to datetime if needed
        if isinstance(self.start_time, str):
            self.start_time = TimeUtils.str_to_datetime(self.start_time)
        if isinstance(self.end_time, str):
            self.end_time = TimeUtils.str_to_datetime(self.end_time)

    def __repr__(self) -> str:
        return f"<TradingInfo(start_time={self.start_time}, end_time={self.end_time}, count={self.count}, period={self.period})>"

    def _get_period_delta(self) -> dict:
        """Get time delta and alignment function for each period"""
        return self.ALLOW_PERIODS_MAP.get(self.period, self.ALLOW_PERIODS_MAP['1d'])

    def _align_to_period(self, dt: datetime) -> datetime:
        """Align datetime to period boundaries"""
        if self.period in ['1m', '5m', '15m', '30m']:
            # Align to minute boundaries first
            aligned = self._math_align_to_period(dt)
            # Then adjust to trading hours if necessary
            return self._adjust_to_trading_hours(aligned)

        elif self.period == '1d':
            return datetime.combine(dt.date(), time(hour=15))  # Align to market close

        elif self.period == '1w':
            # Align to Friday (assuming week ends on Friday)
            days_to_friday = (4 - dt.weekday()) % 7
            friday = dt + pd.Timedelta(days=days_to_friday)
            return datetime.combine(friday.date(), time(hour=15))

        elif self.period in ['1mon', '3mon']:
            # Align to month end
            if self.period == '3mon':
                # Align to quarter end
                month = ((dt.month - 1) // 3 + 1) * 3
                year = dt.year if month <= 12 else dt.year + 1
                month = month if month <= 12 else month - 12
                last_day = pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(1)
            else:
                last_day = pd.Timestamp(dt.year, dt.month, 1) + pd.offsets.MonthEnd(1)
            return datetime.combine(last_day.date(), time(hour=15))

        return dt

    def _math_align_to_period(self, dt: datetime) -> datetime:
        """Pure mathematical alignment to period boundaries (no trading hours consideration)"""
        if self.period == '1m':
            return dt.replace(second=0, microsecond=0)
        elif self.period == '5m':
            minute = (dt.minute // 5) * 5
            return dt.replace(minute=minute, second=0, microsecond=0)
        elif self.period == '15m':
            minute = (dt.minute // 15) * 15
            return dt.replace(minute=minute, second=0, microsecond=0)
        elif self.period == '30m':
            minute = 30 if dt.minute >= 30 else 0
            return dt.replace(minute=minute, second=0, microsecond=0)
        else:
            return dt

    def _adjust_to_trading_hours(self, dt: datetime) -> datetime:
        """Adjust datetime to fall within trading hours (9:30-12:00, 13:00-15:00)"""
        morning_start = datetime.combine(dt.date(), time(hour=9, minute=30))
        morning_end = datetime.combine(dt.date(), time(hour=12, minute=0))
        afternoon_start = datetime.combine(dt.date(), time(hour=13, minute=0))
        afternoon_end = datetime.combine(dt.date(), time(hour=15, minute=0))

        if dt < morning_start:
            # Before trading hours, align to morning start
            return morning_start
        elif dt <= morning_end:
            # Within morning session
            return dt
        elif dt < afternoon_start:
            # Between sessions, align to afternoon start
            return afternoon_start
        elif dt <= afternoon_end:
            # Within afternoon session
            return dt
        else:
            # After trading hours, align to afternoon end
            return afternoon_end

    def _get_previous_period(self, dt: datetime, steps: int = 1) -> datetime:
        """Get previous period start"""
        period_info = self._get_period_delta()
        return self._align_to_period(dt - period_info['delta'] * steps)

    def _get_next_period(self, dt: datetime, steps: int = 1) -> datetime:
        """Get next period end"""
        period_info = self._get_period_delta()
        return self._align_to_period(dt + period_info['delta'] * steps)

    def _calc_count_between(self, start: datetime, end: datetime) -> int:
        """Calculate number of periods between two datetimes"""
        if start > end:
            return 0

        period_info = self._get_period_delta()
        aligned_start = self._align_to_period(start)
        aligned_end = self._align_to_period(end)

        if isinstance(period_info['delta'], pd.DateOffset):
            # For month/quarter offsets, use date_range
            dates = pd.date_range(start=aligned_start, end=aligned_end,
                                 freq=period_info['align'])
            return len(dates)
        else:
            # For timedelta periods
            diff = aligned_end - aligned_start
            return int(diff.total_seconds() / period_info['delta'].total_seconds()) + 1

    # 补全交易日期
    def complete(self):
        datetime_now = datetime.now()

        if self.count is None or self.count <= 0:
            self.count = 1

        # Initialize variables
        start_date = None
        end_date = None

        # Align times based on period
        if self.period in ['1d', '1w', '1mon', '3mon']:
            # For daily and above, use trading day logic
            if self.start_time is None and self.end_time is None:
                # 如果都没有指定，则获取最近的交易日
                end_date = calc_belong_trading_day(datetime_now, time(hour=15))
                start_date = calc_previous_trading_day(end_date, self.count - 1)
                self.start_time = start_date
                self.end_time = end_date
            elif self.start_time is None:
                end_date = calc_belong_trading_day(self.end_time, time(hour=15))
                start_date = calc_previous_trading_day(end_date, self.count - 1)
                self.start_time = start_date
                self.end_time = end_date
            elif self.end_time is None:
                start_date = calc_belong_trading_day(self.start_time, time())
                end_date = calc_next_trading_day(start_date, self.count - 1)
                self.start_time = start_date
                self.end_time = end_date
            else:
                self.count = calc_count_of_trading_days(self.start_time, self.end_time)
        else:
            # For intraday periods (minutes)
            if self.start_time is None and self.end_time is None:
                # If both None, use current time as end
                self.end_time = self._align_to_period(datetime_now)
                self.start_time = self._get_previous_period(self.end_time, self.count - 1)
            elif self.start_time is None:
                # Only end_time provided
                self.end_time = self._align_to_period(self.end_time)
                self.start_time = self._get_previous_period(self.end_time, self.count - 1)
            elif self.end_time is None:
                # Only start_time provided
                self.start_time = self._align_to_period(self.start_time)
                self.end_time = self._get_next_period(self.start_time, self.count - 1)
            else:
                # Both provided, calculate count
                self.start_time = self._align_to_period(self.start_time)
                self.end_time = self._align_to_period(self.end_time)
                self.count = self._calc_count_between(self.start_time, self.end_time)

        return self

    def get_time_range(self):
        """Get the complete time range after completion"""
        if self.start_time is None or self.end_time is None:
            self.complete()
        return self.start_time, self.end_time

    def get_periods(self) -> list:
        """Get list of all periods in the range"""
        if self.start_time is None or self.end_time is None:
            self.complete()

        period_info = self._get_period_delta()

        if isinstance(period_info['delta'], pd.DateOffset):
            # For month/quarter offsets
            dates = pd.date_range(start=self.start_time, end=self.end_time,
                                freq=period_info['align'])
            return dates.to_pydatetime().tolist()
        else:
            # For timedelta periods
            periods = []
            current = self.start_time
            while current <= self.end_time:
                periods.append(current)
                current += period_info['delta']
            return periods


# 使用到 QMT API, 在 miniQMT 中不生效
def get_market_cap(context, stock_code):
    """计算市值（亿元）"""
    try:
        # 获取总股本（手册 3.2.3.21）
        total_shares = context.get_total_share(stock_code)
        if total_shares is None or total_shares <= 0:
            return None

        # 获取最新收盘价
        close_data = context.get_market_data_ex(stock_code=[stock_code], period='1d', fields=['close'], count=1)
        if not close_data or len(close_data) == 0:
            return None
        price = float(close_data[-1])

        market_value = (total_shares * price) / 1e8  # 转为亿元
        return market_value
    except:
        return None


def is_st_stock(stock_name: str) -> bool:
    return any(st_flag in stock_name.upper() for st_flag in ['ST', '*ST', '退'])


def is_valid_stock(context, stock_code: str) -> bool:
    """判断是否为主板/中小板非ST股票"""
    try:
        # 获取股票名称（手册 3.2.2.20）
        name = context.get_stock_name(stock_code)
        if name and is_st_stock(name):
            return False

        # 提取6位代码
        if '.' in stock_code:
            code = stock_code.split('.')[0]
        else:
            code = stock_code[:6]

        # 排除不合规板块
        if (code.startswith('300') or      # 创业板
            code.startswith('688') or      # 科创板
            code.startswith('8') or        # 北交所
            code.startswith('92') or       # 北交所
            code.startswith('43') or       # 老三板
            code.startswith('4') or        # 其他三板
            code.startswith('9')):         # B股
            return False

        # 保留主板/中小板
        if code.startswith(('000', '001', '002', '600', '601', '603', '605')):
            return True

        return False
    except:
        return False


def select_stocks(context):
    """
    选股逻辑（适配QMT）
    条件：
    1. 股价 3 < price < 40
    2. 5日均量 > 60日均量
    3. 市值 < 200亿
    4. 排除创业板(300)、科创板(688)、北交所(8/43等)、ST/*ST、B股等
    5. 排除停牌股
    """
    try:
        # 获取股票池
        all_stocks = context.get_universe()
        if not all_stocks or len(all_stocks) == 0:
            I("股票池为空，请检查 init() 中 set_universe() 是否成功")
            return []

        selected_stocks = []
        I(f"开始选股，共 {len(all_stocks)} 只股票")

        for stock in all_stocks:
            try:
                # 条件5：排除停牌股（手册 3.2.2.13）
                if context.is_suspended_stock(stock):
                    continue

                # 条件4：排除不合规股票
                if not is_valid_stock(context, stock):
                    continue

                # 获取最新收盘价（使用 get_market_data，手册 3.2.3.17）
                close_data = context.get_market_data_ex(stock_code=[stock], period='1d', fields=['close'], count=1)
                if not close_data or len(close_data) == 0:
                    continue
                price = float(close_data[-1])

                # 条件1：价格区间
                if not (3 < price < 40):
                    continue

                # 获取60日成交量
                vol_data = context.get_market_data_ex(stock_code=[stock], period='1d', fields=['volume'], count=60)
                if not vol_data or len(vol_data) < 60:
                    continue

                vol_5 = sum(vol_data[-5:]) / 5.0
                vol_60 = sum(vol_data) / 60.0

                # 条件2：5日均量 > 60日均量
                if vol_5 <= vol_60:
                    continue

                # 条件3：市值 < 200亿
                market_cap = get_market_cap(context, stock)
                if market_cap is None or market_cap >= 200:
                    continue

                selected_stocks.append(stock)
                I(f"选中: {stock} | 价格: {price:.2f} | 市值: {market_cap:.1f}亿 | 5日量: {int(vol_5)} vs 60日量: {int(vol_60)}")

            except Exception as e:
                # 记录异常，但不中断整个循环
                W(f"处理股票 {stock} 时发生异常: {str(e)}, trace: {traceback.format_exc()}")
                return

        I(f"选股完成，共选出 {len(selected_stocks)} 只股票")
        return selected_stocks

    except Exception as e:
        E(f"选股主函数异常: {traceback.format_exc()}")
        return []

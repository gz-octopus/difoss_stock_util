# encoding: utf-8

__all__ = [
    'connect_miniQMT',
    'get_market_stocks',
    
    # (适用于 xtdata.get_market_data)
    'transform_data',
    'transform_data_concise',
]

import socket
from typing import Optional, List, Dict
from .security_util import *
from .network_util import check_port
from .color_log_util import *
from xtquant import xtdata
xtdata.enable_hello = False

def connect_miniQMT(host_or_ip: str ='difoss-home'):
    """
    确保连接 miniQMT，先尝试本地，再尝试 hostname 的地址进行连接。

    Args:
        host_or_ip (str, optional): 连接的主机名或IP地址. Defaults to 'difoss-home'.
    """
    port = 58610
    if host_or_ip and ('.' in host_or_ip):
        ip = host_or_ip
    else:
        ip = socket.gethostbyname(host_or_ip)
        if not ip:
            raise Exception('无法通过 hostname 找到主机')

    if check_port(port) != True:
        W(info='本地 miniQMT 未开启，尝试连接远程主机。', hostname=host_or_ip, ip=ip)
        xtdata.connect(ip, port)


def get_market_stocks(market: str, security_types: SecurityType = None, is_sort: bool = True) -> List[SecurityCode]:
    # TODO: 参考 slb_to_files.py 经一步添加 xtdata 无法连接时通过本地数据库查找市场股票列表。（考虑快速检测 xtdata 链接是否可用。通过 ping 端口？）
    if security_types is None:
        security_types = [SecurityType.STOCK,]
    all_stocks = []
    stocks_in_market = xtdata.get_stock_list_in_sector(market)
    
    # DEBUG
    # I(板块=market, 证券数量=len(stocks_in_market))
    # print("证券代码(未过滤股票类型):", stocks_in_market)
    # from .util import create_limiter
    # limiter = create_limiter(1)

    for stock in stocks_in_market:
        try:
            code = SecurityCode(stock)
            # DEBUG
            # if limiter():
            #   T(full_code=code.full_code, type=code.security_type, market=code.market_code)
            if (code.security_type is not None) and code.security_type in security_types:
                all_stocks.append(code)
        except Exception as e:
            E(f"处理时异常: {e}", stock=stock, market=market)
            import traceback
            traceback.print_exc()
            exit(1)
    if is_sort:
        return sorted(all_stocks, key=lambda x: x.full_code)
    return all_stocks


import pandas as pd
from datetime import datetime
import pytz

def utc_to_local(dt_utc: datetime, timezone='Asia/Shanghai') -> datetime:
    """
    将毫秒时间戳转换为本地时间的 YYYYmmddHHMMSS 格式字符串
    
    Parameters:
    -----------
    timestamp_ms : int
        毫秒级时间戳
    timezone : str
        时区，默认 Asia/Shanghai（东八区）
        
    Returns:
    --------
    str
        格式为 YYYYmmddHHMMSS 的本地时间字符串
    """    
    # 设置为UTC时区
    dt_utc = pytz.utc.localize(dt_utc)
    
    # 转换为目标时区
    target_tz = pytz.timezone(timezone)
    dt_local = dt_utc.astimezone(target_tz)
    
    # 格式化为 YYYYmmddHHMMSS
    return dt_local


# 把 get_market_data 返回的格式转换成 get_market_data_ex 的格式
def transform_data(dict_data) -> Dict[str, pd.DataFrame]:
    """
    将字段字典转换为股票代码字典
    
    Parameters:
    -----------
    dict_data : dict
        键为字段名，值为DataFrame，其中索引为股票代码，列为日期
        
    Returns:
    --------
    dict
        键为股票代码，值为DataFrame，其中索引为Datetime，列为字段名
    """
    if not dict_data:
        print("参数为空")
        return
    
    result = {}
    
    # 获取所有股票代码
    stock_codes = dict_data['time'].index
    
    # 获取日期列
    date_columns = dict_data['time'].columns
    
    # 将日期字符串转换为datetime格式
    # 从'time' DataFrame中获取对应的时间戳并转换为datetime
    dates = []
    for col in date_columns:
        # 从time字段获取对应日期的时间戳（毫秒）
        timestamp_ms = dict_data['time'].loc[stock_codes[0], col]
        # 转换为datetime
        dt = pd.to_datetime(timestamp_ms, unit='ms') # type: datetime
        dates.append(utc_to_local(dt).strftime('%Y%m%d%H%M%S'))
    
    # 为每个股票代码创建DataFrame
    for stock_code in stock_codes:
        # 初始化一个空列表来存储每个字段的数据
        stock_data = {}
        
        # 遍历所有字段
        for field_name, field_df in dict_data.items():
            # 获取该股票在该字段的所有日期数据
            if stock_code in field_df.index:
                stock_data[field_name] = field_df.loc[stock_code].values
        
        # 创建DataFrame，索引为datetime，列为字段名
        stock_df = pd.DataFrame(stock_data, index=dates)
        
        # 添加到结果字典
        result[stock_code] = stock_df
    
    return result

# 或者使用更简洁的列表推导式版本
def transform_data_concise(dict_data) -> dict[str, pd.DataFrame]:
    """
    更简洁的版本
    """
    stock_codes = dict_data['time'].index
    date_columns = dict_data['time'].columns
    
    # 获取所有日期（从第一个股票代码获取）
    dates = pd.to_datetime(dict_data['time'].loc[stock_codes[0]].values, unit='ms')
    local_dates = [utc_to_local(x).strftime('%Y%m%d%H%M%S') for x in dates]
    
    return {
        stock_code: pd.DataFrame({
            field_name: field_df.loc[stock_code].values 
            for field_name, field_df in dict_data.items()
        }, index=local_dates)
        for stock_code in stock_codes
    }

# 使用示例
# result_dict = transform_data(dict_data)
# result_dict = transform_data_concise(dict_data)

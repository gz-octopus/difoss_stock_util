#!python
# encoding: utf-8
# author: DifossChan
#

__all__ = [
    'MA',
    'AVEDEV', 'AVEDEV_value',
    'MA', 
    'CCI', 'CCI_v1', 'CCI_value',
]

# from ..log_util import *
import talib
import numpy as np
import pandas as pd
from typing import Union, Any, Optional, Iterable, List

def MA(arr: Iterable, N: Union[int, None]=None) -> Optional[np.ndarray]:
    if not N:
        N = len(arr)
    if N >= 1 and len(arr) < N:
        return None

    # 将列表转换为Pandas Series，并设置日期索引（可选）
    if not isinstance(arr, pd.Series):
        series = pd.Series(data=arr)
    else:
        series = arr

    # 计算N日移动平均值
    MAs = series.rolling(window=N).mean()

    # 打印结果，注意：移动平均值会在达到窗口大小后才开始有值
    # P(MA_values=MAs.values, MAsType=type(MAs))

    return MAs.values


def AVEDEV(data: np.ndarray, N=None) -> Optional[np.ndarray]:
    if not N:
        N = len(data)
    return talib.AVGDEV(data, N)


# 计算N日平均绝对偏差
def AVEDEV_value_v1(data: Iterable):
    """计算N日平均绝对偏差

    Args:
        data (_type_): _description_

    Returns:
        _type_: _description_
    """
    if not data:  # 检查数据列表是否为空
        return 0

    # 计算平均值
    mean_value = sum(data) / len(data)

    # 计算每个数据点与平均值的差的绝对值并求和
    sum_of_abs_deviations = sum(abs(x - mean_value) for x in data)

    # 计算平均绝对偏差
    avedev_value = sum_of_abs_deviations / len(data)

    return avedev_value

def AVEDEV_value(data):
    """计算N日平均绝对偏差（使用NumPy实现）
    """
    if len(data) == 0:
        return 0
    return np.mean(np.abs(data - np.mean(data)))


def CCI_v1(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, N=88) -> Optional[np.ndarray]:
    TYPs = (highs+lows+closes)/3
    CCIs = (TYPs - pd.Series(TYPs).rolling(window=N).mean().values)*1000 / 15 / talib.AVGDEV(TYPs, N)
    return CCIs


def CCI(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, N=88) -> Optional[np.ndarray]:
    return talib.CCI(highs,lows,closes,timeperiod=N)


def CCI_value(highs: Iterable, lows: Iterable, closes: Iterable, N=88) -> float:
    """ 公式名称: CCI
        公式描述: 商品路径指标
        参数  最小 最大 缺省
          N:   2,   100, 14
    公式：
    TYP:=(HIGH+LOW+CLOSE)/3;
    CCI:(TYP-MA(TYP,N))*1000/(15*AVEDEV(TYP,N));

    Args:
        highs (Iterable): 最高价的数组
        lows (Iterable): 最低价的数组
        closes (Iterable): 收盘价的数组
        N (int, optional): 参数. Defaults to 88.

    Returns:
        float: CCI值
    """
    # T(N=N, len_highs=len(highs))
    TYPs = [ (highs[i]+lows[i]+closes[i])/3 for i in range(0, N)]
    typ = TYPs[-1]

    ma_typ_n = MA(TYPs, N)[-1]
    # E(ma_typ_n=ma_typ_n, AVEDEV_value=AVEDEV_value(TYPs))
    cci = (typ-ma_typ_n)*1000/(15*AVEDEV_value(TYPs))
    return cci
#!python
# encoding: utf-8
# author: DifossChan
#

"""股票的合约详情（InstrumentDetail）据结构定义
"""

__all__ = [
    'StockInstrumentDetail',
]

from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, Index, BigInteger
from sqlalchemy.ext.declarative import declared_attr
from difoss_stock_util.security_util import *
from difoss_stock_util.time_util import *
from difoss_stock_util.color_log_util import *
from difoss_stock_util.db_util import *
from typing import TypeVar, Tuple, Optional, List
from dictdiffer import diff

_T = TypeVar('_T', bound='StockInstrumentDetail', covariant=True)

class StockInstrumentDetail(BaseSecurityModelWithID):

    # 合约基础信息字段
    InstrumentName = Column(String(20), comment='合约名称')
    OpenDate = Column(IntegerDate, comment='IPO日期(股票)')
    ExpireDate = Column(IntegerDate, comment='退市日期')
    FloatVolume = Column(Float, comment='流通股本')
    TotalVolume = Column(Float, comment='总股本')
    InstrumentStatus = Column(Integer, comment='合约停牌状态')

    @declared_attr
    def __ignore_columns__(cls):
        return ['id', 'created_at', 'updated_at',  'InstrumentName', 'OpenDate', 'ExpireDate']

    def __lt__(self, other) -> bool:
        if not isinstance(other, __class__):
            raise Exception("不同类型无法对比")

        return (self.TotalVolume < other.TotalVolume) or (self.FloatVolume < other.FloatVolume)


    @staticmethod
    def has_more_risk(old: dict, new: dict):
        old_tv = old.get('TotalVolume', 0)
        new_tv = new.get('TotalVolume', 0)
        old_fv = old.get('FloatVolume', 0)
        new_fv = new.get('FloatVolume', 0)
        return new_tv > old_tv or new_fv > old_fv

    @staticmethod
    def show_differences(old: dict, new: dict, excludes=[]) -> Tuple[Optional[bool], Optional[List[str]]]:
        """对比两条 股票合约详情
        """
        if not new:
            raise Exception("新数据不能为空")
        if not old:
            I("插入新数据", code=new['InstrumentID'], name=new['InstrumentName'], _level="NEW")
            return None, None
        
        # 检查数据是否相同
        differences = list(diff(old, new, ignore=StockInstrumentDetail.__ignore_columns__))
        
        if differences:
            # 数据不同，插入新记录
            more_risk = StockInstrumentDetail.has_more_risk(old, new)
            diff_details = []
            for change_type, path, values in differences:
                if excludes and isinstance(path, list):
                    if path[0] == excludes:
                        continue
                diff_details.append(f"{change_type}: {path} -> {values}")
            if diff_details:
                I("股本提高" if more_risk else "股本减少", code=new['InstrumentID'], name=new['InstrumentName'],
                    流通股本变化=f"{old.get('FloatVolume')} -> {new['FloatVolume']}",
                    总股本变化=f"{old.get('TotalVolume')} -> {new['TotalVolume']}",
                    具体差异=diff_details,
                    _indent=2,
                    _color='bright_red' if more_risk else 'bright_green',
                    _level='⬇' if more_risk else '⬆'
                )
                return more_risk, diff_details

        return None, None


def main():
    sid = StockInstrumentDetail()
    D(sid=sid)


if __name__ == "__main__":
    main()
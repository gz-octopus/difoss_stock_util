#!python
# encoding: utf-8
# author: DifossChan
#

__all__ = ['HistoryData1D']

from sqlalchemy import (Column, String, Integer, Float, Numeric, Boolean,
                        DateTime, Text, Index, BigInteger,
                        PrimaryKeyConstraint)
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import scoped_session, Session
from datetime import datetime
from difoss_stock_util.db_util import *
from difoss_stock_util.time_util import *
from difoss_stock_util.color_log_util import *
from typing import TypeVar, List
import pandas as pd

_THD1D = TypeVar('_THD1D', bound='HistoryData1D', covariant=True)


class HistoryData1D(BaseSecurityModel):
    """日线历史数据模型
    """
    @declared_attr
    def __tablename__(cls):
        return 'history_data_1d'

    # 移除基类的自增主键，使用复合主键
    @declared_attr
    def __mapper_args__(cls):
        # 指定复合主键
        return {
            "primary_key": [cls.ExchangeID, cls.InstrumentID, cls.trade_date]
        }

    trade_date = Column(IntegerDate, comment='交易日期')

    # 价格字段
    open = Column(Numeric(10, 2), comment='开盘价')
    close = Column(Numeric(10, 2), comment='收盘价')
    high = Column(Numeric(10, 2), comment='最高价')
    low = Column(Numeric(10, 2), comment='最低价')

    # 交易数据
    volume = Column(BigInteger, comment='成交量')
    amount = Column(Numeric(18, 2), comment='成交额')

    # 状态标记
    suspend_flag = Column(Boolean, comment='停牌标记')

    # 市场数据
    change_pct = Column(Numeric(8, 4), comment='涨跌幅(%)')  # 计算字段，便于查询
    turnover_rate = Column(Numeric(8, 4), comment='换手率(%)')  # 如果有流通股本数据

    # 分区表必须在主键中包含分区键
    @declared_attr
    def __table_args__(cls):
        return (
            # 复合主键约束（必须包含分区键trade_date）
            PrimaryKeyConstraint('ExchangeID', 'InstrumentID', 'trade_date', name='pk_history_data_1d'),
            # 额外索引
            Index('idx_trade_date', 'trade_date'),
            {
                'comment': 'A股日线历史数据（前复权）',
                'postgresql_partition_by': 'RANGE (trade_date)'
            }
        )

    @classmethod
    def upsert(cls, new_record: _THD1D):
        with cls.get_session(True) as session:
            c = session.query(cls).filter(
                cls.InstrumentID == new_record.InstrumentID,
                cls.ExchangeID == new_record.ExchangeID,
                cls.trade_date == new_record.trade_date,
            ).count()
            if c == 0:
                # 不存在则插入
                session.add(new_record)
            else:
                # 已存在则更新
                session.query(cls).filter(
                    cls.InstrumentID == new_record.InstrumentID,
                    cls.ExchangeID == new_record.ExchangeID,
                    cls.trade_date == new_record.trade_date,
                ).update(new_record)
            return new_record


    @classmethod
    def _prepare_records_from_dataframe(cls, df: pd.DataFrame, instrument_id: str, exchange_id: str) -> List[dict]:
        """
        从DataFrame准备记录数据

        参数:
        df -- pandas DataFrame，包含日线数据
        exchange_id -- 交易所ID (如 'SH', 'SZ')
        instrument_id -- 证券代码 (如 '600000')

        返回:
        记录数据列表
        """
        records = []
        for _, row in df.iterrows():
            trade_date = TimeUtils.ms_to_datetime(row['time']).date()
            record_data = {
                'ExchangeID': exchange_id.upper(),
                'InstrumentID': instrument_id,
                'trade_date': trade_date,
                'open': float(row['open']) if pd.notna(row['open']) else 0.0,
                'high': float(row['high']) if pd.notna(row['high']) else 0.0,
                'low': float(row['low']) if pd.notna(row['low']) else 0.0,
                'close': float(row['close']) if pd.notna(row['close']) else 0.0,
                'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
                'amount': float(row['amount']) if pd.notna(row['amount']) else 0.0,
                'suspend_flag': bool(row.get('suspendFlag', 0)) if pd.notna(row.get('suspendFlag', 0)) else False,
                'change_pct': None
            }

            # 计算涨跌幅
            if pd.notna(row.get('preClose')) and float(row['preClose']) != 0:
                pre_close = float(row['preClose'])
                change_pct = (record_data['close'] - pre_close) / pre_close * 100
                record_data['change_pct'] = round(change_pct, 4)

            records.append(record_data)
        return records

    @classmethod
    def bulk_insert_from_dataframe(cls, df: pd.DataFrame, instrument_id: str, exchange_id: str, batch_size=1000, replace_existing=False):
        """
        从DataFrame批量插入日线数据

        参数:
        df -- pandas DataFrame，包含日线数据
        exchange_id -- 交易所ID (如 'SH', 'SZ')
        instrument_id -- 证券代码 (如 '600000')
        batch_size -- 每批次插入的记录数
        replace_existing -- 是否替换已存在的记录

        返回:
        (成功插入数, 总处理数)
        """

        # 验证必要字段
        required_columns = ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"DataFrame缺少必要字段: {missing_columns}")

        # 确保索引是连续的
        df = df.reset_index(drop=True)
        total_records = len(df)
        inserted_count = 0

        print(f"df={df}. total_records={total_records}")


        # 分批处理
        for i in range(0, total_records, batch_size):
            batch_df = df.iloc[i:i+batch_size]
            records = []

            print(f"batch_df={batch_df}")

            records = cls._prepare_records_from_dataframe(batch_df, instrument_id, exchange_id)

            print(f"records after preparation: {records}")

            with cls.get_session() as session:
                # if replace_existing:
                #     # 删除已存在的记录
                #     trade_dates = [record['trade_date'] for record in records]
                #     session.query(cls).filter(
                #         cls.ExchangeID == exchange_id,
                #         cls.InstrumentID == instrument_id,
                #         cls.trade_date.in_(trade_dates)
                #     ).delete(synchronize_session=False)

                # # 直接批量插入
                # session.bulk_insert_mappings(cls, records)
                # session.commit()

                if replace_existing:
                    # 使用upsert逻辑
                    for record in records:
                        instance = HistoryData1D(**record)
                        # DEBUG:
                        I("record:", **instance.to_dict())
                        instance.upsert(instance)
                        inserted_count += 1
                else:
                    # 尝试直接批量插入
                    try:
                        # session.bulk_insert_mappings(cls, records)
                        session.add_all([HistoryData1D(**record) for record in records])
                        session.flush()
                        inserted_count += len(records)
                    except Exception as e:
                        if "UniqueViolation" in str(e):
                            # 遇到重复键，单条插入并跳过重复
                            for record in records:
                                try:
                                    session.add(cls(**record))
                                    inserted_count += 1
                                except Exception as inner_e:
                                    if "UniqueViolation" not in str(inner_e):
                                        # raise inner_e
                                        pass
                            session.commit()
                        else:
                            raise e

                session.commit()
                print(f"已处理 {min(i+batch_size, total_records)}/{total_records} 条记录，成功插入 {inserted_count} 条")

        print(f"批量插入完成: {inserted_count}/{total_records} 条记录成功")

        return inserted_count, total_records

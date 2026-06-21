#!python
# encoding: utf-8
# author: DifossChan
#
import os
import re
from typing import List, Dict, Set, Optional, Union
from difoss_stock_util.security_util import *
from difoss_stock_util.color_log_util import *

__all__ = ['TdxEbk']

class TdxEbk:
    """
    通达信自定义板块文件(.ebk)操作类
    格式：一行一只股票代码，深市前加0，沪市前加1，北交所前加2
    """

    # 市场前缀映射
    MARKET_PREFIX = {
        'SZ': '0',  # 深圳
        'SH': '1',  # 上海
        'BJ': '2'   # 北京交易所
    }

    # 反向映射
    PREFIX_MARKET = {
        '0': 'SZ',
        '1': 'SH',
        '2': 'BJ'
    }

    def __init__(self, file_path: str = None):
        """
        初始化

        Args:
            file_path: ebk文件路径，如果为None则创建新板块
        """
        self.file_path = file_path
        self.stocks: Set[SecurityCode] = set()  # 存储标准化股票代码

        if file_path and os.path.exists(file_path):
            self.load(file_path)

    def _serialize_code(self, code: SecurityCode) -> str:
        """
        返回序列化时用的股票代码（带市场前缀的7位数字）

        Args:
            code: 输入的股票代码，可以是各种格式

        Returns:
            带市场前缀的7位数字
        """
        # 处理带市场标识的代码
        prefix = self.MARKET_PREFIX.get(code.market_code, '0')
        return prefix + code.short_code


    def _deserialize_code(self, code: str) -> Optional[SecurityCode]:
        """
        格式化显示代码（带市场标识）

        Args:
            code: 标准化的8位代码

        Returns:
            带市场标识的代码，如 SZ000001
        """
        if len(code) != 7 or code[0] not in self.PREFIX_MARKET:
            return None

        prefix = code[0]
        num_part = code[1:]
        market = self.PREFIX_MARKET.get(prefix, 'SZ')

        return SecurityCode((num_part, market))


    def load(self, file_path: str) -> None:
        """
        从ebk文件加载板块数据

        Args:
            file_path: ebk文件路径
        """
        self.file_path = file_path
        self.stocks.clear()

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):  # 跳过空行和注释
                        code = self._deserialize_code(line)
                        if code:
                            self.stocks.add(code)
            print(f"成功加载板块文件: {file_path}, 包含 {len(self.stocks)} 只股票")
        except Exception as e:
            print(f"加载文件失败: {e}")
            raise

    def save(self, file_path: str = None) -> None:
        """
        保存板块数据到ebk文件

        Args:
            file_path: 保存路径，如果为None则使用原路径
        """
        if file_path:
            self.file_path = file_path

        if not self.file_path:
            raise ValueError("未指定文件保存路径")

        file_dir = os.path.dirname(os.path.abspath(self.file_path))
        I(**locals(), dir=file_dir)
        # 确保目录存在
        os.makedirs(file_dir, exist_ok=True)

        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                for code in sorted(self.stocks):
                    serialized_code = self._serialize_code(code)
                    f.write(serialized_code + '\n')
            print(f"成功保存板块文件: {self.file_path}, 包含 {len(self.stocks)} 只股票")
        except Exception as e:
            print(f"保存文件失败: {e}")
            raise

    def add(self, code: Union[SecurityCode, str]) -> bool:
        """
        添加股票到板块

        Args:
            code: 股票代码

        Returns:
            是否添加成功
        """
        if isinstance(code, str):
            code = SecurityCode(code)

        if code in self.stocks:
            print(f"股票 {code} 已存在")
            return False
        self.stocks.add(code)
        print(f"成功添加股票: {code}")
        return True

    def remove(self, code: Union[SecurityCode, str]) -> bool:
        """
        从板块移除股票

        Args:
            code: 股票代码

        Returns:
            是否移除成功
        """
        if isinstance(code, str):
            code = SecurityCode(code)

        if code in self.stocks:
            self.stocks.remove(code)
            print(f"成功移除股票: {code}")
            return True

        print(f"股票 {code} 不存在")
        return False

    def has(self, code: SecurityCode) -> bool:
        """
        检查股票是否在板块中

        Args:
            code: 股票代码

        Returns:
            是否存在
        """
        return code in self.stocks

    def clear_all(self) -> None:
        """清空板块所有股票"""
        self.stocks.clear()
        print("已清空板块所有股票")

    def get_stocks(self) -> List[SecurityCode]:
        """
        获取板块所有股票列表

        Args:
            formatted: 是否返回格式化代码（带市场标识）

        Returns:
            股票代码列表
        """
        return self.stocks

    def get_stocks_by_market(self, market: str) -> List[SecurityCode]:
        """
        按市场获取股票列表

        Args:
            market: 市场代码 'SZ', 'SH', 'BJ'

        Returns:
            该市场的股票列表
        """
        return [code for code in self.stocks if (code.market_code == market)]

    def add_batch(self, codes: List[Union[SecurityCode, str]]) -> Dict[str, int]:
        """
        批量添加股票

        Args:
            codes: 股票代码列表

        Returns:
            添加结果统计
        """
        results = {
            'success': 0,
            'failed': 0,
            'duplicate': 0
        }

        for code in codes:
            if isinstance(code, str):
                code = SecurityCode(code)

            if code in self.stocks:
                results['duplicate'] += 1
            else:
                self.stocks.add(code)
                results['success'] += 1

        print(f"批量添加完成: 成功 {results['success']}, 重复 {results['duplicate']}, 失败 {results['failed']}")
        return results

    def remove_stocks_batch(self, codes: List[str]) -> Dict[str, int]:
        """
        批量移除股票

        Args:
            codes: 股票代码列表

        Returns:
            移除结果统计
        """
        results = {
            'success': 0,
            'failed': 0,
            'not_found': 0
        }

        for code in codes:
            if code not in self.stocks:
                results['not_found'] += 1
            else:
                self.stocks.remove(code)
                results['success'] += 1

        print(f"批量移除完成: 成功 {results['success']}, 未找到 {results['not_found']}, 失败 {results['failed']}")
        return results

    def get_stats(self) -> Dict[str, int]:
        """
        获取板块统计信息

        Returns:
            统计信息字典
        """
        stats = {
            'total': len(self.stocks),
            'sz': len(self.get_stocks_by_market('SZ')),
            'sh': len(self.get_stocks_by_market('SH')),
            'bj': len(self.get_stocks_by_market('BJ'))
        }
        return stats

    def __len__(self) -> int:
        """返回板块股票数量"""
        return len(self.stocks)

    def __contains__(self, code: str) -> bool:
        """支持 in 操作符"""
        return self.has(code)

    def __str__(self) -> str:
        """字符串表示"""
        stats = self.get_stats()
        return (f"TdxEbk(文件: {self.file_path}, "
                f"总数: {stats['total']}, "
                f"深市: {stats['sz']}, "
                f"沪市: {stats['sh']}, "
                f"北交: {stats['bj']})")

# 使用示例
def demo():
    """使用示例"""
    # 创建新的板块对象
    ebk = TdxEbk()

    # 添加股票（支持各种格式）
    ebk.add("000001")      # 平安银行
    ebk.add("600000")      # 浦发银行
    ebk.add("000002.SZ")   # 万科A
    ebk.add("600036.SH")   # 招商银行
    ebk.add("430090")      # 北交所股票

    # 批量添加
    stocks_to_add = ["000858", "600519", "300750", "830799"]
    ebk.add_batch(stocks_to_add)

    # 检查股票是否存在
    print(f"包含000001: {ebk.has('000001')}")
    print(f"包含SZ000001: {ebk.has('SZ000001')}")

    # 获取股票列表
    print("\n所有股票:", ebk.get_stocks())
    print("\n深市股票:", ebk.get_stocks_by_market('SZ'))
    print("沪市股票:", ebk.get_stocks_by_market('SH'))
    print("北交股票:", ebk.get_stocks_by_market('BJ'))

    # 获取统计信息
    print(f"\n板块统计: {ebk.get_stats()}")

    # 保存到文件
    ebk.save("test_block.ebk")

    # 从文件加载
    ebk2 = TdxEbk("test_block.ebk")
    print(f"\n加载的板块: {ebk2}")

if __name__ == "__main__":
    demo()

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BlockInfo:
    """板块信息数据类"""
    block_type: str      # 板块类型：GN(概念), FG(风格), SZ(指数)等
    block_name: str      # 板块名称
    index: str          # 索引
    instrument_id: str  # 板块代码
    start_date: str     # 开始日期
    end_date: str       # 结束日期
    stocks: List[Tuple[str, str]]  # 股票列表 [(市场前缀, 股票代码)]


class InfoharborBlockParser:
    """通达信 infoharbor_block.dat 文件解析器"""

    # 板块行正则表达式：匹配 #TYPE_NAME,index,instrument_id,start_date,end_date
    BLOCK_PATTERN = re.compile(r'^#([A-Z]+)_([^,]+),(\d+),(\d+),(\d+),(\d+),,*$')
    # 股票行正则表达式：匹配 0#000001,1#600000 等
    STOCK_PATTERN = re.compile(r'^([0-2])#(\d{6})')

    # 板块类型映射（可选，用于友好显示）
    BLOCK_TYPE_MAPPING = {
        'GN': '概念板块',
        'FG': '风格板块',
        'SZ': '指数板块',
        'HS': '行业板块',  # 可能还有其他类型
        'ZJ': '资金板块',
        # 根据实际文件添加更多类型
    }

    def __init__(self):
        self.blocks: List[BlockInfo] = []
        self.blocks_by_name: Dict[str, List[BlockInfo]] = {}  # 同名称可能有不同类型
        self.blocks_by_id: Dict[str, BlockInfo] = {}
        self.blocks_by_type: Dict[str, List[BlockInfo]] = {}

    def parse_file(self, file_path: str) -> List[BlockInfo]:
        """
        解析文件

        Args:
            file_path: 文件路径

        Returns:
            板块信息列表
        """
        self.blocks.clear()
        self.blocks_by_name.clear()
        self.blocks_by_id.clear()
        self.blocks_by_type.clear()

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试GBK编码
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()

        lines = content.strip().split('\n')
        current_block = None
        current_stocks = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否是板块定义行
            if line.startswith('#'):
                # 保存上一个板块
                if current_block is not None:
                    block_info = self._create_block_info(current_block, current_stocks)
                    self._store_block_info(block_info)
                    current_stocks = []

                # 解析新板块
                match = self.BLOCK_PATTERN.match(line)
                if match:
                    block_type, block_name, index, instrument_id, start_date, end_date = match.groups()
                    current_block = (block_type, block_name, index, instrument_id, start_date, end_date)
                else:
                    # 重置，处理格式错误
                    current_block = None
                    current_stocks = []

            elif line.startswith(('0#', '1#', '2#')):
                # 解析股票列表
                stock_parts = line.split(',')
                for stock_part in stock_parts:
                    stock_part = stock_part.strip()
                    if not stock_part:
                        continue

                    match = self.STOCK_PATTERN.match(stock_part)
                    if match:
                        market_prefix, stock_code = match.groups()
                        current_stocks.append((market_prefix, stock_code))

        # 处理最后一个板块
        if current_block is not None:
            block_info = self._create_block_info(current_block, current_stocks)
            self._store_block_info(block_info)

        return self.blocks

    def _create_block_info(self, block_data: tuple, stocks: list) -> BlockInfo:
        """创建BlockInfo对象"""
        block_type, block_name, index, instrument_id, start_date, end_date = block_data
        return BlockInfo(
            block_type=block_type,
            block_name=block_name,
            index=index,
            instrument_id=instrument_id,
            start_date=start_date,
            end_date=end_date,
            stocks=stocks.copy()
        )

    def _store_block_info(self, block_info: BlockInfo):
        """存储板块信息到各个索引"""
        # 添加到总列表
        self.blocks.append(block_info)

        # 按ID索引
        self.blocks_by_id[block_info.instrument_id] = block_info

        # 按名称索引（可能有多个同名不同类的板块）
        if block_info.block_name not in self.blocks_by_name:
            self.blocks_by_name[block_info.block_name] = []
        self.blocks_by_name[block_info.block_name].append(block_info)

        # 按类型索引
        if block_info.block_type not in self.blocks_by_type:
            self.blocks_by_type[block_info.block_type] = []
        self.blocks_by_type[block_info.block_type].append(block_info)

    def get_block_by_name(self, block_name: str, block_type: Optional[str] = None) -> List[BlockInfo]:
        """
        根据板块名称获取板块信息

        Args:
            block_name: 板块名称
            block_type: 可选，指定板块类型

        Returns:
            板块信息列表（同名可能有不同类型）
        """
        blocks = self.blocks_by_name.get(block_name, [])
        if block_type:
            return [b for b in blocks if b.block_type == block_type]
        return blocks

    def get_block_by_id(self, instrument_id: str) -> Optional[BlockInfo]:
        """根据板块代码获取板块信息"""
        return self.blocks_by_id.get(instrument_id)

    def get_blocks_by_type(self, block_type: str) -> List[BlockInfo]:
        """根据板块类型获取所有板块"""
        return self.blocks_by_type.get(block_type, [])

    def get_block_type_name(self, block_type: str) -> str:
        """获取板块类型的中文名称"""
        return self.BLOCK_TYPE_MAPPING.get(block_type, f"未知板块({block_type})")

    def get_all_blocks(self) -> List[Dict]:
        """获取所有板块信息（转换为字典格式）"""
        result = []
        for block in self.blocks:
            result.append({
                'block_type': block.block_type,
                'block_type_name': self.get_block_type_name(block.block_type),
                'block_name': block.block_name,
                'index': block.index,
                'instrument_id': block.instrument_id,
                'start_date': block.start_date,
                'end_date': block.end_date,
                'stock_count': len(block.stocks),
                'stocks': block.stocks
            })
        return result

    def get_blocks_by_stock(self, market_prefix: str, stock_code: str,
                           block_type: Optional[str] = None) -> List[BlockInfo]:
        """
        获取包含指定股票的板块

        Args:
            market_prefix: 市场前缀 '0'(深市), '1'(沪市), '2'(北证)
            stock_code: 股票代码
            block_type: 可选，指定板块类型

        Returns:
            板块信息列表
        """
        target_stock = (market_prefix, stock_code)
        result = []
        for block in self.blocks:
            if block_type and block.block_type != block_type:
                continue
            if target_stock in block.stocks:
                result.append(block)
        return result

    def format_date(self, date_str: str) -> str:
        """格式化日期字符串为 YYYY-MM-DD"""
        if len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str

    def is_block_active(self, block_name: str, block_type: Optional[str] = None,
                       check_date: Optional[datetime] = None) -> bool:
        """
        检查板块在指定日期是否有效

        Args:
            block_name: 板块名称
            block_type: 可选，指定板块类型（同名可能有不同类型）
            check_date: 检查日期，默认为当前日期

        Returns:
            是否有效
        """
        blocks = self.get_block_by_name(block_name, block_type)
        if not blocks:
            return False

        if check_date is None:
            check_date = datetime.now()

        # 只要有一个板块在当前日期有效就返回True
        for block in blocks:
            try:
                start_date = datetime.strptime(block.start_date, "%Y%m%d")
                end_date = datetime.strptime(block.end_date, "%Y%m%d")
                if start_date <= check_date <= end_date:
                    return True
            except ValueError:
                continue  # 如果日期解析失败，跳过

        return False

    def export_blocks_to_csv(self, output_path: str, block_type: Optional[str] = None):
        """导出板块信息到CSV文件"""
        import csv

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['板块类型', '板块名称', '板块代码', '开始日期', '结束日期', '股票数量', '股票列表'])

            for block in self.blocks:
                if block_type and block.block_type != block_type:
                    continue

                # 将股票列表转换为字符串
                stocks_str = ','.join([f"{market}{code}" for market, code in block.stocks])

                writer.writerow([
                    self.get_block_type_name(block.block_type),
                    block.block_name,
                    block.instrument_id,
                    self.format_date(block.start_date),
                    self.format_date(block.end_date),
                    len(block.stocks),
                    stocks_str
                ])


# 使用示例
if __name__ == "__main__":
    # 创建解析器实例
    parser = InfoharborBlockParser()

    # 解析文件
    blocks = parser.parse_file("infoharbor_block.dat.txt")

    print(f"共解析到 {len(blocks)} 个板块")

    # 统计不同类型板块的数量
    print("\n板块类型统计:")
    for block_type, blocks_list in parser.blocks_by_type.items():
        type_name = parser.get_block_type_name(block_type)
        print(f"  {block_type}({type_name}): {len(blocks_list)} 个")

    # 示例：查找特定板块
    print("\n查找'一带一路'板块:")
    yidaiyilu_blocks = parser.get_block_by_name("一带一路")
    for block in yidaiyilu_blocks:
        print(f"  {block.block_type}({parser.get_block_type_name(block.block_type)}) - {block.instrument_id}")
        print(f"  股票数量: {len(block.stocks)}")
        print(f"  是否当前有效: {parser.is_block_active('一带一路', block.block_type)}")

    # 示例：查找包含特定股票的板块
    print("\n查找包含000002(万科A)的板块:")
    containing_blocks = parser.get_blocks_by_stock('0', '000002')
    print(f"包含000002的板块:")
    for block in containing_blocks:
        print(f"  {block.block_type}: {block.block_name}")

    # 导出概念板块到CSV
    parser.export_blocks_to_csv("concept_blocks.csv", block_type="GN")

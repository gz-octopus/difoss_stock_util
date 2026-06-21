#!python
# encoding: utf-8
# author: DifossChen
#

from typing import Optional, List, Dict, Set, Union, Any
from pathlib import Path
from collections import defaultdict
import os

# 假设 tdx_industry.py 在同一目录或已安装
try:
    from tdx_industry import TDXIndustryTree, TDXIndustryNode
except ImportError:
    # 如果单独运行，需要导入
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent))
    from tdx_industry import TDXIndustryTree, TDXIndustryNode


class TDXIndustryStockMapper:
    """
    通达信行业-股票映射管理类

    解析 tdxhy.cfg 文件，建立股票代码与行业节点的映射关系。
    可以与 TDXIndustryTree 协同工作，获取行业包含的股票列表。
    """

    # 市场前缀映射
    MARKET_PREFIX = {
        '0': 'SZ',  # 深市
        '1': 'SH',  # 沪市
        '2': 'BJ'   # 北交所
    }

    def __init__(
        self,
        cfg_path: Optional[str] = None,
        tdx_root: Optional[str] = None,
        industry_tree: Optional[TDXIndustryTree] = None,
        encoding: str = 'gbk'):
        """
        初始化行业-股票映射器

        Args:
            cfg_path: tdxhy.cfg 文件路径
            tdx_root: 通达信安装根目录（如果提供，会自动拼接 T0002/hq_cache/tdxhy.cfg）
            industry_tree: TDXIndustryTree 对象（用于验证行业ID、获取行业信息）
            encoding: 文件编码（默认gbk）
        """
        self.industry_tree = industry_tree
        self.encoding = encoding

        # 数据结构
        self.stock_to_blockid: Dict[str, str] = {}          # 股票代码 -> 行业ID
        self.blockid_to_stocks: Dict[str, Set[str]] = defaultdict(set)  # 行业ID -> 股票代码集合
        self.stock_info: Dict[str, Dict[str, Any]] = {}     # 股票代码 -> 额外信息（市场、T代码等）

        # 加载 cfg 文件
        if cfg_path:
            self.load_from_file(cfg_path)
        elif tdx_root:
            tdx_root_path = Path(tdx_root)
            if not tdx_root_path.exists():
                raise FileExistsError(f"通达信安装目录不存在: {tdx_root}")
            cfg_file_path = tdx_root_path / 'T0002' / 'hq_cache' / 'tdxhy.cfg'
            self.load_from_file(cfg_file_path)

    def load_from_file(self, cfg_path: Union[str, Path], encoding: Optional[str] = None):
        """
        从 tdxhy.cfg 文件加载映射数据

        Args:
            cfg_path: 配置文件路径
            encoding: 文件编码，如果为None则使用实例的encoding
        """
        enc = encoding or self.encoding
        cfg_path = Path(cfg_path)

        if not cfg_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {cfg_path}")

        print(f"正在加载股票行业映射文件: {cfg_path}")

        line_count = 0
        valid_count = 0

        with open(cfg_path, 'r', encoding=enc) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                line_count += 1
                if self._parse_line(line):
                    valid_count += 1

        print(f"✓ 映射文件加载成功！共 {line_count} 行，有效记录 {valid_count} 条")
        print(f"  涉及股票数: {len(self.stock_to_blockid)} 只")
        print(f"  涉及行业数: {len(self.blockid_to_stocks)} 个")

    def _parse_line(self, line: str) -> bool:
        """
        解析单行配置

        格式: 市场|股票代码|T代码|||行业ID
        示例: 0|000001|T1001|||X500102

        Args:
            line: 配置行

        Returns:
            是否解析成功
        """
        parts = line.split('|')
        if len(parts) < 6:
            return False

        market = parts[0]           # 市场: 0深市,1沪市,2北交所
        stock_code = parts[1]       # 股票代码
        t_code = parts[2]           # T代码（如T1001）
        blockid = parts[5]          # 行业ID（如X500102）

        # 补齐股票代码（深市6位，沪市6位，北交所可能也是6位）
        if len(stock_code) < 6:
            stock_code = stock_code.zfill(6)

        # 生成标准股票代码格式（带市场前缀）
        market_prefix = self.MARKET_PREFIX.get(market, '')
        full_code = f"{market_prefix}.{stock_code}" if market_prefix else stock_code

        # 存储映射关系
        self.stock_to_blockid[full_code] = blockid
        self.blockid_to_stocks[blockid].add(full_code)

        # 存储股票信息
        self.stock_info[full_code] = {
            'market': market,
            'market_prefix': market_prefix,
            'stock_code': stock_code,
            't_code': t_code,
            'blockid': blockid,
            'full_code': full_code
        }

        return True

    # ================ 查询方法 ================

    def get_blockid_by_stock(self, stock_code: str) -> Optional[str]:
        """
        根据股票代码获取行业ID

        Args:
            stock_code: 股票代码（支持多种格式：'000001', '000001.SZ', 'SH.600000'等）

        Returns:
            行业ID，如果找不到则返回None
        """
        # 标准化股票代码
        normalized = self._normalize_stock_code(stock_code)
        return self.stock_to_blockid.get(normalized)

    def get_node_by_stock(self, stock_code: str) -> Optional[TDXIndustryNode]:
        """
        根据股票代码获取行业节点（需要industry_tree）

        Args:
            stock_code: 股票代码

        Returns:
            行业节点，如果找不到或未关联industry_tree则返回None
        """
        if not self.industry_tree:
            return None

        blockid = self.get_blockid_by_stock(stock_code)
        if blockid:
            return self.industry_tree.get_node_by_id(blockid)
        return None

    def get_stocks_by_blockid(self, blockid: str) -> List[str]:
        """
        根据行业ID获取所有股票代码

        Args:
            blockid: 行业ID（如 X500102）

        Returns:
            股票代码列表（带市场前缀）
        """
        return list(self.blockid_to_stocks.get(blockid, set()))

    def get_stocks_by_node(self, node: Union[str, TDXIndustryNode]) -> List[str]:
        """
        根据行业节点获取所有股票代码

        Args:
            node: 行业节点或行业ID

        Returns:
            股票代码列表
        """
        if isinstance(node, TDXIndustryNode):
            blockid = node.blockid
        else:
            blockid = node

        return self.get_stocks_by_blockid(blockid)

    def get_stocks_by_node_with_descendants(self, node: Union[str, TDXIndustryNode]) -> Dict[str, List[str]]:
        """
        获取行业节点及其所有后代节点包含的股票

        Args:
            node: 行业节点或行业ID

        Returns:
            字典，key为行业ID，value为该行业的股票列表
        """
        if not self.industry_tree:
            return {}

        if isinstance(node, str):
            node = self.industry_tree.get_node_by_id(node)
            if not node:
                return {}

        result = {}
        descendants = node.get_descendants(include_self=True)

        for desc_node in descendants:
            stocks = self.get_stocks_by_blockid(desc_node.blockid)
            if stocks:
                result[desc_node.blockid] = stocks

        return result

    def get_stock_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票的详细信息

        Args:
            stock_code: 股票代码

        Returns:
            股票信息字典
        """
        normalized = self._normalize_stock_code(stock_code)
        return self.stock_info.get(normalized)

    def _normalize_stock_code(self, stock_code: str) -> str:
        """
        标准化股票代码格式为 'SZ.000001' 或 'SH.600000'

        Args:
            stock_code: 原始股票代码

        Returns:
            标准化后的代码
        """
        # 如果已经是标准格式，直接返回
        if '.' in stock_code and stock_code.split('.')[0] in ['SH', 'SZ', 'BJ']:
            return stock_code

        # 去除可能的点号和前缀
        code = stock_code.replace('.', '').upper()

        # 去除市场前缀
        for prefix in ['SH', 'SZ', 'BJ']:
            if code.startswith(prefix):
                code = code[len(prefix):]
                break

        # 补齐6位
        code = code.zfill(6)

        # 根据首位判断市场
        if code.startswith('6'):
            return f"SH.{code}"
        elif code.startswith('0') or code.startswith('3'):
            return f"SZ.{code}"
        elif code.startswith('8') or code.startswith('4'):
            return f"BJ.{code}"
        else:
            # 未知市场，返回原代码
            return code

    # ================ 统计和展示方法 ================

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        """
        stats = {
            'total_stocks': len(self.stock_to_blockid),
            'total_industries': len(self.blockid_to_stocks),
            'industry_stock_counts': {},
            'stocks_without_industry': 0,
            'industries_without_stocks': 0
        }

        # 统计每个行业的股票数量
        for blockid, stocks in self.blockid_to_stocks.items():
            stats['industry_stock_counts'][blockid] = len(stocks)

        # 如果有行业树，可以统计缺失的行业和股票
        if self.industry_tree:
            all_industry_nodes = self.industry_tree.get_all_nodes()
            all_blockids = {node.blockid for node in all_industry_nodes}

            stats['total_industry_nodes'] = len(all_blockids)
            stats['industries_with_stocks'] = len(set(self.blockid_to_stocks.keys()) & all_blockids)
            stats['industries_without_stocks'] = len(all_blockids - set(self.blockid_to_stocks.keys()))

            # 统计股票所属行业在树中的层级分布
            level_counts = {1: 0, 2: 0, 3: 0}
            for blockid in self.blockid_to_stocks.keys():
                node = self.industry_tree.get_node_by_id(blockid)
                if node:
                    level = node.get_level()
                    level_counts[level] = level_counts.get(level, 0) + 1
            stats['industry_level_distribution'] = level_counts

        return stats

    def display_statistics(self):
        """显示统计信息"""
        stats = self.get_statistics()

        from rich.table import Table
        from rich.panel import Panel
        from rich import print as rprint

        table = Table(title="行业-股票映射统计", show_header=True, header_style="bold magenta")
        table.add_column("项目", style="cyan")
        table.add_column("数值", style="green")

        table.add_row("总股票数", str(stats['total_stocks']))
        table.add_row("总行业数", str(stats['total_industries']))

        if 'total_industry_nodes' in stats:
            table.add_row("行业树节点数", str(stats['total_industry_nodes']))
            table.add_row("有股票的行业数", str(stats['industries_with_stocks']))
            table.add_row("无股票的行业数", str(stats['industries_without_stocks']))

            # 添加层级分布
            level_dist = stats.get('industry_level_distribution', {})
            table.add_row("一级行业数", str(level_dist.get(1, 0)))
            table.add_row("二级行业数", str(level_dist.get(2, 0)))
            table.add_row("三级行业数", str(level_dist.get(3, 0)))

        rprint(Panel(table, title="📊 行业股票映射统计", border_style="blue"))

    def print_stocks_by_industry(self, blockid_or_node: Union[str, TDXIndustryNode],
                                  include_descendants: bool = False,
                                  max_display: int = 20):
        """
        打印指定行业的股票列表

        Args:
            blockid_or_node: 行业ID或节点
            include_descendants: 是否包含后代行业的股票
            max_display: 最大显示数量（-1表示全部显示）
        """
        from rich.table import Table
        from rich import print as rprint

        # 获取节点信息
        node = None
        if self.industry_tree:
            if isinstance(blockid_or_node, TDXIndustryNode):
                node = blockid_or_node
            else:
                node = self.industry_tree.get_node_by_id(blockid_or_node)

        # 获取股票列表
        if include_descendants and node:
            stocks_dict = self.get_stocks_by_node_with_descendants(node)
            all_stocks = []
            for bid, stocks in stocks_dict.items():
                sub_node = self.industry_tree.get_node_by_id(bid)
                sub_name = sub_node.caption if sub_node else bid
                all_stocks.extend([(bid, sub_name, stock) for stock in stocks])

            title = f"行业 '{node.caption}' 及其子行业股票列表"
        else:
            blockid = blockid_or_node if isinstance(blockid_or_node, str) else blockid_or_node.blockid
            stocks = self.get_stocks_by_blockid(blockid)
            all_stocks = [(blockid, node.caption if node else blockid, stock) for stock in stocks]
            title = f"行业 '{node.caption if node else blockid}' 股票列表"

        # 创建表格
        table = Table(title=title, show_header=True, header_style="bold cyan")
        table.add_column("序号", style="dim")
        table.add_column("股票代码")
        table.add_column("行业ID")
        table.add_column("行业名称")

        display_count = len(all_stocks) if max_display == -1 else min(max_display, len(all_stocks))

        for i, (bid, name, stock) in enumerate(all_stocks[:display_count], 1):
            table.add_row(str(i), stock, bid, name)

        if len(all_stocks) > display_count:
            table.add_row("...", f"还有 {len(all_stocks) - display_count} 只", "", "")

        rprint(table)
        print(f"📊 总计: {len(all_stocks)} 只股票")

    def print_industry_by_stock(self, stock_code: str):
        """
        打印股票所属的行业信息

        Args:
            stock_code: 股票代码
        """
        from rich.table import Table
        from rich import print as rprint

        normalized = self._normalize_stock_code(stock_code)
        blockid = self.stock_to_blockid.get(normalized)

        if not blockid:
            print(f"✗ 未找到股票 {stock_code} 的行业信息")
            return

        # 获取行业树路径
        path_nodes = []
        if self.industry_tree:
            path_nodes = self.industry_tree.get_path_to_root(blockid)

        # 创建表格
        table = Table(title=f"股票 {normalized} 所属行业", show_header=True, header_style="bold green")
        table.add_column("层级", style="cyan")
        table.add_column("行业ID")
        table.add_column("行业名称")

        if path_nodes:
            for i, node in enumerate(path_nodes, 1):
                table.add_row(f"L{node.get_level()}", node.blockid, node.caption)
        else:
            # 如果没有行业树，只显示ID
            table.add_row("未知", blockid, "（无行业树信息）")

        rprint(table)

    def export_mapping(self, output_path: str, format: str = 'csv'):
        """
        导出映射关系

        Args:
            output_path: 输出文件路径
            format: 导出格式，支持 'csv', 'json', 'xlsx'
        """
        import csv
        import json

        if format == 'csv':
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['股票代码', '市场', 'T代码', '行业ID', '行业名称'])

                for full_code, info in self.stock_info.items():
                    node = None
                    if self.industry_tree:
                        node = self.industry_tree.get_node_by_id(info['blockid'])

                    writer.writerow([
                        full_code,
                        info['market_prefix'],
                        info['t_code'],
                        info['blockid'],
                        node.caption if node else ''
                    ])

            print(f"✓ 已导出 {len(self.stock_info)} 条记录到 {output_path}")

        elif format == 'json':
            data = []
            for full_code, info in self.stock_info.items():
                node = None
                if self.industry_tree:
                    node = self.industry_tree.get_node_by_id(info['blockid'])

                data.append({
                    'stock_code': full_code,
                    'market': info['market_prefix'],
                    't_code': info['t_code'],
                    'blockid': info['blockid'],
                    'industry_name': node.caption if node else ''
                })

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"✓ 已导出 {len(data)} 条记录到 {output_path}")

        else:
            raise ValueError(f"不支持的导出格式: {format}")


def test_tdx_mapper():
    """测试函数"""
    import os

    # 测试文件路径 - 根据实际情况修改
    tdx_root = os.environ.get('TDX_ROOT', "D:\\new_tdx")
    hy_xml = os.path.join(tdx_root, "T0002", "cloud_cfg", "hy_tree.xml")
    tdx_cfg = os.path.join(tdx_root, "T0002", "hq_cache", "tdxhy.cfg")

    try:
        print("=" * 60)
        print("测试1: 仅加载映射文件（无行业树）")
        print("=" * 60)

        mapper = TDXIndustryStockMapper(tdx_root=tdx_root)
        mapper.display_statistics()

        # 测试查询
        stock = "000001.SZ"
        blockid = mapper.get_blockid_by_stock(stock)
        print(f"\n股票 {stock} 所属行业ID: {blockid}")

        # 查询某行业的股票
        stocks = mapper.get_stocks_by_blockid("X500102")
        print(f"行业 X500102 包含股票数: {len(stocks)}")
        print(f"  前5只: {stocks[:5]}")

        print("\n" + "=" * 60)
        print("测试2: 加载行业树和映射文件")
        print("=" * 60)

        # 先加载行业树
        tree = TDXIndustryTree(xml_path=hy_xml, encoding='gbk')
        print("✓ 行业树加载成功")

        # 加载映射器并关联行业树
        mapper2 = TDXIndustryStockMapper(cfg_path=tdx_cfg, industry_tree=tree)
        mapper2.display_statistics()

        # 测试按股票查行业路径
        print("\n查询股票 000001 的行业路径:")
        mapper2.print_industry_by_stock("000001")

        # 测试按行业查股票
        print("\n查询行业 '股份制银行' 的股票:")
        bank_node = tree.get_node_by_id("X500102")  # 股份制银行
        if bank_node:
            mapper2.print_stocks_by_industry(bank_node, max_display=10)

        # 测试包含子行业的查询
        print("\n查询行业 '银行' 及其子行业的股票:")
        bank_parent = tree.get_node_by_id("X50")  # 银行
        if bank_parent:
            mapper2.print_stocks_by_industry(bank_parent, include_descendants=True, max_display=15)

        # 导出测试
        # mapper2.export_mapping("industry_stock_mapping.csv", format='csv')

    except FileNotFoundError as e:
        print(f"✗ 文件未找到: {e}")
    except Exception as e:
        print(f"✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_tdx_mapper()

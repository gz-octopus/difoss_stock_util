#!python
# encoding: utf-8
# author: DifossChen
#
import xml.etree.ElementTree as ET
import codecs
from typing import Optional, List, Dict, Union, Tuple, Any
from rich.tree import Tree as RichTree
from rich import print as rprint
from rich.text import Text
from pathlib import Path
import os

__all__ = ['TDXIndustryNode', 'TDXIndustryTree']

class TDXIndustryNode:
    """行业树节点类"""
    def __init__(self, caption: str, blockid: str, visible: bool = True):
        self.caption = caption
        self.blockid = blockid
        self.visible = visible
        self.parent = None
        self.children = []
        
    def add_child(self, child_node):
        """添加子节点"""
        child_node.parent = self
        self.children.append(child_node)
        
    def get_level(self) -> int:
        """获取节点层级：1级(X10), 2级(X1001), 3级(X100101)"""
        # 去掉前缀X，计算剩余数字长度
        if len(self.blockid) <= 3:  # X10, X99等
            return 1
        elif len(self.blockid) == 5:  # X1001, X5001等
            return 2
        elif len(self.blockid) == 7:  # X100101, X500101等
            return 3
        else:
            return 0  # 未知层级
    
    def get_siblings(self) -> List['TDXIndustryNode']:
        """获取兄弟节点（不包括自己）"""
        if self.parent is None:
            return []
        return [child for child in self.parent.children if child != self]
    
    def get_ancestors(self) -> List['TDXIndustryNode']:
        """获取所有祖先节点（从父节点到根节点）"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors
    
    def get_descendants(self, include_self=False) -> List['TDXIndustryNode']:
        """获取所有后代节点（深度优先）"""
        descendants = []
        
        def dfs(node):
            for child in node.children:
                descendants.append(child)
                dfs(child)
        
        if include_self:
            descendants.append(self)
        dfs(self)
        return descendants
    
    def __repr__(self):
        return f"TDXIndustryNode(caption='{self.caption}', blockid='{self.blockid}', level={self.get_level()})"


class TDXIndustryTree:
    """通达信行业树管理类"""
    
    def __init__(self,
                xml_path: Optional[str] = None,
                xml_content: Optional[str] = None,
                tdx_root: Optional[str] = None,
                encoding: str = 'gbk'):
        """
        初始化行业树
        
        Args:
            xml_path: XML文件路径      （三选一）
            xml_content: XML内容字符串 （三选一）
            tdx_root: 通达信根目录     （三选一）
            encoding: XML文件编码（默认gbk）
        """
        self.root = None
        self.nodes_by_id: Dict[str, TDXIndustryNode] = {}
        self.nodes_by_caption: Dict[str, List[TDXIndustryNode]] = {}
        self.encoding = encoding
        
        if xml_path:
            self.load_from_file(xml_path)
        elif xml_content:
            self.load_from_string(xml_content)
        elif tdx_root:
            tdx_root_path = Path(tdx_root)
            if not tdx_root_path.exists():
                raise FileExistsError(f"通达信安装目录不存在: {tdx_root}")
            hy_tree_xml_path = tdx_root_path / 'T0002' / 'cloud_cfg' / 'hy_tree.xml'
            self.load_from_file(hy_tree_xml_path)
            

    def load_from_file(self, xml_path: str, encoding: str = 'gbk'):
        """从XML文件加载（兼容各种编码）"""
        # 使用二进制模式读取，然后尝试不同编码
        with open(xml_path, 'rb') as f:
            content = f.read()
        
        # 尝试常见编码
        if not encoding:
            encodings = ['gbk', 'gb2312', 'utf-8', 'utf-16', 'latin-1']
        else:
            encodings = [encoding]

        for encoding in encodings:
            try:
                decoded = content.decode(encoding)
                # 检查是否是有效的XML
                root = ET.fromstring(decoded)
                self._build_tree(root)
                print(f"✓ 使用编码 {encoding} 成功解析")
                return
            except (UnicodeDecodeError, ET.ParseError):
                continue
        
        # 如果所有编码都失败，抛出异常
        raise ValueError(f"无法解析XML文件，尝试了所有编码: {encodings}")
    
    def load_from_string(self, xml_content: str):
        """从XML字符串加载"""
        try:
            # 尝试直接解析
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            # 如果失败，尝试添加XML声明
            if not xml_content.startswith('<?xml'):
                xml_content = f'<?xml version="1.0" encoding="utf-8"?>\n{xml_content}'
                root = ET.fromstring(xml_content)
            else:
                raise
        self._build_tree(root)
    
    def _build_tree(self, xml_root):
        """构建行业树结构"""
        # 找到第一个node元素（通达信研究行业）
        tree_node = xml_root.find('.//tree/node')
        if tree_node is None:
            raise ValueError("未找到行业树数据")
        
        self.root = self._parse_node(tree_node, None)
    
    def _parse_node(self, xml_node, parent_node: Optional[TDXIndustryNode]) -> TDXIndustryNode:
        """递归解析XML节点"""
        caption = xml_node.get('caption', '')
        blockid = xml_node.get('blockid', '')
        visible = xml_node.get('visible', 'TRUE').upper() == 'TRUE'
        
        node = TDXIndustryNode(caption, blockid, visible)
        node.parent = parent_node
        
        # 添加到索引
        self.nodes_by_id[blockid] = node
        if caption:
            if caption not in self.nodes_by_caption:
                self.nodes_by_caption[caption] = []
            self.nodes_by_caption[caption].append(node)
        
        # 递归处理子节点
        for child_xml in xml_node.findall('node'):
            child_node = self._parse_node(child_xml, node)
            node.add_child(child_node)
        
        return node
    
    # ================ 查询方法 ================
    
    def get_node_by_id(self, blockid: str) -> Optional[TDXIndustryNode]:
        """通过blockid获取节点"""
        return self.nodes_by_id.get(blockid)
    
    def get_nodes_by_caption(self, caption: str) -> List[TDXIndustryNode]:
        """通过caption获取节点列表（可能有同名行业）"""
        return self.nodes_by_caption.get(caption, [])
    
    def get_parent(self, blockid_or_node: Union[str, TDXIndustryNode]) -> Optional[TDXIndustryNode]:
        """获取父节点"""
        node = self._get_node(blockid_or_node)
        return node.parent if node else None
    
    def get_children(self, blockid_or_node: Union[str, TDXIndustryNode]) -> List[TDXIndustryNode]:
        """获取子节点列表"""
        node = self._get_node(blockid_or_node)
        return node.children if node else []
    
    def get_siblings(self, blockid_or_node: Union[str, TDXIndustryNode]) -> List[TDXIndustryNode]:
        """获取兄弟节点列表（不包括自己）"""
        node = self._get_node(blockid_or_node)
        return node.get_siblings() if node else []
    
    def get_level(self, blockid_or_node: Union[str, TDXIndustryNode]) -> int:
        """获取行业层级"""
        node = self._get_node(blockid_or_node)
        return node.get_level() if node else -1
    
    def get_ancestors(self, blockid_or_node: Union[str, TDXIndustryNode]) -> List[TDXIndustryNode]:
        """获取所有祖先节点"""
        node = self._get_node(blockid_or_node)
        return node.get_ancestors() if node else []
    
    def get_descendants(self, blockid_or_node: Union[str, TDXIndustryNode], 
                        include_self: bool = False) -> List[TDXIndustryNode]:
        """获取所有后代节点"""
        node = self._get_node(blockid_or_node)
        return node.get_descendants(include_self) if node else []
    
    def find_nodes_by_pattern(self, pattern: str, search_in: str = 'both') -> List[TDXIndustryNode]:
        """
        通过模式查找节点
        
        Args:
            pattern: 搜索模式（支持部分匹配）
            search_in: 'caption'仅搜索标题, 'id'仅搜索ID, 'both'都搜索
        """
        results = []
        pattern_lower = pattern.lower()
        
        for node in self.nodes_by_id.values():
            if search_in in ['caption', 'both'] and pattern_lower in node.caption.lower():
                results.append(node)
            elif search_in in ['id', 'both'] and pattern_lower in node.blockid.lower():
                results.append(node)
        
        return results
    
    def get_tree_structure(self, node: Optional[TDXIndustryNode] = None, 
                          depth: int = 0, max_depth: int = 3) -> List[str]:
        """获取树形结构字符串表示"""
        if node is None:
            node = self.root
        
        lines = []
        indent = "  " * depth
        lines.append(f"{indent}{node.caption} [{node.blockid}] (L{node.get_level()})")
        
        if depth < max_depth:
            for child in node.children:
                lines.extend(self.get_tree_structure(child, depth + 1, max_depth))
        
        return lines
    
    def _get_node(self, blockid_or_node: Union[str, TDXIndustryNode]) -> Optional[TDXIndustryNode]:
        """统一获取节点对象"""
        if isinstance(blockid_or_node, TDXIndustryNode):
            return blockid_or_node
        elif isinstance(blockid_or_node, str):
            return self.get_node_by_id(blockid_or_node)
        return None
    
    def get_all_nodes(self, level: Optional[int] = None) -> List[TDXIndustryNode]:
        """获取所有节点（可筛选层级）"""
        if level is None:
            return list(self.nodes_by_id.values())
        return [node for node in self.nodes_by_id.values() if node.get_level() == level]
    
    def get_path_to_root(self, blockid_or_node: Union[str, TDXIndustryNode]) -> List[TDXIndustryNode]:
        """获取从节点到根节点的路径"""
        node = self._get_node(blockid_or_node)
        if not node:
            return []
        
        path = [node]
        current = node.parent
        while current:
            path.append(current)
            current = current.parent
        
        return list(reversed(path))  # 从根节点到当前节点
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取行业树统计信息"""
        stats = {
            'total_nodes': len(self.nodes_by_id),
            'level_counts': {},
            'depth': 0,
            'root_caption': self.root.caption if self.root else None,
        }
        
        # 统计各层级数量
        for node in self.nodes_by_id.values():
            level = node.get_level()
            if level not in stats['level_counts']:
                stats['level_counts'][level] = 0
            stats['level_counts'][level] += 1
        
        # 计算最大深度
        def max_depth(node, current_depth):
            if not node.children:
                return current_depth
            return max(max_depth(child, current_depth + 1) for child in node.children)
        
        if self.root:
            stats['depth'] = max_depth(self.root, 0)
        
        return stats
    
    # ================ Rich Tree 可视化接口 ================
    
    def display_tree(self, 
                     start_node: Optional[Union[str, TDXIndustryNode]] = None,
                     show_full_tree: bool = True,
                     show_path_only: bool = False,
                     max_depth: Optional[int] = None,
                     title: Optional[str] = None) -> RichTree:
        """
        使用 Rich Tree 显示行业树
        
        Args:
            start_node: 起始节点（ID或节点对象），None表示从根节点开始
            show_full_tree: True显示完整子树，False只显示到指定节点的路径
            show_path_only: True只显示到指定节点的路径（不包括兄弟节点）
            max_depth: 最大显示深度
            title: 树形图的标题
            
        Returns:
            RichTree 对象，可用于进一步渲染
        """
        # 获取起始节点
        if start_node is None:
            start_node = self.root
        else:
            start_node = self._get_node(start_node)
            if start_node is None:
                raise ValueError(f"未找到节点: {start_node}")
        
        # 设置标题
        if title is None:
            if show_path_only:
                title = f"行业路径: {start_node.caption} [{start_node.blockid}]"
            elif start_node == self.root:
                title = "通达信行业分类树"
            else:
                title = f"行业子树: {start_node.caption} [{start_node.blockid}]"
        
        # 创建 Rich Tree
        tree = RichTree(Text(title, style="bold cyan"))
        
        if show_path_only:
            # 只显示到指定节点的路径
            self._add_path_to_tree(tree, start_node, max_depth)
        elif show_full_tree:
            # 显示完整子树
            self._add_subtree_to_tree(tree, start_node, max_depth, 0)
        else:
            # 显示从起始节点开始的子树
            self._add_subtree_to_tree(tree, start_node, max_depth, 0)
        
        return tree
    
    def _add_subtree_to_tree(self, 
                            rich_tree: RichTree,
                            node: TDXIndustryNode,
                            max_depth: Optional[int],
                            current_depth: int) -> None:
        """
        递归添加子树到 Rich Tree
        
        Args:
            rich_tree: Rich Tree 对象或其分支
            node: 当前节点
            max_depth: 最大深度限制
            current_depth: 当前深度
        """
        # 检查深度限制
        if max_depth is not None and current_depth >= max_depth:
            return
        
        # 创建节点标签
        label = self._create_node_label(node)
        
        # 如果有子节点，创建分支
        if node.children:
            branch = rich_tree.add(label)
            for child in node.children:
                self._add_subtree_to_tree(branch, child, max_depth, current_depth + 1)
        else:
            rich_tree.add(label)
    
    def _add_path_to_tree(self, 
                         rich_tree: RichTree,
                         target_node: TDXIndustryNode,
                         max_depth: Optional[int]) -> None:
        """
        添加从根节点到目标节点的路径（不包括兄弟节点）
        
        Args:
            rich_tree: Rich Tree 对象
            target_node: 目标节点
            max_depth: 最大深度限制
        """
        # 获取到根节点的路径
        path = self.get_path_to_root(target_node)
        
        current_branch = rich_tree
        current_depth = 0
        
        # 添加路径上的每个节点
        for i, node in enumerate(path):
            if max_depth is not None and current_depth >= max_depth:
                break
                
            label = self._create_node_label(node)
            
            # 如果是最后一个节点（目标节点）
            if i == len(path) - 1:
                current_branch.add(Text(label, style="bold green"))
            else:
                # 如果不是最后一个节点，创建分支
                branch = current_branch.add(label)
                current_branch = branch
            
            current_depth += 1
    
    def _create_node_label(self, node: TDXIndustryNode) -> str:
        """
        创建节点标签
        
        Args:
            node: 行业节点
            
        Returns:
            格式化的节点标签字符串
        """
        # 根据层级设置不同的样式提示
        level_markers = {
            1: "🌲",  # 一级行业
            2: "🌳",  # 二级行业
            3: "🌿",  # 三级行业
            0: "❓"   # 未知层级
        }
        
        marker = level_markers.get(node.get_level(), "📌")
        
        if node.children:
            # 有子节点的显示不同
            marker = "📂" if marker == "🌲" else "📁"
        
        return f"{marker} {node.caption} [{node.blockid}] (L{node.get_level()})"
    
    def print_tree(self, 
                   start_node: Optional[Union[str, TDXIndustryNode]] = None,
                   show_full_tree: bool = True,
                   show_path_only: bool = False,
                   max_depth: Optional[int] = None,
                   title: Optional[str] = None) -> None:
        """
        打印 Rich Tree 可视化
        
        Args:
            start_node: 起始节点（ID或节点对象），None表示从根节点开始
            show_full_tree: True显示完整子树，False只显示到指定节点的路径
            show_path_only: True只显示到指定节点的路径（不包括兄弟节点）
            max_depth: 最大显示深度
            title: 树形图的标题
        """
        tree = self.display_tree(start_node, show_full_tree, show_path_only, max_depth, title)
        rprint(tree)
    
    def display_all_industries(self, max_depth: Optional[int] = None) -> None:
        """显示完整的行业树"""
        stats = self.get_statistics()
        title = f"通达信行业分类树 (共{stats['total_nodes']}个行业)"
        self.print_tree(
            start_node=None,
            show_full_tree=True,
            max_depth=max_depth,
            title=title
        )
    
    def display_industry_path(self, 
                            blockid_or_node: Union[str, TDXIndustryNode],
                            max_depth: Optional[int] = None) -> None:
        """显示到指定行业的路径（不包括兄弟节点）"""
        self.print_tree(
            start_node=blockid_or_node,
            show_full_tree=False,
            show_path_only=True,
            max_depth=max_depth
        )
    
    def display_sub_industries(self, 
                            blockid_or_node: Union[str, TDXIndustryNode],
                            max_depth: Optional[int] = None) -> None:
        """显示指定行业及其子行业"""
        self.print_tree(
            start_node=blockid_or_node,
            show_full_tree=True,
            max_depth=max_depth
        )
    
    def display_level_industries(self, level: int = 1) -> None:
        """显示指定层级的行业列表"""
        nodes = self.get_all_nodes(level=level)
        
        # 创建 Rich Tree 显示一级行业
        tree = RichTree(Text(f"第 {level} 级行业列表", style="bold cyan"))
        
        for node in sorted(nodes, key=lambda x: x.blockid):
            label = self._create_node_label(node)
            tree.add(label)
        
        rprint(tree)
        
        # 同时打印统计信息
        print(f"\n📊 第 {level} 级行业统计:")
        print(f"   总数: {len(nodes)} 个行业")
        if nodes:
            print(f"   示例: {nodes[0].caption} [{nodes[0].blockid}]")
            if len(nodes) > 1:
                print(f"   示例: {nodes[-1].caption} [{nodes[-1].blockid}]")
    
    def display_statistics(self) -> None:
        """显示行业树统计信息"""
        stats = self.get_statistics()
        
        from rich.table import Table
        from rich.panel import Panel
        
        table = Table(title="行业树统计信息", show_header=True, header_style="bold magenta")
        table.add_column("项目", style="cyan")
        table.add_column("数值", style="green")
        
        table.add_row("总行业数", str(stats['total_nodes']))
        table.add_row("树深度", str(stats['depth']))
        table.add_row("根节点", stats['root_caption'] or "无")
        
        # 添加层级统计
        for level in sorted(stats['level_counts'].keys()):
            table.add_row(f"第 {level} 级行业数", str(stats['level_counts'][level]))
        
        rprint(Panel(table, title="📊 通达信行业统计", border_style="blue"))


def test_tdx_industry():
    """测试函数"""
    tdx_root = os.environ.get('TDX_ROOT', "D:\\new_tdx")
    
    try:
        # 创建行业树实例，指定编码为gbk
        tree = TDXIndustryTree(tdx_root=tdx_root)
        
        print("✓ 行业树加载成功！")
        
        # 显示统计信息
        tree.display_statistics()
        
        # 显示完整行业树（限制深度为2，避免输出太长）
        print("\n显示行业树（最大深度2）:")
        tree.display_all_industries(max_depth=2)
        
        # 测试查询功能
        print("\n测试查询功能:")
        print("-" * 40)
        
        # 查询煤炭开采
        node = tree.get_node_by_id("X1001")
        if node:
            print(f"1. 查询X1001: {node.caption}")
            print(f"   层级: {tree.get_level(node)}级")
            
            # 获取父节点
            parent = tree.get_parent(node)
            print(f"   父行业: {parent.caption if parent else '无'}")
            
            # 获取子节点
            children = tree.get_children(node)
            print(f"   子行业数: {len(children)}")
            for child in children:
                print(f"     - {child.caption} [{child.blockid}]")
        
        # 搜索包含"电子"的行业
        electronic_nodes = tree.find_nodes_by_pattern("电子", search_in='caption')
        print(f"\n2. 包含'电子'的行业数: {len(electronic_nodes)}")
        if electronic_nodes:
            print(f"   示例: {electronic_nodes[0].caption} [{electronic_nodes[0].blockid}]")
        
        # 显示一级行业
        print("\n3. 一级行业列表:")
        tree.display_level_industries(level=1)
        
        # 显示具体行业的路径
        print("\n4. 显示具体行业路径:")
        if node:
            tree.display_industry_path(node)
        
    except FileNotFoundError as e:
        print(f"✗ 文件未找到: {e}")
    except Exception as e:
        print(f"✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 直接运行测试
    test_tdx_industry()
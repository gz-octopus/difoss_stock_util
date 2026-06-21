#!python
# encoding: utf-8
# author: DifossChen
#

__all__ = [
    'SLBFileManager',
]

from .security_util import *
from .security_json_file_util import *

class SLBFileManager(SecurityJsonFileManager):
    """扫雷宝文件管理器"""
    NAME = "SLB"


# 使用示例
def test_slb_file_naming():
    """测试扫雷宝文件命名类"""
    print("=== 扫雷宝文件命名测试 ===")

    # 测试文件名生成
    test_cases = ['000001', '600000.SH', '300750', '159915.SZ']

    for code in test_cases:
        filename = SLBFileManager.generate_filename(code)
        is_slb = SLBFileManager.is_slb_file(filename)

        print(f"代码: {code:10} -> 文件名: {filename:20}  是否SLB文件: {is_slb}")

    # 测试文件名解析
    print("\n=== 文件名解析测试 ===")
    filenames = ['SLB.000001.json', 'SLB.600000.json', 'invalid.txt', 'SLB.300750.json']

    for filename in filenames:
        parsed = SLBFileManager.parse_filename(filename)
        if parsed:
            print(f"文件名: {filename:20} -> 解析结果: {parsed}")
        else:
            print(f"文件名: {filename:20} -> 不是有效的扫雷宝文件")


def test_slb_file_manager():
    """测试扫雷宝文件管理器"""
    print("\n=== 扫雷宝文件管理器测试 ===")

    manager = SLBFileManager("./test_slb_data")

    # 测试保存数据
    test_data = {
        'company_name': '测试公司',
        'risk_level': '中等',
        'financial_data': {
            'revenue': 1000000000,
            'profit': 500000000
        }
    }

    metadata = {
        'source': '扫雷宝',
        'version': '1.0'
    }

    # 保存测试数据
    stock_code = '000001'
    if manager.save_data(stock_code, test_data, metadata):
        print(f"✅ 保存数据成功: {stock_code}")

    # 检查文件是否存在
    if manager.file_exists(stock_code):
        print(f"✅ 文件存在: {stock_code}")

    # 加载数据
    loaded_data = manager.load_data(stock_code)
    if loaded_data:
        print(f"✅ 加载数据成功: {loaded_data['stock_code']}")
        print(f"   数据内容: {loaded_data['data']['company_name']}")
        print(f"   下载时间: {loaded_data['download_time']}")

    # 列出所有文件
    files = manager.list_all_files()
    print(f"📁 文件列表: {len(files)} 个文件")
    for file_info in files:
        print(f"   - {file_info['filename']} ({file_info['file_size']} bytes)")

    # 获取股票代码列表
    stock_codes = manager.get_stock_codes()
    print(f"📊 股票代码列表: {stock_codes}")

    # 统计文件数量
    count = manager.count_files()
    print(f"📈 文件数量: {count}")

    # 清理测试文件
    manager.clear_all_files()
    print("🧹 已清理测试文件")


if __name__ == "__main__":
    test_slb_file_naming()
    test_slb_file_manager()
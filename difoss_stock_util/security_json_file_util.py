#!python
# encoding: utf-8
# author: DifossChen
#

__all__ = [
    'SecurityJsonFileNaming',
    'SecurityJsonFileManager',
]

import json
from pathlib import Path
from typing import Optional, Dict, Any, Union
from datetime import datetime
from .security_util import *
from .color_log_util import *
from .util import trace_func

class SecurityJsonFileNaming:
    """JSON类证券相关文件命名类"""
    NAME = ''
    
    @classmethod
    def generate_filename(cls, stock_code: SecurityCode) -> str:
        """
        生成扫雷宝文件名
        
        Args:
            stock_code: 股票代码（支持完整代码或6位代码）
            
        Returns:
            str: 文件名，格式为 {cls.NAME}.{full_code}.json
        """
        return f"{cls.NAME}.{stock_code.full_code}.json"
        
    @classmethod
    def parse_filename(cls, filename: str) -> Optional[Dict[str, str]]:
        """
        解析扫雷宝文件名
        
        Args:
            filename: 文件名
            
        Returns:
            dict: 包含解析信息的字典，或None（如果不是扫雷宝文件）
        """
        if not filename.startswith(f'{cls.NAME}.') or not filename.endswith('.json'):
            return None
        
        try:
            # 移除前缀和后缀
            code_part = filename[4:-5]  # 移除 "{cls.NAME}." 和 ".json"
            
            code = SecurityCode(code_part)
            # I(filename=filename, NAME=cls.NAME, code=code)
            return {
                'filename': filename,
                'short_code': code.short_code,
                'full_code': code.full_code,
            }
        except:
            return None
    
    @classmethod
    def is_valid_file(cls, filename: str) -> bool:
        """
        判断是否为扫雷宝文件
        
        Args:
            filename: 文件名
            
        Returns:
            bool: 是否为扫雷宝文件
        """
        return filename.startswith(f'{cls.NAME}.') and filename.endswith('.json')
    
    @classmethod
    def get_stock_code_from_filename(cls, filename: str) -> Optional[str]:
        """
        从文件名中提取股票代码
        
        Args:
            filename: 文件名
            
        Returns:
            str: 6位股票代码，或None（如果不是扫雷宝文件）
        """
        parsed = cls.parse_filename(filename)
        return parsed['short_code'] if parsed else None
    
    
class SecurityJsonFileManager(SecurityJsonFileNaming):
    """JSON类证券相关文件管理器"""
    NAME = ""
    
    @classmethod
    def generate_dirname(cls, dt: datetime) -> str:
        return f'{cls.NAME}-{dt.strftime("%Y%m%d")}'
    
    def __init__(self, base_dir: str = None):
        """
        初始化文件管理器
        
        Args:
            base_dir: 基础目录路径
        """
        if not base_dir:
            base_dir = self.generate_dirname(datetime.now())
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def get_file_path(self, stock_code: SecurityCode) -> Path:
        """
        获取文件路径
        
        Args:
            stock_code: 股票代码
            
        Returns:
            Path: 文件路径
        """
        filename = self.generate_filename(stock_code)
        return self.base_dir / filename
    
    def save_data(self, stock_code: SecurityCode, data: Dict[str, Any], 
                  metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        保存数据到文件
        
        Args:
            stock_code: 股票代码
            data: 要保存的数据
            metadata: 元数据（下载时间等）
            
        Returns:
            bool: 是否保存成功
        """
        try:
            file_path = self.get_file_path(stock_code)
            
            # 准备保存的数据
            save_data = {
                'data': data,
                'metadata': metadata or {},
                'download_time': datetime.now().isoformat(),
                'stock_code': stock_code.full_code,
                'short_code': stock_code.short_code,
            }
            
            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            print(f"保存数据失败: {e}")
            return False
    
    def load_data(self, stock_code: SecurityCode) -> Optional[Dict[str, Any]]:
        """
        从文件加载数据
        
        Args:
            stock_code: 股票代码
            
        Returns:
            dict: 数据，或None（如果文件不存在或读取失败）
        """
        try:
            file_path = self.get_file_path(stock_code)
            
            if not file_path.exists():
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            print(f"加载数据失败: {e}")
            return None
    
    def file_exists(self, stock_code: SecurityCode) -> bool:
        """
        检查文件是否存在
        
        Args:
            stock_code: 股票代码
            
        Returns:
            bool: 文件是否存在
        """
        file_path = self.get_file_path(stock_code)
        return file_path.exists()
    
    def delete_file(self, stock_code: SecurityCode) -> bool:
        """
        删除文件
        
        Args:
            stock_code: 股票代码
            
        Returns:
            bool: 是否删除成功
        """
        try:
            file_path = self.get_file_path(stock_code)
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception as e:
            print(f"删除文件失败: {e}")
            return False
    
    def list_all_files(self) -> list[dict]:
        """
        列出所有扫雷宝文件
        
        Returns:
            list: 文件信息列表
        """
        files = []
        for file_path in self.base_dir.glob(f"{self.NAME}.*.json"):
            parsed = self.parse_filename(file_path.name)
            if parsed:
                file_info = {
                    'file_path': file_path,
                    'filename': file_path.name,
                    **parsed,
                    'file_size': file_path.stat().st_size,
                    'modified_time': datetime.fromtimestamp(file_path.stat().st_mtime)
                }
                files.append(file_info)
        
        return files
    
    def get_stock_codes(self) -> list:
        """
        获取所有已保存的股票代码
        
        Returns:
            list: 股票代码列表
        """
        files = self.list_all_files()
        return [file_info['full_code'] for file_info in files]
    
    def count_files(self) -> int:
        """
        统计文件数量
        
        Returns:
            int: 文件数量
        """
        return len(self.list_all_files())
    
    def clear_all_files(self) -> bool:
        """
        清空所有文件
        
        Returns:
            bool: 是否清空成功
        """
        try:
            files = self.list_all_files()
            for file_info in files:
                file_info['file_path'].unlink()
            return True
        except Exception as e:
            print(f"清空文件失败: {e}")
            return False
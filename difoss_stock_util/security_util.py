#!python
# encoding: utf-8
# author: DifossChan
#
__all__ = [
    'DividendType',
    'SecurityType',
    'MarketType',
    'SecurityCode',
]

from enum import Enum, EnumType
from typing import Optional, Union, Tuple, ClassVar, Any
from functools import lru_cache
from rich import print as pprint

# 项目内的 imports
from .color_log_util import *
from .BJ_change_code_2025_10_09 import *

# DEBUG:
from .util import print_locals


class MetadataEnumType(EnumType):
    """
    支持元数据的枚举元类
    参考 EnumType 的设计模式
    """

    @classmethod
    def __prepare__(metacls, cls, bases, **kwds):
        # 创建命名空间字典
        enum_dict = super().__prepare__(cls, bases, **kwds)
        return enum_dict

    def __new__(metacls, cls, bases, classdict, **kwds):
        # 先创建枚举类
        enum_class = super().__new__(metacls, cls, bases, classdict, **kwds)

        # 检查是否有 METADATA 定义（不使用下划线）
        if 'METADATA' in classdict:
            metadata = classdict['METADATA']

            # 构建各种映射字典
            enum_class._int_to_enum = {}
            enum_class._enum_to_int = {}
            enum_class._enum_to_chinese = {}
            enum_class._str_to_enum = {}
            enum_class._chinese_to_enum = {}

            # 收集所有枚举成员
            members = {}
            for name in dir(enum_class):
                attr = getattr(enum_class, name)
                if isinstance(attr, enum_class):
                    members[name] = attr

            # 处理元数据
            for item in metadata:
                if len(item) == 4:
                    enum_name, str_val, int_val, chinese_name = item

                    enum_member = members.get(enum_name)
                    if enum_member:
                        if int_val is not None:
                            enum_class._int_to_enum[int_val] = enum_member
                            enum_class._enum_to_int[enum_member] = int_val
                        if chinese_name:
                            enum_class._enum_to_chinese[enum_member] = chinese_name
                            enum_class._chinese_to_enum[chinese_name] = enum_member
                        if str_val is not None and str_val != '':
                            enum_class._str_to_enum[str_val] = enum_member

        return enum_class

    def __call__(cls, value, *args, **kwds):
        """
        重写 __call__ 方法来处理各种类型的值
        """
        # 如果 value 已经是枚举成员，直接返回
        if isinstance(value, cls):
            return value

        # 处理 None
        if value is None:
            value = ''

        # 处理字符串
        if isinstance(value, str):
            # 如果是数字字符串，尝试转整数
            if value.isdigit():
                try:
                    int_val = int(value)
                    if int_val in cls._int_to_enum:
                        return cls._int_to_enum[int_val]
                except ValueError:
                    pass
            # 尝试从字符串值查找
            if hasattr(cls, '_str_to_enum') and value in cls._str_to_enum:
                return cls._str_to_enum[value]

        # 处理整数
        if isinstance(value, int):
            if hasattr(cls, '_int_to_enum') and value in cls._int_to_enum:
                return cls._int_to_enum[value]

        # 调用父类的 __call__ 处理其他情况
        return super().__call__(value, *args, **kwds)

    def __init__(cls, clsname, bases, classdict, **kwds):
        super().__init__(clsname, bases, classdict, **kwds)

        # 只有在有映射字典时才添加额外的方法
        if hasattr(cls, '_int_to_enum'):
            # 添加属性方法
            @property
            def str_value(self):
                """获取字符串值"""
                return next(
                    (s for s, e in self.__class__._str_to_enum.items() if e == self),
                    ''
                )
            cls.str_value = str_value

            @property
            def int_value(self) -> int:
                """获取整数值"""
                return self.__class__._enum_to_int.get(self, -1)
            cls.int_value = int_value

            @property
            def chinese_name(self):
                """获取中文名称"""
                return self.__class__._enum_to_chinese.get(self, '')
            cls.chinese_name = chinese_name

            @classmethod
            def from_int(cls, value):
                """从整数值获取枚举成员"""
                if isinstance(value, Enum):
                    value = value.value
                return cls._int_to_enum.get(value)
            cls.from_int = classmethod(from_int)

            @classmethod
            def from_str(cls, value):
                """从字符串值获取枚举成员"""
                return cls._str_to_enum.get(value)
            cls.from_str = classmethod(from_str)

            @classmethod
            def chinese_name_2_en(cls, chinese_name):
                """中文名称→枚举值的字符串值"""
                enum_member = cls._chinese_to_enum.get(chinese_name)
                if enum_member:
                    return next(
                        (s for s, e in cls._str_to_enum.items() if e == enum_member),
                        None
                    )
                return None
            cls.chinese_name_2_en = classmethod(chinese_name_2_en)

            @classmethod
            @lru_cache(maxsize=1)
            def allows(cls):
                """获取允许的字符串值列表"""
                return list(cls._str_to_enum.keys())
            cls.allows = classmethod(allows)

            @classmethod
            @lru_cache(maxsize=1)
            def allows_cn(cls):
                """获取允许的中文名称列表"""
                return [name for name in cls._chinese_to_enum.keys() if name]
            cls.allows_cn = classmethod(allows_cn)

            def __str__(self):
                """字符串表示返回字符串值"""
                return self.str_value
            cls.__str__ = __str__

            def __repr__(self):
                """更友好的表示"""
                return f"<{self.__class__.__name__}.{self.name}: str='{self.str_value}', int={self.int_value}, cn='{self.chinese_name}'>"
            cls.__repr__ = __repr__

class MetadataEnum(Enum, metaclass=MetadataEnumType):
    """
    支持元数据的枚举基类

    使用示例：
        class MyEnum(MetadataEnum):
            METADATA = [
                ('MEMBER_NAME', 'str_value', int_value, '中文名称'),
                ...
            ]

            MEMBER_NAME = 'str_value'
    """
    pass

# 使用新基类重新定义三个枚举
class DividendType(MetadataEnum):
    """复权类型"""
    METADATA = [
        ('UNADJUSTED', 'none', 0, '不复权'),
        ('FORWARD_ADJUSTED', 'front', 1, '前复权'),
        ('BACKWARD_ADJUSTED', 'back', 2, '后复权'),
    ]

    UNADJUSTED = 'none'
    FORWARD_ADJUSTED = 'front'
    BACKWARD_ADJUSTED = 'back'

class SecurityType(MetadataEnum):
    """证券类型"""
    METADATA = [
        ('STOCK', 'stock', 1, '股票'),
        ('STOCK_B', 'stock_b', 2, 'B股'),
        ('FUND', 'fund', 3, '基金'),
        ('BOND', 'bond', 4, '债券'),
        ('INDEX', 'index', 5, '指数'),
        ('TDX_INDEX', 'tdx_index', 6, '通达信指数'),
        ('OPTION', 'option', 7, '期权'),
        ('FUTURES', 'futures', 8, '期货'),
        ('FUTURES_OPTION', 'futures_option', 12, '期货期权'), # 新增期货期权类型
        ('WARRANT', 'warrant', 9, '权证'),
        ('REPO', 'repo', 10, '回购'),
        ('OTHER', 'other', 99, '其他'),
    ]

    STOCK = "stock"
    STOCK_B = "stock_b"
    FUND = "fund"
    BOND = "bond"
    INDEX = "index"
    TDX_INDEX = "tdx_index"
    OPTION = "option"
    FUTURES = "futures"
    FUTURES_OPTION = "futures_option"
    WARRANT = "warrant"
    REPO = "repo"
    OTHER = "other"

class MarketType(MetadataEnum):
    """市场类型"""
    METADATA = [
        ('NULL', '', -1, ''),
        ('SZ', 'SZ', 0, '深圳交易所'),
        ('SH', 'SH', 1, '上海交易所'),
        ('BJ', 'BJ', 2, '北京交易所'),
        ('NQ', 'NQ', 44, '新三板'),
        ('SHO', 'SHO', 8, '上海个股期权'),
        ('SZO', 'SZO', 9, '深证个股期权'),
        ('HK', 'HK', 31, '港股个股'),
        ('US', 'US', 74, '美国股票'),
        ('CSI', 'CSI', 62, '中证指数'),
        ('CNI', 'CNI', 102, '国证指数'),
        ('HG', 'HG', 38, '国内宏观指标'),
        ('CFF', 'CFF', 47, '中金期货'),
        ('CZC', 'CZC', 28, '郑州期货'),
        ('DCE', 'DCE', 29, '大连期货'),
        ('SHF', 'SHF', 30, '上海期货'),
        ('GFE', 'GFE', 66, '广州期货'),
        ('INE', 'INE', 30, '上海能源'), # 能源中心
        ('HI', 'HI', 27, '港股指数'),
        ('OF', 'OF', 33, '开放式基金净值'),
        ('CFFO', 'CFFO', 7, '中金期货期权'),
        ('CZCO', 'CZCO', 4, '郑州期货期权'),
        ('DCEO', 'DCEO', 5, '大连期货期权'),
        ('SHFO', 'SHFO', 6, '上海期货期权'),
        ('GFEO', 'GFEO', 67, '广州期货期权'),

        # xtquant 里面的市场代码
        ('SF', 'SF', 50, '上海期货交易所'),          # 上期所   SHFE
        ('DF', 'DF', 48, '大连商品期货交易所'),      # 大商所   DCE
        ('ZF', 'ZF', 49, '郑州商品期货交易所'),      # 郑商所   CZCE
        ('IF', 'IF', 51, '中国金融期货交易所'),      # 中金所   GFFEX
        ('GF', 'GF', 52, '广州期货交易所'),          # 广期所   GFEX

        # 暂时不知道哪些标的使用哪个市场代码，先保留原来的市场代码，等后续有数据了再调整
        ('SHFE', 'SHFE', 50, '上海期货交易所'),
        ('CZCE', 'CZCE', 49, '郑州商品期货交易所'),
        ('GFFEX', 'GFFEX', 51, '中国金融期货交易所'),
        ('GFEX', 'GFEX', 52, '广州期货交易所'),
    ]

    NULL = ''
    SZ = 'SZ'
    SH = 'SH'
    BJ = 'BJ'
    NQ = 'NQ'
    SHO = 'SHO'
    SZO = 'SZO'
    HK = 'HK'
    US = 'US'
    CSI = 'CSI'
    CNI = 'CNI'
    HG = 'HG'
    CFF = 'CFF'
    CZC = 'CZC'
    DCE = 'DCE'
    SHF = 'SHF'
    GFE = 'GFE'
    INE = 'INE'
    HI = 'HI'
    OF = 'OF'
    CFFO = 'CFFO'
    CZCO = 'CZCO'
    DCEO = 'DCEO'
    SHFO = 'SHFO'
    GFEO = 'GFEO'
    SF = 'SF'
    DF = 'DF'
    ZF = 'ZF'
    CF = 'CF'
    GF = 'GF'
    SHFE = 'SHFE'
    CZCE = 'CZCE'
    GFFEX = 'GFFEX'
    GFEX = 'GFEX'

    @classmethod
    @lru_cache(maxsize=1)
    def allows(cls) -> list[str]:
        """覆盖默认实现，只返回部分市场"""
        return ['SH', 'SZ', 'BJ', 'SZO', 'HK']


class SecurityCode:
    """证券代码类"""

    # 添加期货和期货期权代码的正则表达式模式
    FUTURES_PATTERNS = {
        # 大商所期货: 品种代码+到期年月（2位年份+月份）
        # 例如: eb05.DF (eb 25年05月), v2610.DF (v 26年10月)
        'DF': r'^([a-z]+)(\d{2,4})(?:\.DF)?$',
        # 郑商所期货
        'ZF': r'^([a-z]+)(\d{2,4})(?:\.ZF)?$',
        # 上期所期货
        'SF': r'^([a-z]+)(\d{2,4})(?:\.SF)?$',
        # 中金所期货
        'CF': r'^([a-z]+)(\d{2,4})(?:\.CF)?$',
    }

    FUTURES_OPTION_PATTERNS = {
        # 大商所期货期权: 品种代码+到期年月-C/P-行权价
        # 例如: m2612-P-3000.DF, y2609-C-8800.DF
        'DF': r'^([a-z]+)(\d{4})-([CP])-(\d+)\.DF$',
        # 郑商所期货期权
        'ZF': r'^([a-z]+)(\d{4})-([CP])-(\d+)\.ZF$',
        # 上期所期货期权
        'SF': r'^([a-z]+)(\d{4})-([CP])-(\d+)\.SF$',
        # 中金所期货期权
        'CF': r'^([a-z]+)(\d{4})-([CP])-(\d+)\.CF$',
    }

    # 期货品种代码映射（用于识别和标准化）
    FUTURES_PRODUCT_MAP = {
        # 农产品
        'm': '豆粕', 'c': '玉米', 'a': '豆一', 'b': '豆二', 'y': '豆油',
        'p': '棕榈油', 'jd': '鸡蛋', 'lh': '生猪', 'rr': '粳米', 'cs': '玉米淀粉',
        'fb': '纤维板', 'bb': '胶合板', 'eg': '乙二醇', 'eb': '苯乙烯', 'pg': '液化气',
        'pp': '聚丙烯', 'l': '塑料', 'v': '聚氯乙烯', 'i': '铁矿石', 'j': '焦炭',
        'jm': '焦煤', 'jm': '焦煤', 'zc': '动力煤', 'ap': '苹果', 'cf': '棉花',
        'cy': '棉纱', 'ma': '甲醇', 'oi': '菜籽油', 'rm': '菜籽粕', 'rs': '油菜籽',
        'sf': '硅铁', 'sm': '锰硅', 'ta': 'PTA', 'ur': '尿素', 'wh': '强麦',
        'pm': '普麦', 'jr': '粳稻', 'lr': '晚籼稻', 'ri': '早籼稻', 'sr': '白糖',
        'cu': '铜', 'al': '铝', 'zn': '锌', 'pb': '铅', 'ni': '镍', 'sn': '锡',
        'au': '黄金', 'ag': '白银', 'rb': '螺纹钢', 'wr': '线材', 'hc': '热卷',
        'ss': '不锈钢', 'bu': '沥青', 'ru': '橡胶', 'nr': '20号胶', 'sp': '纸浆',
        'sc': '原油', 'lu': '低硫燃料油', 'fu': '燃料油', 'if': '沪深300',
        'ic': '中证500', 'ih': '上证50', 't': '10年期国债', 'tf': '5年期国债',
        'ts': '2年期国债',
    }


    def __init__(
        self,
        code: str,
        market: Union[str, MarketType, None] = None,
        security_type: Optional[SecurityType] = None,
        BJ_old_code = False,
    ):
        """
        初始化证券代码

        Args:
            code: 证券代码，支持 "002367.SZ" 或 "002367" 格式，或 ("002367", "SZ")
            security_type: 证券类型，如果为None则自动推断
            BJ_old_code: 是否使用北交所旧代码
        """
        self._short_code: str = ""
        self._market_code: MarketType = MarketType.NULL
        self._security_type: Optional[SecurityType] = None
        self._futures_info: Optional[dict] = None  # 存储期货/期权信息
        self._option_info: Optional[dict] = None  # 兼容旧属性

        if market:
            self._short_code = code
            self._market_code = MarketType(market)
        else:
            # 解析代码
            if self.is_full_code(code):
                # 完整代码格式: "002367.SZ" 或 "eb05.DF" 或 "m2612-P-3000.DF"
                self._short_code, self._market_code = code.split('.')
            else:
                # 缩写代码格式: "002367" 或 "eb05"
                self._short_code = code
                full_code = self.guess_full_code(code)
                if full_code:
                    self._short_code, self._market_code = full_code.split('.')
                else:
                    self._short_code = code
                    self._market_code = None

        # 尝试转换更名后北交所股票代码
        if BJ_old_code == False:
            self._short_code = old_2_new(self._short_code)

        # 确定证券类型
        if security_type:
            self._security_type = security_type
        else:
            self._security_type = SecurityCode.guess_security_type(self._short_code, self._market_code)


    def _parse_futures_contract(self, code: str, market: str) -> bool:
        """
        解析期货合约代码

        Args:
            code: 期货代码，如 "eb05" 或 "v2610"
            market: 市场代码，如 "DF"

        Returns:
            bool: 是否成功解析
        """
        import re
        pattern = self.FUTURES_PATTERNS.get(market)
        if pattern:
            # 移除可能的市场后缀
            clean_code = code.replace(f'.{market}', '')
            match = re.match(pattern, clean_code)
            if match:
                product_code = match.group(1)
                expiry_code = match.group(2)

                # 解析到期年月
                if len(expiry_code) == 2:  # 格式: 05 (年份简写)
                    # 当前年份的后两位
                    import datetime
                    current_year = datetime.datetime.now().year % 100
                    year_num = int(expiry_code)

                    # 判断是今年还是明年
                    if year_num >= current_year:
                        year = 2000 + year_num
                    else:
                        year = 2000 + year_num + 100
                    month = None  # 只有年份，没有月份
                elif len(expiry_code) == 3:  # 格式: 105 (可能的格式)
                    year = 2000 + int(expiry_code[0])
                    month = int(expiry_code[1:])
                elif len(expiry_code) == 4:  # 格式: 2610 (年份+月份)
                    year = 2000 + int(expiry_code[:2])
                    month = int(expiry_code[2:])
                else:
                    year = None
                    month = None

                self._futures_info = {
                    'type': 'futures',
                    'product_code': product_code,           # 品种代码
                    'product_name': self.FUTURES_PRODUCT_MAP.get(product_code, product_code),  # 品种名称
                    'expiry_code': expiry_code,             # 到期代码
                    'expiry_year': year,                    # 到期年份
                    'expiry_month': month,                  # 到期月份
                    'market': market,                       # 市场
                }

                # 生成到期日期字符串
                if year and month:
                    self._futures_info['expiry_date'] = f"{year}-{month:02d}"
                elif year:
                    self._futures_info['expiry_date'] = f"{year}"

                return True
        return False

    def _parse_futures_option(self, code: str, market: str) -> bool:
        """
        解析期货期权代码

        Args:
            code: 期权代码，如 "m2612-P-3000"
            market: 市场代码，如 "DF"

        Returns:
            bool: 是否成功解析
        """
        import re
        pattern = self.FUTURES_OPTION_PATTERNS.get(market)
        if pattern:
            # 移除可能的市场后缀
            clean_code = code.replace(f'.{market}', '')
            match = re.match(pattern, clean_code)
            if match:
                product_code = match.group(1)
                expiry_code = match.group(2)
                option_type = match.group(3)
                strike_price = int(match.group(4))

                # 解析到期年月
                year = 2000 + int(expiry_code[:2])
                month = int(expiry_code[2:])

                self._futures_info = {
                    'type': 'option',
                    'product_code': product_code,           # 标的品种代码
                    'product_name': self.FUTURES_PRODUCT_MAP.get(product_code, product_code),  # 标的品种名称
                    'expiry_code': expiry_code,             # 到期代码
                    'expiry_year': year,                    # 到期年份
                    'expiry_month': month,                  # 到期月份
                    'expiry_date': f"{year}-{month:02d}",   # 到期日期
                    'option_type': 'CALL' if option_type == 'C' else 'PUT',  # 期权类型
                    'strike_price': strike_price,           # 行权价
                    'market': market,                       # 市场
                }

                # 兼容旧的 option_info 属性
                self._option_info = self._futures_info
                return True
        return False

    @property
    def futures_info(self) -> Optional[dict]:
        """获取期货/期权信息"""
        return self._futures_info

    @property
    def option_info(self) -> Optional[dict]:
        """获取期权信息（兼容旧属性）"""
        return self._option_info if self._option_info else self._futures_info

    @property
    def is_futures(self) -> bool:
        """判断是否为期货合约"""
        return self._futures_info is not None and self._futures_info.get('type') == 'futures'

    @property
    def is_futures_option(self) -> bool:
        """判断是否为期货期权"""
        return self._futures_info is not None and self._futures_info.get('type') == 'option'

    @staticmethod
    def is_futures_code(code: str) -> bool:
        """判断是否为期货合约代码"""
        import re
        for market, pattern in SecurityCode.FUTURES_PATTERNS.items():
            if re.match(pattern, code):
                return True
            if re.match(pattern, code + '.' + market):
                return True
        return False

    @staticmethod
    def is_futures_option_code(code: str) -> bool:
        """判断是否为期货期权代码"""
        import re
        for market, pattern in SecurityCode.FUTURES_OPTION_PATTERNS.items():
            if re.match(pattern, code):
                return True
            if re.match(pattern, code + '.' + market):
                return True
        return False


    @property
    def short_code(self) -> str:
        """6位证券代码"""
        return self._short_code

    @property
    def market_code(self) -> str:
        """市场代码"""
        if self._market_code:
            return str(self._market_code)
        else:
            return ''

    @property
    def security_type(self) -> Optional[SecurityType]:
        """证券类型"""
        return self._security_type

    @property
    def full_code(self) -> str:
        """完整代码"""
        if self._market_code:
            return f"{self.short_code}.{self.market_code}"
        else:
            return f"{self.short_code}"

    def __str__(self) -> str:
        return self.full_code

    def __repr__(self) -> str:
        return self.__str__()

    @staticmethod
    def is_security_code(s: str) -> bool:
        """判断是否为6位数字证券代码（国内市场是6位，深圳期权是8位，香港市场是5位，期货连续合约最低3位）"""
        # return s.isdigit() and len(s) > 4
        return len(s) > 3

    @staticmethod
    def is_full_code(code: str) -> bool:
        """判断是否为完整代码格式"""
        return '.' in code

    @staticmethod
    def guess_security_type(short_code: str, market: Union[str, MarketType]) -> Optional[SecurityType]:
        """根据证券代码和市场推测交易标的类型

        Returns:
            SecurityType: 推测的交易标的类型

        References:
            pytdx/reader/daily_bar_reader.py: get_security_type(self, fname)
        """
        # 统一转为字符串，避免 MarketType 枚举成员与字符串比较失败
        if isinstance(market, MarketType):
            market = str(market)

        # 先检查是否为期货期权（不带市场后缀）
        if SecurityCode.is_futures_option_code(short_code):
            return SecurityType.FUTURES_OPTION

        # 检查是否为期货合约（不带市场后缀）
        if SecurityCode.is_futures_code(short_code):
            return SecurityType.FUTURES

        head5 = short_code[:5]
        head3 = short_code[:3]
        head2 = short_code[:2]
        len_short_code = len(short_code)

        if market == 'SZO' and  len_short_code == 8 and head5 in ["90005", "90006"]:
            return SecurityType.OPTION  # 深圳期权

        if market == 'HK' and len_short_code == 5:
            return SecurityType.STOCK  # 港股

        if market == 'SZ':
            if head2 in ["00", "30"]:
                return SecurityType.STOCK  # A股
            elif head2 in ["20"]:
                return SecurityType.STOCK_B  # B股
            elif head2 in ["39"]:
                return SecurityType.INDEX  # 指数
            elif head3 in ['501', # 沪市分级基金
                ] or head2 in ["51", "16", "18"]:
                return SecurityType.FUND   # 基金
            elif head2 in ["07", "08",
                           "10", "11", "12", "13", "14", "15", "19",
                           "37", "38",
                           "50", "52", "56"]:
                return SecurityType.BOND   # 债券
            elif head2 in ["99"]:
                return SecurityType.INDEX  # 指数
        elif market == 'SH':
            if head2 in ["60", "68"]:
                return SecurityType.STOCK  # A股科创板
            elif head2 in ["90"]:
                return SecurityType.STOCK_B  # B股
            elif head2 in ["00", "99"]:
                return SecurityType.INDEX  # 指数
            elif head2 in ["88",]:
                return SecurityType.TDX_INDEX  # 通达信指数
            elif head2 in ["51", "52"]: # , "53", "54", "55", "56", "57", "58", "59"
                return SecurityType.FUND   # 基金
            elif head2 in ["00", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19",
                           "20", "23", "24", "27",
                           "50", "53",
                           "78"]:
                return SecurityType.BOND   # 债券
            elif head3 in ["010", "018", "019", "020", "231"]:
                return SecurityType.BOND   # 债券（国债）
            elif head2 in ["55", "71"]:
                return SecurityType.BOND   # 债券
            elif head2 in ["56", "58"]:
                return SecurityType.FUND   # 基金
            elif head2 in ["36", "73", "75", "79"]:
                return SecurityType.OTHER  # 其他
        elif market == 'BJ':
            if head2 in ["92"]:
                return SecurityType.STOCK
            elif head2 in ["89"]:
                return SecurityType.INDEX

        return None


    @staticmethod
    def guest_market(stock_code: str) -> str:
        """推测市场代码"""
        # 市场判断逻辑
        if len(stock_code) == 5:
            return 'HK'  # 港股
        elif len(stock_code) == 8 and stock_code.startswith('9000'):
            return 'SZO'  # 深圳期权
        elif stock_code.startswith('900'):
            return 'SH'  # 上海B股
        elif stock_code.startswith('688'):
            return 'SH'  # 科创板
        elif stock_code.startswith('6'):
            return 'SH'  # 上海主板
        elif stock_code.startswith(('88', '99')):
            return 'SH'  # 上海（通达信）指数
        elif stock_code.startswith('200'):
            return 'SZ'  # 深圳B股
        elif stock_code.startswith('3'):
            return 'SZ'  # 创业板
        elif stock_code.startswith('0'):
            return 'SZ'  # 深圳主板
        elif stock_code.startswith(('8', '4', '920')):
            return 'BJ'  # 北京证券交易所
        elif stock_code.startswith(('501',          # 沪市分级基金
                                    '500', '550',   # 沪市封闭式基金
                                    '51',           # 沪市ETF基金
                                    )):
            return 'SH'
        elif stock_code.startswith(('159',  # 深市ETF基金
                                    '16',   # 深市LOF基金
                                    '18'    # 深市其他基金
                                    )):
            return 'SZ'
        else:
            return None

    @staticmethod
    def guess_full_code(short_code: str, strict_mode: bool = False) -> Optional[str]:
        """
        （股票）短代码转换为完整代码

        Args:
            code: 6位数字的字符串或整数
            strict_mode: 严格模式，如果为True

        Returns:
            str: 完整的股票代码字符串
        """
        if not isinstance(short_code, str):
            raise TypeError(f"代码必须是字符串，short_code={short_code}, 当前类型：{type(short_code)}")

        if "." in short_code:
            return short_code # 已包含 . 就是 full_code

        # 严格模式检查
        if strict_mode:
            if not SecurityCode.is_security_code(short_code):
                raise ValueError(f"无效的股票代码格式: {short_code}")

        market = SecurityCode.guest_market(short_code)
        if market and market != None:
            return f"{short_code}.{market}"

        return None

    def get_type_chinese_name(self) -> str:
        """获取类型名称（中文）"""
        return self._security_type.chinese_name if self._security_type else '未知'

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'short_code': self.short_code,
            'market_code': self.market_code,
            'security_type': self.security_type,
            'full_code': self.full_code,
            'type_name': self.security_type,
        }

    def __str__(self) -> str:
        return self.full_code

    def __repr__(self) -> str:
        return f"SecurityCode(short_code='{self.short_code}', market_code='{self.market_code}', security_type='{self.security_type}')"

    def __eq__(self, other) -> bool:
        if isinstance(other, SecurityCode):
            return self.full_code == other.full_code
        elif isinstance(other, str):
            return self.full_code == other
        return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, SecurityCode):
            return self.full_code < other.full_code
        elif isinstance(other, str):
            return self.full_code < other
        return False

    def __hash__(self):
            """
            重载哈希函数，用于set、dict等哈希集合
            哈希值应该基于那些用于判断相等性的属性
            """
            return hash(self.full_code)

# 测试函数

def run_enum_tests():
    print("=" * 50)
    print("测试 DividendType")
    print("=" * 50)
    print(f"DividendType.UNADJUSTED: {DividendType.UNADJUSTED}")
    print(f"str_value: {DividendType.UNADJUSTED.str_value}")
    print(f"int_value: {DividendType.UNADJUSTED.int_value}")
    print(f"chinese_name: {DividendType.UNADJUSTED.chinese_name}")
    print(f"repr: {repr(DividendType.UNADJUSTED)}")
    print(f"from_str('front'): {DividendType.from_str('front')}")
    print(f"from_int(0): {DividendType.from_int(0)}")
    print(f"chinese_name_2_en('前复权'): {DividendType.chinese_name_2_en('前复权')}")
    print(f"allows(): {DividendType.allows()}")
    print(f"allows_cn(): {DividendType.allows_cn()}")

    print("\n" + "=" * 50)
    print("测试 SecurityType")
    print("=" * 50)
    print(f"SecurityType.STOCK: {SecurityType.STOCK}")
    print(f"str_value: {SecurityType.STOCK.str_value}")
    print(f"int_value: {SecurityType.STOCK.int_value}")
    print(f"chinese_name: {SecurityType.STOCK.chinese_name}")
    print(f"repr: {repr(SecurityType.STOCK)}")
    print(f"from_str('bond'): {SecurityType.from_str('bond')}")
    print(f"from_int(1): {SecurityType.from_int(1)}")
    print(f"chinese_name_2_en('股票'): {SecurityType.chinese_name_2_en('股票')}")
    print(f"allows(): {SecurityType.allows()}")
    print(f"allows_cn(): {SecurityType.allows_cn()}")

    print("\n" + "=" * 50)
    print("测试 MarketType")
    print("=" * 50)
    print(f"MarketType.SH: {MarketType.SH}")
    print(f"str_value: {MarketType.SH.str_value}")
    print(f"int_value: {MarketType.SH.int_value}")
    print(f"chinese_name: {MarketType.SH.chinese_name}")
    print(f"repr: {repr(MarketType.SH)}")
    print(f"from_str('SZ'): {MarketType.from_str('SZ')}")
    print(f"from_int(1): {MarketType.from_int(1)}")
    print(f"chinese_name_2_en('深圳交易所'): {MarketType.chinese_name_2_en('深圳交易所')}")
    print(f"allows(): {MarketType.allows()}")
    print(f"allows_cn(): {MarketType.allows_cn()}")

    # 测试初始化
    print("\n" + "=" * 50)
    print("测试初始化")
    print("=" * 50)
    print(f"MarketType('SH'): {MarketType('SH')}")
    print(f"MarketType(1): {MarketType(1)}")
    print(f"MarketType(MarketType.SZ): {MarketType(MarketType.SZ)}")

    # 测试Python 3.12特定的枚举特性
    print("\n" + "=" * 50)
    print("测试Python 3.12特性")
    print("=" * 50)
    print(f"成员列表: {list(MarketType)}")
    print(f"名称访问: {MarketType['SH']}")
    print(f"值访问: {MarketType('SH')}")


def test_security_code():
    """测试SecurityCode类"""
    test_cases = [
        '000001.SZ',
        '600000',
        '300750',
        '688981',
        '159915',
        '512880',
        '131810',
        '830799.BJ'
    ]

    print("=== SecurityCode 测试 ===")
    for code in test_cases:
        security = SecurityCode(code)
        print(f"输入: {code} -> 完整代码: {security.full_code} 类型: {security.security_type} 市场: {security.market_code}")

        # 显示详细信息
        info = security.to_dict()
        print(f"      详细信息: {info}")


# 使用示例
if __name__ == "__main__":
    from rich.console import Console
    import rich
    CONSOLE = Console()

    try:
        # 运行测试
        # run_enum_tests()

        test_security_code()

        # 单个代码使用示例
        print("\n=== 单个代码使用示例 ===")
        code1 = SecurityCode("000001.SZ")
        code2 = SecurityCode("600000")

        from simple_pytdx.api import Api
        code_from_tdx = SecurityCode('000002', Api.Market.SZ.value)
        print(f"code_from_tdx={code_from_tdx}, to_dict(): {code_from_tdx.to_dict()}")
        print(f"代码1: {code1}, to_dict(): {code1.to_dict()}")
        print(f"代码2: {code2}, to_dict(): {code2.to_dict()}")

    except Exception:
        CONSOLE.print_exception(show_locals=True)

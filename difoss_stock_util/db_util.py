#!python
# encoding: utf-8
# author: DifossChen
#
"""
数据库工具模块 - 提供SQLAlchemy ORM基础类和数据库管理功能
"""

__all__ = [
    'Base',
    'BaseModel',
    'BaseModelWithID',
    'BaseModelHistory',
    'BaseSecurityModel',
    'BaseSecurityModelWithID',

    'DatabaseManager',
    'generate_engine_url',
    'generate_engine_url_str',
    'safe_repr_url',
    'get_local_stocks',
]

import re
import atexit
from datetime import datetime
from threading import Lock
from contextlib import contextmanager
from typing import (
    Optional, ClassVar, Union, List, Iterable,
    Generator, Dict, Any, Type, TypeVar, cast
)
from functools import lru_cache

from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime,
    inspect, Index, func, text, Engine
)
from sqlalchemy.engine import URL as EngineUrl
from sqlalchemy.orm import (
    sessionmaker, Session, declarative_base,
    declared_attr, Query
)
from sqlalchemy.exc import SQLAlchemyError

from .color_log_util import I, D, W, E
from .security_util import SecurityCode


# 类型变量
TSecurityModel = TypeVar('TSecurityModel', bound='BaseSecurityModel')
TSecurityModelWithID = TypeVar('TSecurityModelWithID', bound='BaseSecurityModelWithID')

# 常量
ALL_MARKET_LIST = ['SH', 'SZ', 'BJ']


# -----------------------------------------------------------------------------
# 工具函数
# -----------------------------------------------------------------------------
def _dict_equal(d1: Dict[str, Any], d2: Dict[str, Any], ignore_keys: Optional[List[str]] = None) -> bool:
    """
    比较两个字典是否相等（忽略指定键）

    Args:
        d1: 第一个字典
        d2: 第二个字典
        ignore_keys: 要忽略的键列表

    Returns:
        是否相等
    """
    ignore_set = set(ignore_keys) if ignore_keys else set()

    for key in d1.keys():
        if key in ignore_set:
            continue
        if d1.get(key) != d2.get(key):
            return False
    return True


def _snake_case(name: str) -> str:
    """
    将驼峰命名转换为蛇形命名

    Args:
        name: 驼峰命名字符串

    Returns:
        蛇形命名字符串
    """
    # BaseModel -> base_model
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def generate_engine_url(
    drivername: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    **kwargs,
) -> EngineUrl:
    """生成SQLAlchemy引擎URL对象"""
    return EngineUrl.create(
        drivername=drivername,
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
        **kwargs
    )


def generate_engine_url_str(
    drivername: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    hide_password: bool = False,
    **kwargs,
) -> str:
    """生成SQLAlchemy引擎URL字符串"""
    url = generate_engine_url(
        drivername=drivername,
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
        **kwargs
    )
    return url.render_as_string(hide_password)


def safe_repr_url(url: str) -> str:
    """
    安全地显示数据库URL（隐藏密码）

    Args:
        url: 原始数据库URL

    Returns:
        隐藏密码后的URL
    """
    for i, char in enumerate(url):
        if char == ':' and i + 1 < len(url) and url[i + 1] != '/':
            return url[:i] + ':***'
    return url


def get_local_stocks(market: str, model_class: Type[TSecurityModel]) -> List[SecurityCode]:
    """
    获取本地数据库中指定市场的所有股票列表

    Args:
        market: 市场代码
        model_class: 证券模型类

    Returns:
        股票代码对象列表
    """
    records = model_class.get_all_latest_by_market(market)
    if records:
        return [SecurityCode(record.InstrumentID, record.ExchangeID) for record in records]
    return []


# -----------------------------------------------------------------------------
# 数据库管理器
# -----------------------------------------------------------------------------
class DatabaseManager:
    """
    多数据库管理器 - 支持多数据库连接

    职责：
    1. 管理多个数据库连接（按db_url区分）
    2. 提供线程安全的Session管理
    3. 支持不同的Base类绑定到不同的数据库

    使用示例：
        # 获取管理器实例
        db_manager = DatabaseManager.get_instance("postgresql://user:pass@localhost/db")

        # 使用会话上下文
        with db_manager.session_context() as session:
            results = session.query(User).all()

        # 或直接获取会话
        session = db_manager.get_session()
        try:
            results = session.query(User).all()
        finally:
            session.close()
    """

    _instances: Dict[str, 'DatabaseManager'] = {}
    _lock: Lock = Lock()

    def __new__(cls, db_url: str) -> 'DatabaseManager':
        """单例模式：确保每个db_url只有一个实例"""
        with cls._lock:
            if db_url not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[db_url] = instance
            return cls._instances[db_url]

    def __init__(self, db_url: str):
        """
        初始化数据库管理器

        Args:
            db_url: 数据库连接URL
        """
        # 避免重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.db_url = db_url

        # 创建数据库引擎
        self._engine = create_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
        )

        # 创建Session工厂
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

        self._initialized = True
        atexit.register(self.cleanup)

        I(f"数据库引擎初始化完成: {safe_repr_url(db_url)}")

    @classmethod
    def get_instance(cls, db_url: Optional[str] = None) -> 'DatabaseManager':
        """
        获取数据库管理器实例

        Args:
            db_url: 数据库连接URL，默认使用SQLite内存数据库

        Returns:
            DatabaseManager实例
        """
        if db_url is None:
            db_url = "sqlite:///:memory:"
            W("使用SQLite内存数据库进行调试")

        return cls(db_url)

    @classmethod
    def get_session(cls, db_url: Optional[str] = None) -> Session:
        """
        快速获取数据库Session

        Args:
            db_url: 数据库连接URL

        Returns:
            Session对象
        """
        return cls.get_instance(db_url)._session_factory()

    @contextmanager
    def session_context(self, commit: bool = False) -> Generator[Session, None, None]:
        """
        会话上下文管理器，自动处理Session的生命周期

        Args:
            commit: 是否在正常退出时自动提交

        Yields:
            Session对象

        Example:
            with db_manager.session_context(commit=True) as session:
                session.add(user)
        """
        session = self._session_factory()
        try:
            yield session
            if commit:
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def cleanup(self) -> None:
        """清理当前数据库引擎"""
        try:
            if hasattr(self, '_engine'):
                self._engine.dispose()
                I(f"数据库引擎已清理: {safe_repr_url(self.db_url)}")
        except Exception as e:
            W(f"清理数据库引擎时出错 ({safe_repr_url(self.db_url)}): {e}")

    @classmethod
    def cleanup_all(cls) -> None:
        """清理所有数据库引擎"""
        with cls._lock:
            for instance in cls._instances.values():
                instance.cleanup()
            cls._instances.clear()

    @property
    def engine(self) -> Engine:
        """获取数据库引擎"""
        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        """获取Session工厂"""
        return self._session_factory


# -----------------------------------------------------------------------------
# 基础模型类
# -----------------------------------------------------------------------------
Base = declarative_base()


class BaseModel(Base):
    """基础模型抽象类 - 提供通用方法和属性"""

    __abstract__ = True

    # 调试标志
    _debug: ClassVar[bool] = False
    # 数据库URL
    _db_url: ClassVar[Optional[str]] = None

    @declared_attr
    def __tablename__(cls) -> str:
        """自动生成表名：将类名转换为蛇形命名"""
        return _snake_case(cls.__name__)

    def __init__(self, **kwargs):
        """初始化模型实例"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def __repr__(self) -> str:
        """通用字符串表示"""
        dict_str = self.to_dict(str_long_limit=50, stringify_dict_value=True)
        columns_info = [f"{k}={v}" for k, v in dict_str.items()]
        return f"<{self.__class__.__name__}>({', '.join(columns_info)})"

    def to_dict(
        self,
        with_comment: bool = False,
        str_long_limit: int = 50,
        exclude_keys: Optional[List[str]] = None,
        stringify_dict_value: bool = False
    ) -> Dict[str, Any]:
        """
        将模型转换为字典

        Args:
            with_comment: 是否在键名中包含字段注释
            str_long_limit: 字符串截断长度
            exclude_keys: 要排除的键列表
            stringify_dict_value: 是否将字典值转换为字符串

        Returns:
            字段字典
        """
        result = {}
        exclude_set = set(exclude_keys) if exclude_keys else set()

        for column in self.__table__.columns:
            field_name = column.name

            if field_name in exclude_set:
                continue

            # 处理键名
            if with_comment and column.comment:
                key = f"{field_name}({column.comment})"
            else:
                key = field_name

            # 获取值
            value = getattr(self, field_name, None)

            # 处理长字符串
            if value is not None and str_long_limit:
                if isinstance(value, str) or (stringify_dict_value and isinstance(value, dict)):
                    value_str = str(value)
                    if len(value_str) > str_long_limit:
                        value_str = value_str[:str_long_limit - 3] + "..."
                    value = value_str

            result[key] = value

        return result

    # -------------------------------------------------------------------------
    # 数据库连接管理
    # -------------------------------------------------------------------------
    @classmethod
    def init_db(cls, db_url: str, echo: bool = False, debug: bool = False) -> None:
        """
        初始化数据库连接

        Args:
            db_url: 数据库连接URL
            echo: 是否打印SQL语句
            debug: 是否开启调试模式
        """
        if cls._db_url:
            return  # 可重入考虑

        cls._db_url = db_url
        cls._debug = debug

        # 创建所有表
        Base.metadata.create_all(cls.get_engine())
        print(f"数据库初始化完成: {safe_repr_url(db_url)}")
        
    @property
    def is_inited(self) -> bool:
        """检查数据库是否已初始化"""
        return self._db_url is not None
        
    @property
    def debug(self) -> bool:
        return self._debug

    @classmethod
    def get_engine(cls) -> Engine:
        """获取数据库引擎"""
        if not cls._db_url:
            raise RuntimeError("数据库未初始化，请先调用 init_db 方法")
        return DatabaseManager.get_instance(cls._db_url).engine

    @classmethod
    def get_session(
        cls,
        commit: Optional[bool] = False
    ) -> Union[Session, Generator[Session, None, None]]:
        """
        获取数据库会话

        Args:
            commit:
                - False (默认): 返回上下文管理器，不会自动提交
                - True: 返回上下文管理器，会自动提交
                - None: 返回原始Session对象，需要手动关闭

        Returns:
            会话对象或上下文管理器
        """
        if not cls._db_url:
            raise RuntimeError("数据库未初始化，请先调用 init_db 方法")

        if commit is None:
            return DatabaseManager.get_session(cls._db_url)
        else:
            return DatabaseManager.get_instance(cls._db_url).session_context(commit)

    @classmethod
    def _get_session_context(cls, commit: bool = False) -> Generator[Session, None, None]:
        """获取会话上下文管理器（内部使用）"""
        with cls.get_session(commit) as session:  # type: ignore
            yield session

    # -------------------------------------------------------------------------
    # 查询工具
    # -------------------------------------------------------------------------
    @classmethod
    def print_query_sql(cls, query: Query) -> str:
        """
        打印查询的SQL语句

        Args:
            query: SQLAlchemy查询对象

        Returns:
            SQL语句字符串
        """
        compiled = query.statement.compile(
            dialect=cls.get_engine().dialect,
            compile_kwargs={"literal_binds": True}
        )
        sql_str = str(compiled)

        print("=" * 50)
        print(sql_str)
        print("=" * 50)

        return sql_str

    # -------------------------------------------------------------------------
    # CRUD 操作
    # -------------------------------------------------------------------------
    @classmethod
    def create(cls, **kwargs) -> 'BaseModel':
        """
        创建新记录

        Args:
            **kwargs: 字段值

        Returns:
            创建的实例
        """
        with cls.get_session(True) as session:  # type: ignore
            instance = cls(**kwargs)
            session.add(instance)
            session.flush()  # 获取ID但不提交
            session.refresh(instance)
            return instance

    def update(self, **kwargs) -> 'BaseModel':
        """
        更新记录

        Args:
            **kwargs: 要更新的字段

        Returns:
            更新后的实例
        """
        with self.get_session(True) as session:  # type: ignore
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            session.flush()
            session.refresh(self)
            return self

    def delete(self) -> None:
        """删除记录"""
        with self.get_session(True) as session:  # type: ignore
            session.delete(self)

    @classmethod
    def batch_insert(cls, data_list: List[Dict[str, Any]]) -> None:
        """
        批量插入数据

        Args:
            data_list: 数据字典列表

        Raises:
            TypeError: 数据格式错误
        """
        if not data_list:
            return

        if not isinstance(data_list[0], dict):
            raise TypeError("data_list 必须是字典列表")

        with cls.get_session(True) as session:  # type: ignore
            session.bulk_insert_mappings(cls, data_list)


class BaseModelWithID(BaseModel):
    """带ID主键的基础模型"""

    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')

    @classmethod
    def get_by_id(cls, record_id: int) -> Optional['BaseModelWithID']:
        """
        根据ID获取记录

        Args:
            record_id: 记录ID

        Returns:
            记录实例或None
        """
        with cls.get_session() as session:  # type: ignore
            return session.query(cls).filter(cls.id == record_id).first()


class BaseModelHistory(BaseModel):
    """带时间戳的历史记录模型"""

    __abstract__ = True

    created_at = Column(DateTime, default=datetime.now, comment='创建时间', index=True)
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment='更新时间',
        index=True
    )

    @classmethod
    def get_all(cls, limit: Optional[int] = None) -> List['BaseModelHistory']:
        """
        获取所有记录

        Args:
            limit: 限制返回数量

        Returns:
            记录列表
        """
        with cls.get_session() as session:  # type: ignore
            query = session.query(cls).order_by(cls.created_at.asc())
            if limit:
                query = query.limit(limit)
            return query.all()

    @classmethod
    def get_latest_updated_time(cls) -> Optional[datetime]:
        """
        获取最近更新时间

        Returns:
            最近更新时间或None
        """
        with cls.get_session() as session:  # type: ignore
            latest = session.query(cls).order_by(cls.updated_at.desc()).first()
            return latest.updated_at if latest else None


# -----------------------------------------------------------------------------
# 证券相关模型
# -----------------------------------------------------------------------------
class BaseSecurityModel(BaseModelHistory):
    """证券产品基础模型（无ID）"""

    __abstract__ = True

    ExchangeID = Column(String(10), nullable=False, comment='合约市场代码')
    InstrumentID = Column(String(10), nullable=False, comment='市场代码')

    # 忽略比较的字段
    _ignore_columns: ClassVar[Iterable[str]] = ('updated_at', 'created_at')

    @declared_attr
    def __table_args__(cls):
        """表参数：定义索引"""
        table_name = _snake_case(cls.__name__)
        return (
            Index(f'idx_{table_name}_instrument', 'InstrumentID'),
            Index(f'idx_{table_name}_exchange', 'ExchangeID'),
            Index(f'idx_{table_name}_instrument_updated', 'InstrumentID', 'updated_at'),
            Index(f'idx_{table_name}_full_code', 'InstrumentID', 'ExchangeID'),
            Index(f'idx_{table_name}_full_code_updated', 'InstrumentID', 'ExchangeID', 'updated_at'),
        )

    @classmethod
    @lru_cache(maxsize=1)
    def _get_column_names(cls) -> List[str]:
        """获取所有列名（缓存）"""
        return [column.name for column in inspect(cls).columns]

    def __eq__(self, other) -> bool:
        """比较两个记录是否相等（忽略指定字段）"""
        if not isinstance(other, self.__class__):
            return False

        column_names = self._get_column_names()

        for col in column_names:
            if col in self._ignore_columns:
                continue
            if getattr(self, col) != getattr(other, col):
                return False

        return True

    def __hash__(self) -> int:
        """哈希值"""
        return hash(tuple(getattr(self, col) for col in self._get_column_names()))

    # -------------------------------------------------------------------------
    # 查询方法
    # -------------------------------------------------------------------------
    @classmethod
    def _get_latest_by_code(
        cls,
        session: Session,
        code: SecurityCode,
        when: Optional[datetime] = None
    ) -> Optional[TSecurityModel]:
        """
        获取指定代码的最新记录（内部方法）

        Args:
            session: 数据库会话
            code: 证券代码对象
            when: 时间限制

        Returns:
            最新记录或None
        """
        query = session.query(cls).filter(
            cls.InstrumentID == code.short_code,
            cls.ExchangeID == code.market_code
        )

        if when:
            query = query.filter(cls.created_at <= when)

        return query.order_by(cls.updated_at.desc()).first()

    @classmethod
    def get_latest_by_code(
        cls,
        code: SecurityCode,
        when: Optional[datetime] = None
    ) -> Optional[TSecurityModel]:
        """
        获取指定代码的最新记录

        Args:
            code: 证券代码对象
            when: 时间限制

        Returns:
            最新记录或None
        """
        with cls.get_session() as session:  # type: ignore
            return cls._get_latest_by_code(session, code, when)

    @classmethod
    def get_latest_by_code_afap(
        cls,
        code: SecurityCode,
        when: Optional[datetime] = None
    ) -> Optional[TSecurityModel]:
        """
        尽可能获取记录（如果指定时间没有，则获取最新）

        Args:
            code: 证券代码对象
            when: 首选时间点

        Returns:
            记录或None
        """
        with cls.get_session() as session:  # type: ignore
            record = cls._get_latest_by_code(session, code, when)
            if record:
                return record
            return cls._get_latest_by_code(session, code)

    @classmethod
    def get_all_by_code(
        cls,
        code: SecurityCode,
        when: Optional[datetime] = None
    ) -> List[TSecurityModel]:
        """
        获取指定代码的所有历史记录

        Args:
            code: 证券代码对象
            when: 时间限制

        Returns:
            记录列表
        """
        with cls.get_session() as session:  # type: ignore
            query = session.query(cls).filter(
                cls.InstrumentID == code.short_code,
                cls.ExchangeID == code.market_code
            )

            if when:
                query = query.filter(cls.created_at <= when)

            return query.order_by(cls.created_at.asc()).all()

    @classmethod
    def get_latest(
        cls,
        when: Optional[datetime] = None
    ) -> List[TSecurityModel]:
        """
        获取每只个股的最新记录

        Args:
            when: 时间限制

        Returns:
            最新记录列表
        """
        with cls.get_session() as session:  # type: ignore
            # 子查询：获取每只个股的最新创建时间
            subquery = (
                session.query(
                    cls.InstrumentID,
                    cls.ExchangeID,
                    func.max(cls.created_at).label('max_created_at')
                )
                .filter(cls.created_at <= when if when else True)
                .group_by(cls.InstrumentID, cls.ExchangeID)
                .subquery()
            )

            # 主查询：获取完整记录
            return (
                session.query(cls)
                .join(
                    subquery,
                    (cls.InstrumentID == subquery.c.InstrumentID) &
                    (cls.ExchangeID == subquery.c.ExchangeID) &
                    (cls.created_at == subquery.c.max_created_at)
                )
                .order_by(cls.ExchangeID, cls.InstrumentID)
                .all()
            )

    @classmethod
    def get_all_by_market(
        cls,
        market_code: str,
        when: Optional[datetime] = None
    ) -> List[TSecurityModel]:
        """
        获取指定市场的所有记录

        Args:
            market_code: 市场代码
            when: 时间限制

        Returns:
            记录列表
        """
        market_code = market_code.upper()

        with cls.get_session() as session:  # type: ignore
            query = session.query(cls).filter(cls.ExchangeID == market_code)

            if when:
                query = query.filter(cls.created_at <= when)

            return query.order_by(cls.created_at.asc()).all()

    @classmethod
    def get_all_latest_by_market(
        cls,
        market_code: str,
        when: Optional[datetime] = None
    ) -> List[TSecurityModel]:
        """
        获取指定市场的最新记录（每只个股一条）

        Args:
            market_code: 市场代码
            when: 时间限制

        Returns:
            最新记录列表
        """
        market_code = market_code.upper()

        with cls.get_session() as session:  # type: ignore
            # 子查询：获取每只个股的最新创建时间
            subquery = (
                session.query(
                    cls.InstrumentID,
                    func.max(cls.created_at).label('max_created_at')
                )
                .filter(
                    cls.ExchangeID == market_code,
                    cls.created_at <= when if when else True
                )
                .group_by(cls.InstrumentID)
                .subquery()
            )

            # 主查询：获取完整记录
            return (
                session.query(cls)
                .join(
                    subquery,
                    (cls.InstrumentID == subquery.c.InstrumentID) &
                    (cls.created_at == subquery.c.max_created_at)
                )
                .order_by(cls.InstrumentID)
                .all()
            )

    @classmethod
    def get_markets_list(cls, when: Optional[datetime] = None) -> List[str]:
        """
        获取所有有数据的市场列表

        Args:
            when: 时间限制

        Returns:
            市场代码列表
        """
        with cls.get_session() as session:  # type: ignore
            query = session.query(cls.ExchangeID).distinct()

            if when:
                # 获取在指定时间前有数据的市场
                subquery = (
                    session.query(
                        cls.InstrumentID,
                        cls.ExchangeID,
                        func.max(cls.updated_at).label('max_updated_at')
                    )
                    .filter(cls.updated_at <= when)
                    .group_by(cls.InstrumentID, cls.ExchangeID)
                    .subquery()
                )

                query = (
                    session.query(subquery.c.ExchangeID)
                    .distinct()
                )

            return [row[0] for row in query.order_by(cls.ExchangeID).all()]

    @classmethod
    def get_all_created_later(
        cls,
        when: datetime,
        order_by: str = "created_at",
        order_asc: bool = True,
        limit: Optional[int] = None
    ) -> List[TSecurityModel]:
        """
        获取指定时间后创建的所有记录

        Args:
            when: 目标时间点
            order_by: 排序字段
            order_asc: 是否升序
            limit: 限制数量

        Returns:
            记录列表
        """
        with cls.get_session() as session:  # type: ignore
            query = session.query(cls).filter(cls.created_at > when)

            # 排序
            order_field = getattr(cls, order_by, cls.created_at)
            query = query.order_by(order_field.asc() if order_asc else order_field.desc())

            if limit:
                query = query.limit(limit)

            return query.all()

    # -------------------------------------------------------------------------
    # 数据操作
    # -------------------------------------------------------------------------
    @classmethod
    def upsert(
        cls,
        new_dict: Dict[str, Any],
        only_check: bool = False
    ) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        插入或更新数据

        Args:
            new_dict: 新数据字典
            only_check: 仅检查不实际执行

        Returns:
            (操作类型, 旧数据字典)
            操作类型: 'new', 'insert', 'update', None
        """
        if not new_dict:
            return None, None

        # 确保有时间戳
        if new_dict.get('updated_at') is None:
            new_dict['updated_at'] = datetime.now()

        code = SecurityCode(
            new_dict['InstrumentID'],
            new_dict.get('ExchangeID')
        )

        with cls.get_session() as session:  # type: ignore
            # 获取最新记录
            latest = cls._get_latest_by_code(session, code, new_dict['updated_at'])
            latest_dict = latest.to_dict(stringify_dict_value=False) if latest else None

            # 如果没有旧记录
            if not latest_dict:
                if cls._debug:
                    I("首次插入记录", new_record=new_dict)

                if not only_check:
                    obj = cls(**new_dict)
                    session.add(obj)
                    session.commit()

                return 'new', None

            # 检查时间戳
            if latest_dict['updated_at'] >= new_dict['updated_at']:
                if cls._debug:
                    T("数据库记录更新，无需操作", new=new_dict['updated_at'], old=latest_dict['updated_at'])
                return None, latest_dict

            # 检查数据是否相同
            if _dict_equal(
                latest_dict,
                new_dict,
                ignore_keys=['id', 'created_at', 'updated_at']
            ):
                if cls._debug:
                    I("仅更新时间戳")

                if not only_check:
                    latest.updated_at = new_dict['updated_at']
                    session.commit()

                return 'update', latest_dict

            # 数据不同，插入新记录
            if cls._debug:
                I("数据变化，插入新记录")

            if not only_check:
                obj = cls(**new_dict)
                session.add(obj)
                session.commit()

            return 'insert', latest_dict

    @classmethod
    def delete_by_code(cls, code: SecurityCode) -> int:
        """
        删除指定代码的所有记录

        Args:
            code: 证券代码对象

        Returns:
            删除的记录数
        """
        with cls.get_session() as session:  # type: ignore
            result = session.query(cls).filter(
                cls.InstrumentID == code.short_code,
                cls.ExchangeID == code.market_code
            ).delete()
            session.commit()
            return result


class BaseSecurityModelWithID(BaseSecurityModel, BaseModelWithID):
    """带ID的证券产品模型"""

    __abstract__ = True

    # 忽略比较的字段（包含ID）
    _ignore_columns: ClassVar[Iterable[str]] = ('id', 'updated_at', 'created_at')
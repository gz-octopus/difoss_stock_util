#!python
# encoding: utf-8
# author: DifossChen
#

"""扫雷宝相关数据结构定义
"""

__all__ = [
    'SLBDetail',
]

from difoss_stock_util.security_util import *
from difoss_stock_util.color_log_util import *
from difoss_stock_util.db_util import *
from difoss_stock_util.util import trace_func

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Index, func
from sqlalchemy.orm import declared_attr, Session
from sqlalchemy.dialects.sqlite import JSON
from typing import Optional, List, Tuple, TypeVar, Any, Generic
from dictdiffer import diff
import matplotlib.pyplot as plt
import numpy as np
from typing import List, Dict, Optional, Union, Iterable

_T = TypeVar('_T', bound='SLBDetail', covariant=True)

class SLBDetail(BaseSecurityModelWithID):

    # 由于 SLB（扫雷宝）是三字缩写，不想按照 BaseModelOperation 默认的转换表名规则（l_s_b_detail），
    # 故重新定义该属性
    @declared_attr
    def __tablename__(cls):
        return 'slb_detail'

    # 基础字段
    name = Column(String(100), nullable=False, index=True)
    total_risk_score = Column(Integer, default=0)
    risk_count = Column(Integer, default=0)
    risk_data = Column(JSON)

    @declared_attr
    @classmethod
    def __ignore_columns__(cls) -> Iterable[str]:
        return ('id', 'updated_at', 'created_at', 'name')


    def __lt__(self, other) -> bool:
        if isinstance(other, int):
            return self.total_risk_score < other

        if not isinstance(other, __class__):
            raise Exception("不同类型无法对比")

        return self.total_risk_score < other.total_risk_score \
            or (self.total_risk_score == other.total_risk_score and self.risk_count < other.risk_count)

    @staticmethod
    def has_more_risk(old: dict, new: dict):
        old_trs = old.get('total_risk_score', 0)
        new_trs = new.get('total_risk_score', 0)
        old_rc = old.get('risk_count', 0)
        new_rc = new.get('risk_count', 0)
        return old_trs < new_trs or (old_trs == new_trs and old_rc < new_rc)

    @staticmethod
    def show_differences(old: dict, new: dict, excludes=['risk_data']) -> Tuple[Optional[bool], Optional[List[str]]]:
        """对比两条扫雷宝数据的差异
        Returns:
            Tuple[Optional[bool], Optional[List[str]]]: 返回风险是否提高、差异列表
        """
        if not new:
            raise Exception("新数据不能为空")
        if not old:
            I("插入新数据", code=new['InstrumentID'], name=new['name'], _level="NEW")
            return None, None
        
        if not excludes:
            excludes = [] # 提高健壮性

        # 检查数据是否相同
        differences = list(diff(old, new, ignore=SLBDetail.__ignore_columns__))

        if differences:
            # 数据不同，插入新记录
            old_trs = old.get('total_risk_score', 0)
            new_trs = new.get('total_risk_score', 0)
            old_rc = old.get('risk_count', 0)
            new_rc = new.get('risk_count', 0)

            more_risk = SLBDetail.has_more_risk(old, new)
            diff_details = []
            
            for (change_type, path, values) in differences:
                # DEBUG:
                # I(path=path, type=type(path), excludes=excludes, is_contain=path in excludes)
                if excludes:
                    if isinstance(path, list):
                        if path[0] in excludes:
                            continue
                    elif isinstance(path, str):
                        if path in excludes:
                            continue

                diff_details.append(f"{change_type}: {path} -> {values}")
                
            if old_trs == new_trs and old_rc == new_rc:
                I("风险不变，risk_data 数据改变", _level='DATA CHANGE', instrument_id=new['InstrumentID'])
                # DEBUG:
                # D(differences=differences)
                # exit(1)
                return None, diff_details
            elif diff_details:
                I("⬆ 风险提高" if more_risk else "⬇ 风险降低", code=new['InstrumentID'], name=new['name'],
                risk_score=f"{old_trs} -> {new_trs}",
                risk_count=f"{old_rc} -> {new_rc}",
                具体差异=diff_details,
                _indent=2,
                _color='bright_red' if more_risk else 'bright_green',
                _level='BAD' if more_risk else 'GOOD')

            return more_risk, diff_details

        return None, None


    # CRUD 操作方法
    @classmethod
    def get_latest_with_score_range(cls, score_range: Tuple[int], when: datetime = None) -> Optional[List[_T]]:

        with cls.get_session() as session:
            if when is None:
                when = datetime.now()

            if len(score_range) != 2:
                raise ValueError("score_range 必须是 (min_score, max_score) 格式")

            min_score, max_score = score_range

            criterion = []
            if when:
                criterion.append(cls.created_at <= when)

            # 子查询：获取每只个股在 dt 之前创建的最新记录
            subquery = (
                session.query(
                    cls.InstrumentID,
                    cls.ExchangeID,
                    func.max(cls.created_at).label('max_created_at')
                )
                .filter(*criterion)
                .group_by(cls.InstrumentID, cls.ExchangeID)
                .subquery()
            )

            # 主查询：获取这些最新记录的完整信息
            records = (
                session.query(cls)
                .join(
                    subquery,
                    (cls.InstrumentID == subquery.c.InstrumentID) &
                    (cls.ExchangeID == subquery.c.ExchangeID) &
                    (cls.created_at == subquery.c.max_created_at)
                )
                .filter(
                    cls.total_risk_score >= min_score,
                    cls.total_risk_score <= max_score,
                )
                .order_by(cls.total_risk_score.asc(), cls.ExchangeID, cls.InstrumentID)
                .all()
            )

            return records


    # 辅助方法
    @classmethod
    def _calculate_total_score(cls, json_data):
        """计算总风险分数"""
        total_score = 0
        for category in json_data['data']:
            for risk_item in category['rows']:
                total_score += risk_item.get('fs', 0)
        return total_score

    @classmethod
    def _compare_json_data(cls, data1, data2):
        """比较两个 JSON 数据是否相同（简化比较）"""
        try:
            # 比较关键字段
            return (data1.get('name') == data2.get('name') and
                    data1.get('num') == data2.get('num') and
                    data1.get('total') == data2.get('total'))
        except:
            return False


    # 实例方法
    def display_info(self):
        """显示记录信息"""
        created_str = self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        updated_str = self.updated_at.strftime('%Y-%m-%d %H:%M:%S')

        print(f"ID: {self.id}, 合约: {self.InstrumentID}, 市场: {self.ExchangeID} 名称: {self.name}")
        print(f"创建: {created_str}, 更新: {updated_str}")
        print(f"分数: {self.total_risk_score}, 风险数量: {self.risk_count}")

    def is_valid_at(self, when):
        """检查记录在指定时间点是否有效"""
        return self.created_at <= when and (self.updated_at >= when or self.updated_at is None)


    @classmethod
    def plot_score_distribution(cls, score_range: tuple = (0, 100), when: datetime = None, save_path: str = None):

        """绘制风险分数分布的柱状图

        Args:
            score_range: 风险分数范围 (min_score, max_score)
            dt: 目标时间点，如果为None则使用当前时间
            save_path: 图片保存路径，如果为None则显示图片
        """
        # 获取数据
        records = cls.get_latest_with_score_range(score_range, when)

        if not records:
            print("没有找到数据，无法绘制图表")
            return

        exchange_stats = {}
        for record in records:
            exchange = record.ExchangeID
            exchange_stats[exchange] = exchange_stats.get(exchange, 0) + 1

        print("各市场个股数量统计:")
        for exchange, count in exchange_stats.items():
            print(f"  - {exchange}: {count} 只个股")


        scores = [record.total_risk_score for record in records if record.total_risk_score is not None]

        if not scores:
            print("没有有效的分数数据")
            return

        # 设置中文字体（解决中文显示问题）
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # 创建图表
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        # 子图1：分数分布直方图
        min_score = min(scores)
        max_score = max(scores)

        # 自动确定分箱数量
        bin_range = max_score - min_score + 1
        bins = min(20, bin_range)  # 最多20个分箱

        ax1.hist(scores, bins=bins, alpha=0.7, color='skyblue', edgecolor='black')
        ax1.set_xlabel('风险分数')
        ax1.set_ylabel('个股数量')
        ax1.set_title(f'风险分数分布\n({dt.strftime("%Y-%m-%d %H:%M")})')
        ax1.grid(True, alpha=0.3)

        # 添加统计信息
        stats_text = f'总个股数: {len(scores)}\n平均分数: {np.mean(scores):.2f}\n标准差: {np.std(scores):.2f}'
        ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        # 子图2：市场分布饼图
        market_stats = exchange_stats
        if market_stats:
            market_labels = list(market_stats.keys())
            market_sizes = list(market_stats.values())

            # 为饼图添加颜色
            colors = plt.cm.Set3(np.linspace(0, 1, len(market_labels)))

            ax2.pie(market_sizes, labels=market_labels, autopct='%1.1f%%',
                    colors=colors, startangle=90)
            ax2.set_title('各市场个股分布')

        plt.tight_layout()

        # 保存或显示图片
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图表已保存到: {save_path}")
        else:
            plt.show()

        plt.close()

    @classmethod
    def plot_detailed_score_analysis(cls, when: datetime = None, session=None, save_path: str = None):
        """绘制详细的风险分数分析图表

        Args:
            when: 目标时间点
            session: 数据库会话
            save_path: 图片保存路径
        """
        # 获取所有数据
        records = cls.get_latest_with_score_range((0, 100), when)

        if not records:
            print("没有找到数据，无法绘制图表")
            return

        scores = [record.total_risk_score for record in records if record.total_risk_score is not None]

        if not scores:
            print("没有有效的分数数据")
            return

        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # 创建多个子图
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

        # 子图1：分数分布直方图（带密度曲线）
        n, bins, patches = ax1.hist(scores, bins=20, alpha=0.7, color='lightblue',
                                    edgecolor='black', density=True)

        # 添加密度曲线
        from scipy.stats import gaussian_kde
        if len(scores) > 1:
            kde = gaussian_kde(scores)
            x_range = np.linspace(min(scores), max(scores), 100)
            ax1.plot(x_range, kde(x_range), 'r-', linewidth=2, label='密度曲线')

        ax1.set_xlabel('风险分数')
        ax1.set_ylabel('密度')
        ax1.set_title('风险分数分布（带密度曲线）')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 子图2：箱线图
        ax2.boxplot(scores, vert=True, patch_artist=True,
                    boxprops=dict(facecolor='lightgreen', color='black'),
                    medianprops=dict(color='red', linewidth=2))
        ax2.set_ylabel('风险分数')
        ax2.set_title('风险分数箱线图')
        ax2.grid(True, alpha=0.3)

        # 添加统计信息到箱线图
        stats_text = (f'中位数: {np.median(scores):.1f}\n'
                    f'Q1: {np.percentile(scores, 25):.1f}\n'
                    f'Q3: {np.percentile(scores, 75):.1f}\n'
                    f'IQR: {np.percentile(scores, 75) - np.percentile(scores, 25):.1f}')
        ax2.text(0.02, 0.98, stats_text, transform=ax2.transAxes, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        # 子图3：风险等级分布
        risk_levels = ['低风险(0-9)', '中风险(10-19)', '中高风险(20-29)', '高风险(30+)']
        low_risk = len([s for s in scores if 0 <= s < 10])
        medium_risk = len([s for s in scores if 10 <= s < 20])
        medium_high_risk = len([s for s in scores if 20 <= s < 30])
        high_risk = len([s for s in scores if s >= 30])

        risk_counts = [low_risk, medium_risk, medium_high_risk, high_risk]
        colors = ['green', 'yellow', 'orange', 'red']

        bars = ax3.bar(risk_levels, risk_counts, color=colors, alpha=0.7, edgecolor='black')
        ax3.set_xlabel('风险等级')
        ax3.set_ylabel('个股数量')
        ax3.set_title('风险等级分布')

        # 在柱子上添加数量标签
        for bar, count in zip(bars, risk_counts):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{count}', ha='center', va='bottom')

        # 子图4：各市场平均分数比较
        market_stats = {}
        for record in records:
            if record.ExchangeID and record.total_risk_score is not None:
                if record.ExchangeID not in market_stats:
                    market_stats[record.ExchangeID] = []
                market_stats[record.ExchangeID].append(record.total_risk_score)

        if market_stats:
            market_names = list(market_stats.keys())
            market_means = [np.mean(scores) for scores in market_stats.values()]
            market_stds = [np.std(scores) for scores in market_stats.values()]

            bars = ax4.bar(market_names, market_means, yerr=market_stds,
                        capsize=5, alpha=0.7, color='lightcoral', edgecolor='black')
            ax4.set_xlabel('市场')
            ax4.set_ylabel('平均风险分数')
            ax4.set_title('各市场平均风险分数比较')

            # 在柱子上添加平均值标签
            for bar, mean in zip(bars, market_means):
                height = bar.get_height()
                ax4.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{mean:.1f}', ha='center', va='bottom')

        plt.tight_layout()

        # 保存或显示图片
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"详细分析图表已保存到: {save_path}")
        else:
            plt.show()

        plt.close()

    @classmethod
    def plot_score_trend(cls, time_points: List[datetime], score_range: tuple = (0, 100),
                        session=None, save_path: str = None):
        """绘制多个时间点的分数趋势图

        Args:
            time_points: 时间点列表
            score_range: 分数范围
            save_path: 图片保存路径
        """
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # 收集数据
        time_labels = []
        avg_scores = []
        stock_counts = []

        for dt in time_points:
            records = cls.get_latest_with_score_range(score_range, dt)
            if records:
                scores = [record.total_risk_score for record in records
                        if record.total_risk_score is not None]
                if scores:
                    time_labels.append(dt.strftime("%m-%d %H:%M"))
                    avg_scores.append(np.mean(scores))
                    stock_counts.append(len(scores))

        if len(avg_scores) < 2:
            print("时间点数据不足，无法绘制趋势图")
            return

        # 创建图表
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

        # 子图1：平均分数趋势
        ax1.plot(time_labels, avg_scores, 'o-', linewidth=2, markersize=8, color='blue')
        ax1.set_xlabel('时间')
        ax1.set_ylabel('平均风险分数')
        ax1.set_title('平均风险分数趋势')
        ax1.grid(True, alpha=0.3)

        # 在点上添加数值标签
        for i, (label, score) in enumerate(zip(time_labels, avg_scores)):
            ax1.annotate(f'{score:.1f}', (label, score), textcoords="offset points",
                        xytext=(0,10), ha='center')

        # 子图2：个股数量趋势
        ax2.bar(time_labels, stock_counts, alpha=0.7, color='green')
        ax2.set_xlabel('时间')
        ax2.set_ylabel('个股数量')
        ax2.set_title('个股数量趋势')
        ax2.grid(True, alpha=0.3)

        # 在柱子上添加数量标签
        for i, (label, count) in enumerate(zip(time_labels, stock_counts)):
            ax2.text(label, count + 0.1, str(count), ha='center', va='bottom')

        plt.tight_layout()

        # 保存或显示图片
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"趋势图表已保存到: {save_path}")
        else:
            plt.show()

        plt.close()


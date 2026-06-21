# rich_enumerate_progress.py
# 带树状嵌套进度条的 enumerate with progress，支持自定义显示名和安全输出
# 使用 rich 实现可视化多级任务追踪

from rich.live import Live
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.tree import Tree
from rich.console import Console
from typing import Iterator, Optional, Any, List, Union, Dict, Callable, TypeVar
from dataclasses import dataclass
from uuid import uuid4
import threading
from contextlib import contextmanager



import os
__FILE__ = __file__.split(os.path.sep)[-1]

__all__ = [
    'ProgressManager',
    'progress_print',
    'enumerate_with_progress',
    'rich_progress',
    'RichProgressContext',
    'register_stop_atexit',
]

# ==============================
# 数据结构定义
# ==============================

@dataclass
class TaskInfo:
    id: str
    name: str
    total: float
    completed: float
    parent_id: Optional[str] = None
    children: List[str] = None
    start_index: int = 1
    current_item: str = ""  # 当前处理项名称
    item_weights: Optional[List[float]] = None    # 若本任务由 enumerate_with_progress 创建，保存其 items 的 weights
    allocated: Optional[float] = None             # 本任务在父任务中的分配量（父层的单位）

    def __post_init__(self):
        if self.children is None:
            self.children = []

    def __repr__(self) -> str:
        # 更友好的 item_weights 展示：最多显示前 5 项，超出部分用 "... (X left)" 表示
        if self.item_weights:
            total_weights = len(self.item_weights)
            if total_weights <= 5:
                weights_str = str(self.item_weights)
            else:
                first_five = ", ".join(repr(x) for x in self.item_weights[:5])
                weights_str = f"[{first_five}, ... ({total_weights-5} left)]"
        else:
            weights_str = "None"

        weights_count = len(self.item_weights) if self.item_weights else 0
        return (
            f"id={self.id}, name='{self.name}', total={self.total}, completed={self.completed}, "
            f"parent_id={self.parent_id}, current_item={self.current_item}, "
            f"item_weights={weights_str} ({weights_count} items), allocated={self.allocated}"
        )


# ==============================
# 全局进度管理器（单例模式）
# ==============================

class FadeLock:
    def __init__(self):
        pass
    
    def __enter__(self) -> bool:
        return True

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class ProgressManager:
    _instance = None
    _lock = FadeLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self.tasks: Dict[str, TaskInfo] = {}
        self.task_order: List[str] = []
        self.console = Console()
        self.live = Live(auto_refresh=False, console=self.console, screen=False)
        self.is_started = False

        # 进度条列配置（用于底部详细进度条）
        self.progress_columns = [
            TextColumn("{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("• {task.completed:.0f}/{task.total:.0f}"),
            # TimeElapsedColumn(),
        ]

        # 复用的 detailed Progress，避免每次刷新创建新对象
        # 关闭 transient（False），确保 Progress 不会在非 Live 场景或结束时直接打印到 stdout
        self.detailed_progress = Progress(*self.progress_columns, refresh_per_second=10, transient=False)
        # 记录当前在 detailed_progress 上已添加的 progress-task id（rich 返回的 id）
        self._progress_task_ids: List[int] = []
        # mapping our internal task_id (str) -> rich progress task id (int)
        self._progress_task_map: Dict[str, int] = {}

    @property
    def _live(self) -> Live:
        return self.live

    def start_live(self):
        with self._lock:
            if not self.is_started:
                # 启动复用的 Progress（TimeElapsedColumn 需要 start 才会计时）
                try:
                    self.detailed_progress.start()
                except Exception:
                    pass
                self.live.start()
                self.is_started = True

    def stop(self):
        """安全停止 Live，应在程序结束时调用"""
        with self._lock:
            if self.is_started:
                try:
                    # 停止并清理 detailed_progress
                    try:
                        # remove any remaining tasks to avoid leak in Progress internal state
                        for pid in list(self._progress_task_ids):
                            try:
                                self.detailed_progress.remove_task(pid)
                            except Exception:
                                pass
                        self._progress_task_ids.clear()
                    except Exception:
                        pass
                    self.detailed_progress.stop()
                except Exception:
                    pass
                self.live.stop()
                self.is_started = False

    @staticmethod
    def show_parents(task_id: str) -> str:
        manager = ProgressManager()
        result = []
        with manager._lock:
            while True:
                task = manager.tasks.get(task_id)
                if not task:
                    break
                result.append(str(task))
                if task.parent_id:
                    task_id = task.parent_id
                else:
                    break
        return "\n → ".join(reversed(result))
    
    @staticmethod
    def _get_display_name(item: Any) -> str:
        """内置默认的显示名称提取逻辑"""
        if hasattr(item, 'full_code'):
            return item.full_code
        elif hasattr(item, 'short_code'):
            return item.short_code
        elif isinstance(item, dict):
            return (item.get('full_code') or 
                    item.get('short_code') or 
                    str({k: v for k, v in item.items() if k in ('code', 'id', 'name')}))
        elif isinstance(item, tuple) and len(item) == 2:
            return str(item[0])
        return str(item)

    @classmethod
    def get_console(cls) -> Console:
        """获取与进度系统绑定的 Console，用于安全输出文本"""
        if cls._instance is None:
            cls()  # 触发实例化
        return cls._instance.console

    def add_task(
        self,
        name: str,
        total: float,
        parent_id: Optional[str] = None,
        start_index: int = 1,
        item_weights: Optional[List[float]] = None,
        allocated: Optional[float] = None,
    ) -> str:
        task_id = str(uuid4())
        task = TaskInfo(
            id=task_id,
            name=name,
            total=float(total),
            completed=0.0,
            parent_id=parent_id,
            start_index=start_index,
            item_weights=item_weights,
            allocated=allocated,
        )
        with self._lock:
            # 如果有 parent 且没有显式传 allocated，则尝试从 parent.item_weights 推断对应分配
            if parent_id is not None and parent_id in self.tasks:
                parent = self.tasks[parent_id]
                child_index = len(parent.children)  # 当前将要成为第几个子任务（按顺序）
                if task.allocated is None and parent.item_weights:
                    if 0 <= child_index < len(parent.item_weights):
                        task.allocated = float(parent.item_weights[child_index])
                # 若没有推断出 allocated，保持 None（后续传播时当作等比或直接传递）

            # 修复：如果调用方传入 total 为 0，但我们从 parent 推断出了 allocated，
            # 则把 total 设为 allocated，便于占位任务按权重正确贡献父层进度
            if task.total == 0.0 and task.allocated is not None:
                task.total = float(task.allocated)

            self.tasks[task_id] = task
            self.task_order.append(task_id)
            if parent_id is not None and parent_id in self.tasks:
                self.tasks[parent_id].children.append(task_id)
        self.refresh_display()
        return task_id

    def update_task(self, task_id: str, advance: float = 0):
        with self._lock:
            if task_id not in self.tasks:
                return
            task = self.tasks[task_id]
            task.completed += advance
            if task.completed > task.total:
                task.completed = task.total

            # 同步到 detailed_progress 并在完成时 stop_task
            if task_id in self._progress_task_map:
                try:
                    self.detailed_progress.update(task_id, completed=task.completed, total=task.total)
                    if task.total > 0 and task.completed >= task.total:
                        try:
                            self.detailed_progress.stop_task(task_id)
                        except Exception:
                            pass
                except Exception:
                    pass

            # 通过子->父的重新计算来维护父层进度
            parent_id = task.parent_id
            self._recalc_parent_progress(parent_id)

            # 把父层的最新 completed 也同步到 detailed_progress 并在完成时 stop_task；
            # 若父层尚未完成，尝试确保其在 Progress 中被 start（以保持 TimeElapsed 列继续计时）
            cur_pid = parent_id
            while cur_pid is not None and cur_pid in self.tasks:
                p = self.tasks[cur_pid]
                if cur_pid in self._progress_task_map:
                    try:
                        # 更新数值与描述
                        self.detailed_progress.update(cur_pid, completed=p.completed, total=p.total)
                        # 如果父层尚未完成，确保 start_task 已被调用（若已 start，rich 会忽略或抛异常）
                        if p.total > 0 and p.completed < p.total:
                            try:
                                self.detailed_progress.start_task(cur_pid)
                            except Exception:
                                pass
                        # 只有当确实完成时才 stop_task
                        if p.total > 0 and p.completed >= p.total:
                            try:
                                self.detailed_progress.stop_task(cur_pid)
                            except Exception:
                                pass
                    except Exception:
                        pass
                cur_pid = p.parent_id

            self.refresh_display()

    def _recalc_parent_progress(self, parent_id: Optional[str]):
        """
        从子节点的当前 completed 状态重新计算每层父任务的完成量：
        - 如果 child.allocated 和 child.total 可用，按 child.allocated * (child.completed/child.total) 贡献父层；
        - 否则把 child.completed 当作与父同单位直接累加（1:1）。
        递归向上直至根节点或不存在的父节点。
        """
        while parent_id is not None and parent_id in self.tasks:
            parent = self.tasks[parent_id]
            accum = 0.0
            for child_id in parent.children:
                child = self.tasks.get(child_id)
                if child is None:
                    continue
                if child.allocated is not None and child.total > 0:
                    accum += child.allocated * (child.completed / child.total)
                else:
                    accum += child.completed
            # 以子贡献为准，且不超过父 total
            parent.completed = min(parent.total, accum)
            parent_id = parent.parent_id

    def update_task_current(self, task_id: str, item_display: str):
        """更新任务当前正在处理的项目名称"""
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].current_item = item_display
        self.refresh_display()

    def refresh_display(self):
        with self._lock:
            # 不再使用 Tree，统一由 detailed_progress 渲染
            # 保留占位字段以兼容外部可能的引用
            self.root_tree = None

            # 确保 detailed_progress 被启动（以便 TimeElapsedColumn 开始计时）
            if not self.is_started:
                try:
                    self.start_live()
                except Exception:
                    pass

            # 注意：不要每次移除再重建所有 rich tasks，会丢失 start_time 导致 TimeElapsed 无效。
            # 改为增量注册：仅对尚未注册的内部任务调用 add_task/start_task，已注册的只 update。
            for tid in self.task_order:
                t = self.tasks[tid]
                desc = f"{t.name}"
                if t.current_item:
                    desc += f" · [blue]{t.current_item}[/blue]"

                if tid not in self._progress_task_map:
                    # 新任务：在 detailed_progress 上注册并 start_task，从而让 TimeElapsedColumn 开始计时
                    try:
                        pid = self.detailed_progress.add_task(description=desc, total=t.total, completed=t.completed)
                        self._progress_task_map[tid] = pid
                        self._progress_task_ids.append(pid)
                        try:
                            self.detailed_progress.start_task(pid)
                        except Exception:
                            # 有些 rich 版本 start_task 接受 str/int 不同，这里忽略异常
                            try:
                                self.detailed_progress.start_task(tid)
                            except Exception:
                                pass
                        # 占位或 0-total 的任务立即 stop，防止一直计时
                        if t.total <= 0:
                            try:
                                self.detailed_progress.update(pid, completed=t.completed, total=t.total)
                                self.detailed_progress.stop_task(pid)
                            except Exception:
                                pass
                    except Exception:
                        pass
                else:
                    # 已注册：只更新 description/completed/total；若完成则 stop_task
                    pid = self._progress_task_map.get(tid)
                    try:
                        # 尝试用 pid 更新（部分 rich 版本支持 description 更新）
                        self.detailed_progress.update(pid, description=desc, completed=t.completed, total=t.total)
                        if t.total > 0 and t.completed >= t.total:
                            try:
                                self.detailed_progress.stop_task(pid)
                            except Exception:
                                pass
                    except Exception:
                        # 回退：尝试只更新数字
                        try:
                            self.detailed_progress.update(pid, completed=t.completed, total=t.total)
                        except Exception:
                            pass

            # 组合布局：只包含标题与 detailed_progress（避免重复刷屏）
            layout = Table.grid(padding=(1, 0))
            layout.add_row(self.detailed_progress.get_renderable())

            # 更新 Live（优先使用 Live 固定位置渲染，避免进度输出与 stdout 混合）
            try:
                if not self.is_started:
                    self.start_live()
                # 将 layout 交给 Live 进行渲染（会固定在底部/指定位置）
                self.live.update(layout, refresh=True)
            except Exception:
                # 若 Live 无法启动或更新失败，作为兜底只打印一次布局（不频繁打印）
                try:
                    self.console.print(layout)
                except Exception:
                    pass


    def _add_node_to_tree(self, parent: Tree, task_id: str):
        task = self.tasks[task_id]
        icon = "📁" if task.children else "🔹"
        percent = (task.completed / task.total * 100) if task.total > 0 else 0
        color = "green" if task.completed >= task.total else "yellow"

        label = f"[{color}]{icon} {task.name}"
        # if task.current_item:
        #     label += f" [gray]· 当前:[/] [{color}]{task.current_item}[/]"
        label += f" [white]•[/] [{color}]{task.completed:.0f}/{task.total:.0f}"
        label += f" [gray]({percent:.0f}%)[/]"

        node = parent.add(label)
        for child_id in task.children:
            self._add_node_to_tree(node, child_id)


# ==============================
# 高层函数导出
# ==============================

def progress_print(*args, **kwargs):
    """
    安全打印函数：优先使用 ProgressManager 的 Console。
    可替代 print() 和 rich.print，避免破坏 Live 渲染。
    """
    console = ProgressManager.get_console()
    if console:
        console.print(*args, **kwargs)
    else:
        Console().print(*args, **kwargs)


_T = TypeVar('_T', bound=Any)

def enumerate_with_progress(
    iterable: Iterator[_T],
    sizes: Optional[List[Union[int, float]]] = None,
    task_name: str = "Processing",
    start: int = 0,
    display_name_func: Optional[Callable[[_T], str]] = None,
) -> Iterator[tuple[int, _T]]:
    """
    带进度条的 enumerate，支持多层嵌套和自定义显示名。

    Args:
        iterable: 要遍历的对象
        sizes: 每一项的工作量权重（如下载大小），默认平均分配
        task_name: 任务名称
        start: 起始索引
        display_name_func: 自定义函数，从 item 提取显示名；若为 None，则使用内置规则

    Yields:
        (index, item)
    """
    items = list(iterable)
    n = len(items)

    manager = ProgressManager()

    if n == 0:
        # 即使没有子项，也创建一个占位子任务，保证父任务的权重槽被占用并按权重贡献进度
        current_parent = None
        with manager._lock:
            for tid in reversed(manager.task_order):
                t = manager.tasks[tid]
                if t.parent_id is None or t.completed < t.total:
                    current_parent = tid
                    break

        placeholder_id = manager.add_task(
            name=task_name,
            total=0.0,  # 若能从 parent.item_weights 推断出 allocated，add_task 会把 total 设为 allocated
            parent_id=current_parent,
            start_index=start,
        )
        # 保证 item_weights 字段存在，避免后续逻辑访问时报错
        with manager._lock:
            if placeholder_id in manager.tasks:
                manager.tasks[placeholder_id].item_weights = []

        # 如果 add_task 根据 parent 推断出了 allocated 并填充了 total，立即把该占位任务标为完成
        final_task = manager.tasks.get(placeholder_id)
        if final_task and final_task.total > 0:
            manager.update_task(placeholder_id, advance=final_task.total)
        manager.update_task_current(placeholder_id, "完成")
        return iter([])

    # 权重处理
    if sizes is None:
        weights = [1.0] * n
    else:
        if len(sizes) != n:
            raise ValueError("sizes 长度必须与 iterable 一致")
        weights = [float(w) for w in sizes]

    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("总权重必须大于 0")

    # 查找父任务
    current_parent = None
    with manager._lock:
        # 找到最后一个添加的、且未完成的非叶子任务或根任务
        for tid in reversed(manager.task_order):
            t = manager.tasks[tid]
            if t.parent_id is None or t.completed < t.total:
                current_parent = tid
                break

    # 添加任务
    task_id = manager.add_task(
        name=task_name,
        total=total_weight,
        parent_id=current_parent,
        start_index=start,
    )
    # 把当前 iterable 的 weights 保存在任务上，供子任务创建时推断 allocated
    with manager._lock:
        manager.tasks[task_id].item_weights = weights

    try:
        for i, item in enumerate(items):
            # 决定使用哪个显示函数
            display_func = display_name_func or manager._get_display_name
            current_name = display_func(item)

            # 更新当前项
            manager.update_task_current(task_id, current_name)

            # input(f"[1] {__FILE__}: {ProgressManager.show_parents(task_id)}")

            yield (start + i, item)

            # 更新进度
            # input(f"[2] {__FILE__}: {ProgressManager.show_parents(task_id)}")
            manager.update_task(task_id, advance=weights[i])

            # input(f"[3] {__FILE__}: {ProgressManager.show_parents(task_id)}")

    finally:
        final_task = manager.tasks.get(task_id)
        if final_task and final_task.completed < final_task.total:
            manager.update_task(task_id, advance=final_task.total - final_task.completed)
        manager.update_task_current(task_id, "完成")

        # input(f"[4] {__FILE__}: (finally) {ProgressManager.show_parents(task_id)}")


def register_stop_atexit():
    """注册 atexit 钩子，在程序退出时自动停止进度系统"""
    import atexit
    atexit.register(lambda: ProgressManager().stop())


@contextmanager
def rich_progress():
    """
    上下文管理器：确保进度系统在作用域结束时被正确关闭。
    
    示例：
        with rich_progress():
            for i, x in enumerate_with_progress(data, ...):
                ...
    """
    try:
        yield
    finally:
        ProgressManager().stop()

class RichProgressContext:
    """上下文管理器，确保在程序退出时关闭进度条"""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ProgressManager().stop()

# ==============================
# 示例代码（仅当直接运行时执行）
# ==============================

if __name__ == "__main__":
    import time
    import random

    # 启用自动退出清理
    register_stop_atexit()

    class Stock:
        def __init__(self, code: str, name: str):
            self.full_code = code
            self.name = name
        def __str__(self):
            return f"{self.full_code}({self.name})"

    stocks = [
        Stock("600000.SH", "浦发银行"),
        Stock("000001.SZ", "平安银行"),
        Stock("09988.HK", "美团-W"),
    ]

    steps = [("加载", 5), ("分析", 10), ("导出", 5)]

    with rich_progress():
        progress_print("[bold cyan]🚀 开始金融数据处理任务[/]\n")

        for step_i, (step_name, step_size) in enumerate_with_progress(steps, sizes=[s for _, s in steps], task_name="主流程"):
            progress_print(f"[blue]📌 步骤 {step_i}: {step_name}[/]")

            sub_items = stocks * random.randint(1, 2)
            for item_i, stock in enumerate_with_progress(
                sub_items,
                task_name=f"→ {step_name}",
                display_name_func=lambda s: s.full_code
            ):
                progress_print(f"  📥 正在处理 {stock.full_code} ...")
                # time.sleep(random.uniform(0.2, 0.6))
                time.sleep(1)

        progress_print("\n[bold green]🎉 所有任务已完成！[/]")

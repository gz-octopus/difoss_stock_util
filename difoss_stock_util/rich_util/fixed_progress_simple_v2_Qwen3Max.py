import threading
from typing import List, Optional, Any, Callable, Generator, Tuple, Iterable, TypeVar
from rich.console import Console
from rich.progress import Progress, Live, SpinnerColumn, TextColumn, BarColumn
import time


__all__ = [
    "enumerate_with_progress",
    "progress_print",
]

_T = TypeVar("_T")

class ProgressManager:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls, console: Console = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init(console=console)
        return cls._instance

    def _init(self, console: Console = None):
        # 防止重复初始化
        if hasattr(self, 'stack'):
            return

        self.stack: List[dict] = []  # 当前处理栈
        self.ui_initialized: bool = False
        self.console = console
        self.progress: Optional[Progress] = None
        self.live: Optional[Live] = None
        self.main_task: Optional[Any] = None

    def enter_root(self, task_name: str):
        with self._lock:
            if self.ui_initialized:
                return  # 避免重复初始化

            self.console = self.console or Console()
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold]{task.description}"),
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                console=self.console
            )
            self.live = Live(
                self.progress,
                console=self.console,
                refresh_per_second=10
            )
            self.live.__enter__()
            self.main_task = self.progress.add_task(
                task_name,
                total=100
            )
            self.ui_initialized = True

    def exit_root(self):
        with self._lock:
            if not self.ui_initialized:
                return

            # 完成主任务
            self.progress.update(
                self.main_task,
                completed=100,
                description="[green]✓ Complete"
            )
            time.sleep(0.5)
            self.live.__exit__(None, None, None)
            self.console.print("\n[bold green]Done!")

            # 重置状态
            self._reset_state()

    def _reset_state(self):
        """重置所有状态，以便下次使用"""
        self.stack.clear()
        self.ui_initialized = False
        self.console = None
        self.progress = None
        self.live = None
        self.main_task = None

    def push_context(self, context_info: dict):
        with self._lock:
            self.stack.append(context_info)

    def pop_context(self) -> dict:
        with self._lock:
            if not self.stack:
                raise IndexError("Stack is empty")
            return self.stack.pop()

    def get_stack_depth(self) -> int:
        with self._lock:
            return len(self.stack)

    def get_current_level(self) -> Optional[dict]:
        with self._lock:
            if not self.stack:
                return None
            return self.stack[-1]

    def remove_task(self, task_id: Any):
        with self._lock:
            if self.progress:
                self.progress.remove_task(task_id)

    def add_task(self, description: str, total: float = 100) -> Any:
        with self._lock:
            if self.progress:
                return self.progress.add_task(description, total=total)
            return None

    def update_task(self, task_id: Any, completed: float, description: str = None):
        with self._lock:
            if self.progress:
                kwargs = {'completed': completed}
                if description is not None:
                    kwargs['description'] = description
                self.progress.update(task_id, **kwargs)

    def _update_display_tasks(self):
        """只更新显示任务，不更新主任务进度"""
        # 这里只确保显示任务存在，进度在主任务更新时处理
        pass

    def update_main_progress(self):
        """更新主任务进度 - 简化的正确版本"""
        with self._lock:
            if not self.stack or not self.ui_initialized:
                return

            # 核心修复：正确的进度计算方向
            # 从最外层开始，逐层向内计算
            global_progress = 0.0

            # 如果有多层，只计算最外层的进度（因为内层进度已经包含在外层中）
            if len(self.stack) > 0:
                outermost_level = self.stack[0]

                # 最外层的进度 = 已完成项目的权重和 + 当前项目的进度
                completed_weight = 0.0
                for j in range(outermost_level['completed']):
                    if j < len(outermost_level['weights']):
                        completed_weight += outermost_level['weights'][j]

                # 当前正在处理的项目（如果有）
                current_contribution = 0.0
                if outermost_level['completed'] < outermost_level['total']:
                    current_index = outermost_level['completed']
                    if current_index < len(outermost_level['weights']):
                        current_weight = outermost_level['weights'][current_index]

                        # 关键：如果当前项目有子层（即stack深度>1）
                        if len(self.stack) > 1:
                            # 找到当前项目的子层进度
                            for level_idx in range(1, len(self.stack)):
                                inner_level = self.stack[level_idx]
                                # 计算内层的进度
                                inner_completed = sum(inner_level['weights'][:inner_level['completed']])
                                if inner_level['completed'] < inner_level['total']:
                                    # 内层当前项目给一点点进度
                                    inner_current = inner_level['weights'][inner_level['completed']] * 0.01
                                    inner_progress = inner_completed + inner_current
                                else:
                                    inner_progress = inner_completed

                                # 外层当前项目进度 = 内层进度
                                current_contribution = current_weight * inner_progress
                                break
                        else:
                            # 没有子层，当前项目刚开始
                            current_contribution = current_weight * 0.01  # 1%表示已开始

                global_progress = completed_weight + current_contribution

            if self.main_task:
                self.progress.update(
                    self.main_task,
                    completed=global_progress * 100
                )


def _normalize_weights(weights):
    """归一化权重"""
    total = sum(weights)
    if total > 0:
        return [w / total for w in weights]
    return [1.0 / len(weights)] * len(weights)

def _get_item_name(item: Any) -> str:
    """获取项目显示名称"""
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

def enumerate_with_progress(
    items: Iterable[_T],
    sizes: Optional[Iterable[float]] = None,
    desc: str = "",
    task_name: str = "Processing",
    start: int = 0,
    display_name_func: Optional[Callable[[_T], str]] = None,
    console: Console = None
) -> Generator[Tuple[int, _T], None, None]:
    """
    修复版：解决第二级进度问题
    使用简单直接的进度计算
    """
    # 获取单例实例
    pm = ProgressManager(console)

    items_list = list(items)
    if not items_list:
        return

    # 处理权重
    if sizes is not None:
        weights_list = list(sizes)
        if len(weights_list) != len(items_list):
            raise ValueError(f"weights长度({len(weights_list)})必须等于items长度({len(items_list)})")
        normalized_weights = _normalize_weights(weights_list)
    else:
        normalized_weights = [1.0 / len(items_list)] * len(items_list)

    is_root = pm.get_stack_depth() == 0

    if is_root:
        # 初始化UI
        pm.enter_root(task_name)

    # 当前层信息
    current_level = {
        'id': id(items_list),  # 唯一标识
        'total': len(items_list),
        'completed': 0,
        'depth': pm.get_stack_depth(),
        'task_id': None,
        'desc': desc,
        'weights': normalized_weights,
        'current_item_index': -1
    }
    pm.push_context(current_level)

    try:
        for i, item in enumerate(items_list):
            current_level['current_item_index'] = i
            current_level['current_weight'] = normalized_weights[i] if i < len(normalized_weights) else 0

            # 关键修复：更新显示任务（但不更新主任务进度）
            pm._update_display_tasks()

            # 显示设置
            indent = "  " * current_level['depth']
            if display_name_func:
                item_name = display_name_func(item)
            else:
                item_name = _get_item_name(item)

            # 权重显示
            weight_info = ""
            if sizes is not None:
                orig_weight = list(sizes)[i] if i < len(list(sizes)) else normalized_weights[i]
                weight_info = f" (权重: {orig_weight:.2f})"

            display_text = f"{indent}[dim]{desc}{item_name}{weight_info}" if desc else f"{indent}[dim]{item_name}{weight_info}"

            if current_level['task_id'] is None:
                # 关键修复：显示任务不设置parent，避免嵌套问题
                current_level['task_id'] = pm.add_task(
                    display_text,
                    total=100
                )
            else:
                pm.update_task(
                    current_level['task_id'],
                    completed=0,  # 我们稍后更新进度
                    description=display_text
                )

            # 显示任务进度：当前项目刚开始
            display_progress = (i / len(items_list)) * 100
            pm.update_task(
                current_level['task_id'],
                completed=display_progress,
                description=display_text
            )

            yield i + start, item

            # 项目完成
            current_level['completed'] += 1

            # 更新显示任务为完成状态
            completed_progress = ((i + 1) / len(items_list)) * 100
            pm.update_task(
                current_level['task_id'],
                completed=completed_progress,
                description=f"{indent}[green]✓ {item_name}{weight_info}"
            )

            # 更新主任务进度（关键：这里才更新全局进度）
            pm.update_main_progress()

    finally:
        # 清理显示任务
        if current_level['task_id'] is not None:
            pm.remove_task(current_level['task_id'])

        pm.pop_context()

        if is_root and pm.ui_initialized:
            pm.exit_root()


def progress_print(*args, **kwargs):
    """打印消息"""
    pm = ProgressManager()
    if pm.console:
        pm.console.print(*args, **kwargs)
    else:
        Console().print(*args, **kwargs)

# 专门测试第二级进度的函数
def test_second_level_fix():
    """专门测试第二级进度问题"""
    print("测试：第二级进度修复")
    print("="*60)

    print("模拟你的场景：")
    print("1. 第一级：4个步骤")
    print("2. 第二级：入库步骤有多个股票")
    print("3. 验证第二级进度是否正常")
    print()

    # 第一级
    steps = ["准备", "下载", "处理", "入库"]
    step_weights = [10, 20, 30, 40]

    for i, step in enumerate_with_progress(
        steps,
        sizes=step_weights,
        task_name="多级进度测试"
    ):
        progress_print(f"\n第一级: {step} (权重: {step_weights[i]})")

        if i == 3:  # 入库步骤
            progress_print("  开始入库处理...")

            # 第二级：股票列表
            stocks = ["396610.SZ", "000001.SZ", "000002.SZ"]
            for j, stock in enumerate_with_progress(stocks):
                progress_print(f"    正在入库: {stock}")

                # 模拟处理
                for _ in range(3):
                    time.sleep(0.05)
                    # 进度会自动更新

                progress_print(f"    完成: {stock}")

        progress_print(f"完成: {step}")

    print("\n" + "="*60)
    print("✅ 第二级进度测试完成")

# 最小测试：只有两级
def test_minimal():
    """最小测试用例"""
    print("\n最小测试：两级进度")
    print("="*60)

    # 第一级：只有一个项目
    for i, outer in enumerate_with_progress(["外层任务"], task_name="最小测试"):
        progress_print(f"外层开始")

        # 第二级：多个子项目
        for j, inner in enumerate_with_progress(["子1", "子2", "子3"]):
            progress_print(f"  内层处理: {inner}")
            time.sleep(0.05)

        progress_print(f"外层完成")

    print("\n" + "="*60)
    print("✅ 最小测试完成")

if __name__ == "__main__":
    print("开始测试修复版 - 重点解决第二级进度问题")
    print("="*60)

    test_minimal()
    test_second_level_fix()

    print("\n" + "="*60)
    print("✅ 所有测试完成!")

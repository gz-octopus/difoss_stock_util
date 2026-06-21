#!python

import pandas as pd
from rich.table import Table
import numpy as np
from rich import print as rich_print
import re

__all__ = [
    "dataframe_to_rich_table",
    "print_dataframe",
    'check_text_in_column',
]

# 高级版本：添加更多footer信息的可选函数
def dataframe_to_rich_table_v0(df: pd.DataFrame,
                            title: str = "DataFrame 表格",
                            decimal_point: int = 2,
                            positive_is_red: bool = True,
                            show_index: bool = False,
                            show_footer: bool = False,
                            footer_options: dict = None
) -> Table:
    """将 Pandas DataFrame 转换为 Rich Table（带详细footer）

    Args:
        df: Pandas DataFrame
        title: 表格标题
        decimal_point: 浮点数小数位数
        positive_is_red: 正数是否显示为红色
        show_index: 是否显示行索引
        show_footer: 是否显示行列信息的footer（footer_options一旦非空，此选项自动开启）
        footer_options: footer显示选项，可包含:
            - show_shape: 是否显示形状
            - show_stats: 是否显示统计信息
            - show_memory: 是否显示内存使用
            - show_na: 是否显示缺失值信息
            - custom_text: 自定义footer文本
    """

    # 创建表格
    table = Table(title=title, show_header=True, header_style="bold blue")

    # 如果需要显示索引，添加索引列
    if show_index:
        table.add_column("INDEX", style="dim", justify="right")

    # 添加数据列
    for column in df.columns:
        table.add_column(str(column), style="cyan")

    # 添加行
    for index, row in df.iterrows():
        formatted_row = []

        # 添加索引（如果需要）
        if show_index:
            formatted_row.append(str(index))

        # 预编译列名关键词判断（提高性能）
        percent_keywords = {'幅', '率', '比', '涨跌', '变化'}
        value_keywords = {'价', '值', '额', '格', '成本', '收入', '利润'}
        amount_keywords = {'量', '数', '手', '股', '份', '笔'}

        # 格式化数据
        for column_i, value in enumerate(row):
            column_str = str(df.columns[column_i])

            # 判断列类型并应用格式
            is_percent = any(keyword in column_str for keyword in percent_keywords)
            is_value = any(keyword in column_str for keyword in value_keywords)
            is_amount = any(keyword in column_str for keyword in amount_keywords)

            if isinstance(value, (float, np.floating)):

                # 浮点数格式化为指定小数位数
                formatted_value = format(value, f".{decimal_point}f")
                # 方法1：使用round()四舍五入

                # 设置颜色
                color = "red" if (positive_is_red ^ (value < 0)) else "green"


                # 根据列名内容应用不同格式
                if is_percent:
                    # 百分比类数据：添加%符号
                    formatted_value = f"[{color}]{formatted_value}%[/{color}]"
                elif is_value or is_amount:
                    # 价格、数值类数据：添加颜色
                    formatted_value = f"[{color}]{formatted_value}[/{color}]"
                else:
                    formatted_value = str(value)

            elif isinstance(value, (int, np.integer)):
                # 大整数添加千位分隔符
                if abs(value) >= 10000:
                    formatted_value = f"{value:,}"
                else:
                    formatted_value = str(value)

                # 为整数也添加颜色（如果是数值类型）
                if is_amount:
                    color = "red" if (positive_is_red ^ (value < 0)) else "green"
                    formatted_value = f"[{color}]{formatted_value}[/{color}]"
            else:
                formatted_value = str(value)

            formatted_row.append(formatted_value)

        table.add_row(*formatted_row)


    if footer_options:
        show_footer = True # 既然都已经设置选项了，有可能是忘记开启显示选项

    # 添加footer显示行列信息
    if show_footer:
        # 默认footer选项
        default_footer = {
            'show_shape': True,
            'show_stats': True,
            'show_memory': True,
            'show_na': True,
            'custom_text': None
        }

        if footer_options:
            default_footer.update(footer_options)

        footer_options = default_footer


        # 构建footer文本
        footer_parts = []

        # 1. 形状信息
        if footer_options['show_shape']:
            rows, cols = df.shape
            footer_parts.append(f"形状: {rows}行 × {cols}列")

        # 2. 缺失值信息
        if footer_options['show_na'] and df.isna().any().any():
            na_count = df.isna().sum().sum()
            na_percentage = (na_count / (rows * cols)) * 100
            footer_parts.append(f"缺失值: {na_count}个 ({na_percentage:.1f}%)")

        # 3. 统计信息
        if footer_options['show_stats']:
            numeric_cols = df.select_dtypes(include=[np.number])
            if not numeric_cols.empty:
                numeric_count = len(numeric_cols.columns)
                footer_parts.append(f"数值列: {numeric_count}个")

                # 添加基本统计
                if len(numeric_cols.columns) > 0:
                    stats = numeric_cols.describe()
                    # TODO: 可以添加更多统计信息

        # 4. 内存使用（估算）
        if footer_options['show_memory']:
            memory_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
            footer_parts.append(f"内存: {memory_mb:.2f} MB")

        # 5. 自定义文本
        if footer_options['custom_text']:
            footer_parts.append(footer_options['custom_text'])

        # 将所有footer部分组合
        if footer_parts:
            footer_text = " | ".join(footer_parts)
            table.caption = f"[dim]{footer_text}[/dim]"

    return table

def dataframe_to_rich_table(df: pd.DataFrame,
                            title: str = "DataFrame 表格",
                            decimal_point: int = 2,
                            positive_is_red: bool = True,
                            show_index: bool = False,
                            show_footer: bool = False,
                            footer_options: dict = None,
                            sum_cols: list[str] = [],   # 新增参数，指定要显示合计的列
) -> Table:
    """将 Pandas DataFrame 转换为 Rich Table（带详细footer）

    Args:
        df: Pandas DataFrame
        title: 表格标题
        decimal_point: 浮点数小数位数
        positive_is_red: 正数是否显示为红色
        show_index: 是否显示行索引
        show_footer: 是否显示行列信息的footer（footer_options一旦非空，此选项自动开启）
        footer_options: footer显示选项，可包含:
            - show_shape: 是否显示形状
            - show_stats: 是否显示统计信息
            - show_memory: 是否显示内存使用
            - show_na: 是否显示缺失值信息
            - custom_text: 自定义footer文本
        sum_cols: 需要显示合计的列名列表，合计值会显示在表头下方的第一行
    """

    # 创建表格
    table = Table(title=title, show_header=True, header_style="bold blue")

    # 预计算各列的合计值（如果需要）
    col_sums = {}
    if sum_cols:
        for col in sum_cols:
            if col in df.columns:
                # 尝试计算数值列的合计
                try:
                    # 只对数值类型的列计算合计
                    if pd.api.types.is_numeric_dtype(df[col]):
                        col_sums[col] = df[col].sum()
                    else:
                        # 尝试转换为数值
                        numeric_series = pd.to_numeric(df[col], errors='coerce')
                        if not numeric_series.isna().all():
                            col_sums[col] = numeric_series.sum()
                except:
                    # 如果无法计算合计，忽略该列
                    pass

    # 计算索引列的合计（如果需要显示索引且索引是数值类型）
    index_sum = None
    if show_index and sum_cols and 'INDEX' in sum_cols:
        try:
            if pd.api.types.is_numeric_dtype(df.index):
                index_sum = df.index.sum()
        except:
            pass

    # 是否需要显示合计行
    show_sum_row = bool(sum_cols) or index_sum is not None

    # 添加列
    columns_to_add = []

    # 如果需要显示索引，添加索引列
    if show_index:
        # 判断索引列是否需要显示合计
        index_style = "dim"
        if index_sum is not None:
            index_style = "bold yellow"  # 高亮显示有合计的列
        table.add_column("INDEX", style=index_style, justify="right")
        columns_to_add.append("INDEX")

    # 添加数据列
    for column in df.columns:
        # 判断该列是否需要显示合计
        col_style = "cyan"
        if column in col_sums:
            col_style = "bold yellow"  # 高亮显示有合计的列
        table.add_column(str(column), style=col_style)
        columns_to_add.append(column)

    # 如果需要显示合计行，先添加合计行
    if show_sum_row:
        sum_row = []

        # 索引列的合计
        if show_index:
            if index_sum is not None:
                # # 格式化索引合计
                if isinstance(index_sum, (float, np.floating)):
                    sum_row.append(f"[bold yellow]{index_sum:.{decimal_point}f}[/bold yellow]")
                elif isinstance(index_sum, (int, np.integer)):
                    sum_row.append(f"[bold yellow]{index_sum:,}[/bold yellow]")
                else:
                    sum_row.append(f"[bold yellow]{index_sum}[/bold yellow]")
            else:
                sum_row.append("[dim]—[/dim]")  # 不显示合计

        # 数据列的合计
        for column in df.columns:
            if column in col_sums:
                sum_value = col_sums[column]
                # 格式化合计值
                if isinstance(sum_value, (float, np.floating)):
                    formatted_sum = f"{sum_value:.{decimal_point}f}"
                    sum_row.append(f"[bold yellow]{formatted_sum}[/bold yellow]")
                elif isinstance(sum_value, (int, np.integer)):
                    formatted_sum = f"{sum_value:,}"
                    sum_row.append(f"[bold yellow]{formatted_sum}[/bold yellow]")
                else:
                    sum_row.append(f"[bold yellow]{sum_value}[/bold yellow]")
            else:
                sum_row.append("[dim]—[/dim]")  # 不显示合计

        table.add_row(*sum_row)

        # 添加一个分隔行
        separator_row = ["[dim]—[/dim]"] * len(columns_to_add)
        table.add_row(*separator_row)

    # 添加数据行
    for index, row in df.iterrows():
        formatted_row = []

        # 添加索引（如果需要）
        if show_index:
            formatted_row.append(str(index))

        # 预编译列名关键词判断（提高性能）
        percent_keywords = {'幅', '率', '比', '涨跌', '变化'}
        value_keywords = {'价', '值', '额', '格', '成本', '收入', '利润'}
        amount_keywords = {'量', '数', '手', '股', '份', '笔'}

        # 格式化数据
        for column_i, value in enumerate(row):
            column_str = str(df.columns[column_i])

            # 判断列类型并应用格式
            is_percent = any(keyword in column_str for keyword in percent_keywords)
            is_value = any(keyword in column_str for keyword in value_keywords)
            is_amount = any(keyword in column_str for keyword in amount_keywords)

            if isinstance(value, (float, np.floating)):
                # 浮点数格式化为指定小数位数
                formatted_value = format(value, f".{decimal_point}f")

                # 设置颜色
                color = "red" if (positive_is_red ^ (value < 0)) else "green"

                # 根据列名内容应用不同格式
                if is_percent:
                    # 百分比类数据：添加%符号
                    formatted_value = f"[{color}]{formatted_value}%[/{color}]"
                elif is_value or is_amount:
                    # 价格、数值类数据：添加颜色
                    formatted_value = f"[{color}]{formatted_value}[/{color}]"
                else:
                    formatted_value = str(value)

            elif isinstance(value, (int, np.integer)):
                # 大整数添加千位分隔符
                if abs(value) >= 10000:
                    formatted_value = f"{value:,}"
                else:
                    formatted_value = str(value)

                # 为整数也添加颜色（如果是数值类型）
                if is_amount:
                    color = "red" if (positive_is_red ^ (value < 0)) else "green"
                    formatted_value = f"[{color}]{formatted_value}[/{color}]"
                else:
                    formatted_value = f"[white]{formatted_value}[/white]"
            else:
                formatted_value = str(value)

            formatted_row.append(formatted_value)

        table.add_row(*formatted_row)

    if footer_options:
        show_footer = True  # 既然都已经设置选项了，有可能是忘记开启显示选项

    # 添加footer显示行列信息
    if show_footer:
        # 默认footer选项
        default_footer = {
            'show_shape': True,
            'show_stats': True,
            'show_memory': True,
            'show_na': True,
            'custom_text': None
        }

        if footer_options:
            default_footer.update(footer_options)

        footer_options = default_footer

        # 构建footer文本
        footer_parts = []

        # 1. 形状信息
        if footer_options['show_shape']:
            rows, cols = df.shape
            footer_parts.append(f"形状: {rows}行 × {cols}列")

        # 2. 缺失值信息
        if footer_options['show_na'] and df.isna().any().any():
            na_count = df.isna().sum().sum()
            na_percentage = (na_count / (rows * cols)) * 100
            footer_parts.append(f"缺失值: {na_count}个 ({na_percentage:.1f}%)")

        # 3. 统计信息
        if footer_options['show_stats']:
            numeric_cols = df.select_dtypes(include=[np.number])
            if not numeric_cols.empty:
                numeric_count = len(numeric_cols.columns)
                footer_parts.append(f"数值列: {numeric_count}个")

                # 添加基本统计
                if len(numeric_cols.columns) > 0:
                    stats = numeric_cols.describe()
                    # TODO: 可以添加更多统计信息

        # 4. 内存使用（估算）
        if footer_options['show_memory']:
            memory_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
            footer_parts.append(f"内存: {memory_mb:.2f} MB")

        # 5. 自定义文本
        if footer_options['custom_text']:
            footer_parts.append(footer_options['custom_text'])

        # 将所有footer部分组合
        if footer_parts:
            footer_text = " | ".join(footer_parts)
            table.caption = f"[dim]{footer_text}[/dim]"

    return table


def print_dataframe(df: pd.DataFrame,
    title: str = "DataFrame 表格",
    table_max_rows: int = 300,
    printer = None,
    show_index = True,
    sum_cols: list[str] = [],
    **args
):
    """打印DataFrame的内容"""
    if printer is None:
        printer = rich_print

    # DEBUG
    # printer(f"df.Index={df.index}, dtype={df.index.dtype}")
    if len(df) > table_max_rows:
        printer(f"{title}", df)
    else:
        printer(dataframe_to_rich_table(df, title=title, show_index=show_index, sum_cols=sum_cols, **args))


def check_text_in_column(df: pd.DataFrame, column_name: str, finds: list[str]) -> pd.DataFrame:
    """
    检查DataFrame指定列是否包含find_names中的任意字符串
    返回布尔序列（True表示包含任意关键词）

    参数:
        df: 目标DataFrame
        column_name: 要检查的列名
        finds: 需要匹配的关键词列表

    返回:
        pd.Series: 布尔结果序列
    """
    if column_name not in df.columns:
        raise ValueError(f"列名 '{column_name}' 不存在于DataFrame中")

    pattern = '|'.join(map(re.escape, finds))  # 转义特殊字符
    return df[df[column_name].str.contains(pattern, case=False, na=False)]

# 使用示例函数
def example_usage():
    """使用示例"""
    # 显示表格（需要rich库的console）
    from rich.console import Console
    console = Console()

    import numpy as np

    # 创建示例DataFrame
    np.random.seed(42)

    data = {
        '股票代码': ['000001.SZ', '600519.SH', '000858.SZ', '300750.SZ'],
        '名称': ['平安银行', '贵州茅台', '五粮液', '宁德时代'],
        '收盘价': np.round(np.random.uniform(50, 300, 4), 2),
        '涨跌幅(%)': np.round(np.random.uniform(-5, 5, 4), 2),
        '成交量(手)': np.random.randint(10000, 1000000, 4),
        '市值(亿)': np.round(np.random.uniform(1000, 10000, 4), 2)
    }

    df = pd.DataFrame(data)

    # 使用基础版本
    console.print("=== 基础版本 ===")
    table1 = dataframe_to_rich_table(df, title="股票数据", show_footer=True)
    console.print(table1)

    # 使用高级版本
    console.print("\n=== 高级版本 ===")
    footer_opts = {
        'show_shape': True,
        'show_stats': True,
        'show_memory': True,
        'show_na': True,
        'custom_text': '数据更新: 2024-01-15'
    }
    table2 = dataframe_to_rich_table(
        df,
        title="股票数据详情",
        footer_options=footer_opts
    )

    console.print(table2)


if __name__ == "__main__":
    example_usage()
#!python

import pandas as pd
from rich.table import Table

__all__ = ["dataframe_to_rich_table"]

def dataframe_to_rich_table(df: pd.DataFrame,
                            title: str = "DataFrame 表格",
                            decimal_point: int = 2,
                            positive_is_red: bool = True) -> Table:
    """将 Pandas DataFrame 转换为 Rich Table"""
    
    table = Table(title=title, show_header=True, header_style="bold blue")
    
    # 添加列
    for column in df.columns:
        table.add_column(str(column), style="cyan")
    
    # 添加行
    for index, row in df.iterrows():
        # 格式化数值
        formatted_row = []
        for column_i, value in enumerate(row):
            column_str = str(df.columns[column_i])
            if isinstance(value, float):
                # 浮点数格式化为 {decimal_point} 位小数
                # formatted_value = f"{value:.{decimal_point}f}"
                floated_value = format(value, f".{decimal_point}f")
                color = "red" if (positive_is_red ^ (value < 0)) else "green"
                if '幅' in column_str or '率' in column_str:
                    # formatted_value = f"[{color}]{value:+.2f}%[/{color}]"
                    formatted_value = f"[{color}]{floated_value}%[/{color}]"
                elif '价' in column_str or '值' in column_str:
                    formatted_value = floated_value
                else:
                    formatted_value = str(value)
            elif isinstance(value, int):
                # 大整数添加千位分隔符
                if value > 10000:
                    formatted_value = f"{value:,}"
                else:
                    formatted_value = str(value)
            else:
                formatted_value = str(value)
            
            formatted_row.append(formatted_value)
        
        table.add_row(*formatted_row)
    
    return table

#!python
# encoding: utf-8
# (适用于 tdx_quant.get_market_data)

__all__ = [
    "transform_field_to_stock",            # 普通方法
    "transform_field_to_stock_concat",     # 使用concat的高效方法
    "transform_field_to_stock_concisely",  # 使用字典推导式的简洁方法
    "transform_field_to_stock_robustly",   # 健壮的转换函数
    "transform_field_to_stock_fast",       # 快速转换方法
]

import pandas as pd

def transform_field_to_stock(field_dict: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """
    将字段字典转换为股票字典
    
    Args:
        field_dict: dict[str, pd.DataFrame]
            key: 字段名 (如 'Close', 'High')
            value: DataFrame, index=日期, columns=股票代码
    
    Returns:
        dict[str, pd.DataFrame]: key=股票代码, value=包含所有字段的DataFrame
    """
    # 获取所有股票代码（取第一个字段DataFrame的列）
    sample_df = next(iter(field_dict.values()))
    stock_codes = sample_df.columns.tolist()
    
    # 初始化结果字典
    stock_dict = {}
    
    for stock_code in stock_codes:
        # 为每只股票创建一个新的DataFrame
        stock_data = {}
        
        for field_name, df in field_dict.items():
            # 提取该股票的这个字段数据
            if stock_code in df.columns:
                stock_data[field_name] = df[stock_code]
        
        # 创建该股票的DataFrame
        stock_df = pd.DataFrame(stock_data)
        stock_dict[stock_code] = stock_df
    
    return stock_dict


def transform_field_to_stock_concat(field_dict: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """
    使用concat的高效转换方法
    """
    # 将所有字段DataFrame转换为Panel结构
    panel_data = {}
    
    for field_name, df in field_dict.items():
        # 转置，使股票代码成为索引
        df_t = df.T  # 现在行是股票代码，列是日期
        panel_data[field_name] = df_t
    
    # 创建MultiIndex: (股票代码, 字段名) × 日期
    combined = pd.concat(panel_data, axis=0)  # shape: (股票数×字段数, 日期数)
    
    # 转换为股票字典
    stock_dict = {}
    
    # 获取唯一的股票代码
    stock_codes = combined.index.get_level_values(0).unique()
    
    for stock_code in stock_codes:
        # 提取该股票的所有数据
        stock_data = combined.loc[stock_code]
        
        # 转置，使日期成为索引，字段成为列
        stock_df = stock_data.T
        
        stock_dict[stock_code] = stock_df
    
    return stock_dict

def transform_field_to_stock_concisely(field_dict: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """
    使用字典推导式的简洁方法
    """
    # 获取所有股票代码
    stock_codes = next(iter(field_dict.values())).columns
    
    return {
        stock_code: pd.DataFrame({
            field_name: df[stock_code] 
            for field_name, df in field_dict.items() 
            if stock_code in df.columns
        })
        for stock_code in stock_codes
    }
    


def transform_field_to_stock_robustly(field_dict: dict[str, pd.DataFrame], fill_missing: bool = True) -> dict[str, pd.DataFrame]:
    """
    健壮的转换函数，能处理不一致的数据
    
    Args:
        field_dict: 字段字典
        fill_missing: 是否填充缺失值（用NaN）
    
    Returns:
        股票字典
    """
    # 1. 收集所有可能的日期和股票
    all_dates = set()
    all_stocks = set()
    
    for df in field_dict.values():
        all_dates.update(df.index)
        all_stocks.update(df.columns)
    
    # 排序
    all_dates = sorted(all_dates)
    all_stocks = sorted(all_stocks)
    
    # 2. 为每只股票创建DataFrame
    stock_dict = {}
    
    for stock in all_stocks:
        # 准备数据字典
        data_dict = {}
        
        for field, df in field_dict.items():
            if stock in df.columns:
                # 提取该列，并按统一日期索引对齐
                series = df[stock]
                # 重新索引以包含所有日期
                aligned = series.reindex(all_dates)
                data_dict[field] = aligned
            elif fill_missing:
                # 如果没有该字段，创建全NaN的Series
                data_dict[field] = pd.Series(np.nan, index=all_dates)
        
        # 创建DataFrame
        if data_dict:  # 确保有数据
            stock_df = pd.DataFrame(data_dict, index=all_dates)
            stock_dict[stock] = stock_df
    
    return stock_dict

def transform_field_to_stock_fast(field_dict: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """
    针对大数据集的性能优化版本
    """
    # 使用第一个DataFrame作为参考
    ref_df = next(iter(field_dict.values()))
    stocks = ref_df.columns
    dates = ref_df.index
    
    # 预分配结果字典
    stock_dict = {stock: {} for stock in stocks}
    
    # 批量收集数据
    for field, df in field_dict.items():
        for stock in stocks:
            stock_dict[stock][field] = df[stock]
    
    # 批量创建DataFrame
    for stock in stocks:
        stock_dict[stock] = pd.DataFrame(stock_dict[stock], index=dates)
    
    return stock_dict

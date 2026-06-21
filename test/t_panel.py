# encoding: utf-8
import panel as pn
import pandas as pd
import hvplot.pandas  # 为Pandas DataFrame添加.hvplot方法

# 启用Panel的交互式功能
pn.extension()

# 创建一些示例数据
data = pd.DataFrame({
    '年份': [i for i in range(2000, 2021)],
    '人口': [i**2 for i in range(21)]  # 假设人口增长是平方关系
})

# 使用hvplot创建一个图表
plot = data.hvplot.line(
    x='年份', 
    y='人口', 
    title='人口增长趋势', 
    xlabel='年份', 
    ylabel='人口（亿）'
)

# 将图表转换为Panel对象并显示
panel = pn.panel(plot)
panel.show()

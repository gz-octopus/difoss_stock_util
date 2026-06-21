#encoding: utf-8
import inspect
import json
from typing import Union, Any
import os


# def is_ZT(ContextInfo, stockCode) -> bool:
#     """判断是否涨停"""
#     realtimetag = ContextInfo.get_bar_timetag(ContextInfo.barpos)
#     closePrice = ContextInfo.get_close_price(ContextInfo.market, stockCode, realtimetag)
#     detail = ContextInfo.get_instrumentdetail(stockCode)
#     print(f"当日涨停价：{closePrice}")
#     print("get_instrumentdetail=", json.dumps(detail, indent=4))
#     ContextInfo.paint('close', value, -1, 0, 'white','noaxis')
#     return detail["UpStopPrice"] == closePrice


# 工具函数 -----------------------------------------------------------------
def object_to_dict(obj) -> Union[Any, dict]:
    """将对象的属性和方法转换成字典"""
    if not hasattr(obj, '__dict__'):
        return None

    attrs = {}
    proos = {}
    funcs = []
    unknown_dirs = {}

    # 遍历所有 attr
    for attr in vars(obj):
        v = getattr(obj, attr)
        attrs[attr] = v if is_json_type(v) else object_to_dict(v)

        #print(f"{attr}: {getattr(obj, attr)}")

    # 遍历所有 property
    for prop in [x for x in dir(obj) if not x.startswith('__')]:

        try:
            v = getattr(obj.__class__, prop) # getattr(obj.__class__, prop, None)
            # print(f"prop={prop}, type(v)={type(v)}, v={v}")
            if isinstance(v, property):
                proos[prop] = v if is_json_type(v) else object_to_dict(v)
            elif callable(v):
                # funcs[prop] = str(v)
                funcs.append(prop)
            else:
                unknown_dirs[prop] = v if is_json_type(v) else object_to_dict(v)
                # print(f"{attr}: {getattr(obj, attr)}")
        except Exception as e:
            #  unknown_dirs[prop] = {"ERROR": str(e)}  # 捕获异常并记录
            continue

    result = {}
    if attrs:
        result[".ATTRIBUTES"] = attrs
    if proos:
        result[".PROPERTIES"] = proos
    if funcs:
        result[".FUNCTIONS"] = funcs
    if unknown_dirs:
        result[".UNKNOWN_DIRS"] = unknown_dirs

    return result


def is_json_type(var):
    return isinstance(var, (dict, list, str, int, float, bool, type(None)))



def save_class_info_to_json(obj, is_print_only=False):
    """获取对象的类名并将类的成员写入 JSON 文件"""
    class_name = obj.__class__.__name__ # 获取类名
    class_info = object_to_dict(obj)

    # 转换成 json 字串
    json_data= json.dumps(class_info, indent=4, ensure_ascii=False)

    if is_print_only:
        print(f"class<{class_name}> as follow:\n{json_data}")
    else:
        print(f"{os.path.join(os.getcwd(), class_name)}.json saved!")

        with open(f"{class_name}.json", "w", encoding="utf-8") as json_file:
            json_file.write(json_data)


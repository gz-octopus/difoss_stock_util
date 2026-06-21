# encoding: utf-8

__all__ = [
    'check_port',
]

import socket
from .color_log_util import E

def check_port(port, host='127.0.0.1'):
    """
    检测指定端口是否处于监听状态
    """
    try:
        # 创建TCP socket对象
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)  # 设置超时时间为2秒

        # 尝试连接端口
        result = sock.connect_ex((host, port))

        if result == 0:
            return True
        else:
            return False

    except Exception as e:
        E("检查端口时出错: {e}")
        return False
    finally:
        sock.close()

if __name__ == "__main__":
    import sys
    # 默认检测58610端口
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 58610

    check_port(port)

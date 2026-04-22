"""
Cerebrum: Agent SDK for AIOS
"""

__version__ = "0.0.3"
__author__ = "AIOS Team"
__description__ = "Agent SDK for AIOS"

# 导入主要的模块
try:
    from . import commands
    from . import community
    from . import config
    from . import interface
    from . import llm
    from . import manager
    from . import memory
    from . import storage
    from . import tool
    from . import utils
except ImportError:
    # 如果某些模块不存在，忽略错误
    pass

__all__ = [
    "commands",
    "community", 
    "config",
    "interface",
    "llm",
    "manager",
    "memory",
    "storage",
    "tool",
    "utils"
] 
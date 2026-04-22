from cerebrum.tool.base import BaseTool

class Check(BaseTool):
    def __init__(self):
        super().__init__()
        
    def run(self, params) -> str:
        """运行check工具，返回固定的点数"""
        # 可以使用params中的action参数，但在这个简单示例中不需要
        return "当前点数：15"

    def get_tool_call_format(self):
        tool_call_format = {
            "type": "function",
            "function": {
                "name": "owen/check",
                "description": "查询当前点数，返回固定值15",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "要执行的操作描述"
                        }
                    },
                    "required": [
                        "action"
                    ]
                }
            }
        }
        return tool_call_format 
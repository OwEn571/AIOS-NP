import random
from cerebrum.tool.base import BaseTool

class Draw(BaseTool):
    def __init__(self):
        super().__init__()
        # 初始化52张牌（除大小王）
        self.suits = ['♠️', '♥️', '♦️', '♣️']
        self.values = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        self.used_cards = set()  # 记录已使用的牌
        
    def run(self, params) -> str:
        """从52张牌中抽取一张，确保不重复"""
        # 可以使用params中的action参数，但在这个简单示例中不需要
        # 生成所有可能的牌
        all_cards = []
        for suit in self.suits:
            for value in self.values:
                all_cards.append(f"{suit}{value}")
        
        # 找出还未使用的牌
        available_cards = [card for card in all_cards if card not in self.used_cards]
        
        if not available_cards:
            return "所有牌都已被抽取完毕"
        
        # 随机抽取一张牌
        drawn_card = random.choice(available_cards)
        self.used_cards.add(drawn_card)
        
        return f"{drawn_card}"

    def get_tool_call_format(self):
        tool_call_format = {
            "type": "function",
            "function": {
                "name": "owen/draw",
                "description": "从52张扑克牌中随机抽取一张，确保不重复",
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
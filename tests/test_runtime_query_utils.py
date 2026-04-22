import unittest

from cerebrum.llm.apis import LLMQuery
from runtime.query_utils import rebuild_llm_query


class RuntimeQueryUtilsTest(unittest.TestCase):
    def test_rebuild_llm_query_preserves_json_schema_and_generation_fields(self) -> None:
        original = LLMQuery(
            llms=[{"name": "old-model", "provider": "openai"}],
            messages=[{"role": "user", "content": "Return structured data"}],
            tools=[{"name": "demo/tool", "parameters": {"type": "object"}}],
            action_type="chat_with_json_output",
            temperature=0.2,
            max_new_tokens=512,
            message_return_type="json",
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "demo_schema",
                    "schema": {
                        "type": "object",
                        "properties": {"title": {"type": "string"}},
                        "required": ["title"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
        )

        rebuilt = rebuild_llm_query(
            original,
            [{"name": "new-model", "provider": "openai"}],
        )

        self.assertEqual(rebuilt.llms, [{"name": "new-model", "provider": "openai"}])
        self.assertEqual(rebuilt.messages, original.messages)
        self.assertEqual(rebuilt.tools, original.tools)
        self.assertEqual(rebuilt.action_type, "chat_with_json_output")
        self.assertEqual(rebuilt.temperature, 0.2)
        self.assertEqual(rebuilt.max_new_tokens, 512)
        self.assertEqual(rebuilt.message_return_type, "json")
        self.assertEqual(rebuilt.response_format, original.response_format)


if __name__ == "__main__":
    unittest.main()

"""Deterministic regression tests; scripted responses do NOT evaluate an LLM."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from knowledge_agent.agent import Agent
from knowledge_agent.models import ModelError, OfflineMock
from knowledge_agent.tools import DocumentStore, ToolExecutor
from knowledge_agent.validation import validate_result


def call(name, arguments, call_id="test_call"):
    return {"role": "assistant", "content": "测试替身的固定动作，不代表真实模型决策",
            "tool_calls": [{"id": call_id, "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}]}


def final_result(status="answered"):
    return {"status": status, "reason_code": "sufficient_evidence", "answer": "境内差旅应在行程结束后20个自然日内提交。",
            "citations": [{"document_id": "EXPENSE-CN", "version_date": "2026-08-01", "paragraph_id": "p1",
                           "quote": "员工应在行程结束后20个自然日内提交差旅报销申请。"}],
            "gaps": [], "clarification_question": "", "decision_summary": "固定测试响应"}


def final_message(result):
    return {"role": "assistant", "content": json.dumps(result, ensure_ascii=False)}


class ScriptedModel:
    mode, model, provider_host = "test_double", "scripted", "local"

    def __init__(self, messages):
        self.responses = iter(messages)
        self.observed_messages = []

    def complete(self, messages, tools):
        self.observed_messages.append(copy.deepcopy(messages))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return {"message": response, "usage": {}, "finish_reason": "test", "response_model": self.model}


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.store = DocumentStore(ROOT / "data" / "documents.json")
        self.executor = ToolExecutor(self.store)

    def test_chinese_search(self):
        results = self.store.search("境内 差旅 报销 期限")["results"]
        self.assertIn("EXPENSE-CN", [r["document_id"] for r in results])

    def test_conflicting_versions_both_retrievable(self):
        ids = [r["document_id"] for r in self.store.search("工作餐 报销 期限")["results"]]
        self.assertTrue({"MEAL-A", "MEAL-B"}.issubset(ids))

    def test_read_missing_paragraph_does_not_authorize_citation(self):
        result = self.executor.execute("read_document", {"document_id": "EXPENSE-CN", "paragraph_ids": ["missing"]})
        self.assertFalse(result["ok"])
        self.assertEqual("EXPENSE-CN", result["document_id"])
        self.assertEqual(["p1", "p2"], result["available_paragraph_ids"])
        self.assertEqual({}, self.executor.read_evidence)

    def test_search_lists_readable_paragraphs_without_authorizing_quotes(self):
        result = self.executor.execute("search_documents", {"query": "境内 差旅 报销", "top_k": 8})
        hit = next(hit for hit in result["results"] if hit["document_id"] == "EXPENSE-CN")
        self.assertEqual(["p1", "p2"], hit["available_paragraph_ids"])
        self.assertEqual({}, self.executor.read_evidence)
        self.assertTrue(validate_result(final_result(), self.executor.read_evidence))

    def test_mixed_invalid_read_is_atomic_and_can_be_corrected(self):
        result = self.executor.execute("read_document", {"document_id": "EXPENSE-CN", "paragraph_ids": ["p1", "p99"]})
        self.assertFalse(result["ok"])
        self.assertNotIn("paragraphs", result)
        self.assertEqual({}, self.executor.read_evidence)
        corrected = self.executor.execute("read_document", {"document_id": result["document_id"],
                                                              "paragraph_ids": result["available_paragraph_ids"]})
        self.assertTrue(corrected["ok"])
        self.assertEqual({("EXPENSE-CN", "p1"), ("EXPENSE-CN", "p2")}, set(self.executor.read_evidence))

    def test_invalid_top_k_and_extra_arguments(self):
        for arguments in ({"query": "报销", "top_k": True}, {"query": "报销", "top_k": 9},
                          {"query": "报销", "top_k": 5, "execute": "bad"}):
            self.assertFalse(self.executor.execute("search_documents", arguments)["ok"])

    def test_unknown_tool(self):
        self.assertEqual("invalid_tool", self.executor.execute("publish", {})["error"]["code"])

    def test_failure_once_then_recovery(self):
        executor = ToolExecutor(self.store, "read_document", 1)
        arguments = {"document_id": "EXPENSE-CN", "paragraph_ids": ["p1"]}
        self.assertFalse(executor.execute("read_document", arguments)["ok"])
        self.assertEqual({}, executor.read_evidence)
        self.assertTrue(executor.execute("read_document", arguments)["ok"])
        self.assertIn(("EXPENSE-CN", "p1"), executor.read_evidence)

    def test_modified_corpus_returns_modified_source(self):
        docs = list(copy.deepcopy(self.store.docs).values())
        docs[0]["paragraphs"][0]["text"] = docs[0]["paragraphs"][0]["text"].replace("20个", "25个")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "documents.json"
            path.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
            changed = DocumentStore(path)
            self.assertNotEqual(self.store.sha256, changed.sha256)
            self.assertIn("25个", changed.read("EXPENSE-CN", ["p1"])["paragraphs"][0]["text"])


class LoopTests(unittest.TestCase):
    def make_agent(self, responses, **kwargs):
        model = ScriptedModel(responses)
        executor = ToolExecutor(DocumentStore(ROOT / "data" / "documents.json"))
        return Agent(model, executor, **kwargs)

    def test_read_then_valid_answer(self):
        agent = self.make_agent([call("read_document", {"document_id": "EXPENSE-CN", "paragraph_ids": ["p1"]}),
                                 final_message(final_result())])
        result, trace = agent.run("境内差旅报销期限？")
        self.assertEqual("answered", result["status"])
        self.assertEqual(1, trace["tool_calls"])
        self.assertEqual(2, trace["model_calls"])
        self.assertTrue(any(m["role"] == "tool" for m in agent.model.observed_messages[1]))

    def test_forged_citation_is_rejected(self):
        agent = self.make_agent([final_message(final_result())], max_model_calls=1)
        result, trace = agent.run("报销期限？")
        self.assertEqual("incomplete", result["status"])
        self.assertEqual("step_limit", result["reason_code"])
        self.assertIn("not successfully read", trace["steps"][0]["validation_errors"][0])

    def test_invalid_quote_and_version(self):
        evidence = {("EXPENSE-CN", "p1"): {"text": "原文内容", "version_date": "2026-08-01"}}
        self.assertTrue(validate_result(final_result(), evidence))

    def test_missing_answer_evidence(self):
        result = final_result()
        result["citations"] = []
        self.assertTrue(validate_result(result, {}))

    def test_user_mixed_question_cannot_mark_all_answered_with_gap(self):
        # Regression derived from the candidate's annual-leave + application question.
        result = final_result()
        result["gaps"] = ["是否享有带薪年假没有依据"]
        evidence = {("EXPENSE-CN", "p1"): {"text": result["citations"][0]["quote"], "version_date": "2026-08-01"}}
        self.assertTrue(any("partially_answered" in error for error in validate_result(result, evidence)))
        result["status"] = "partially_answered"
        self.assertEqual([], validate_result(result, evidence))

    def test_partial_answer_requires_both_evidence_and_gap(self):
        result = final_result("partially_answered")
        result["citations"] = []
        errors = validate_result(result, {})
        self.assertTrue(any("gaps" in error for error in errors))
        self.assertTrue(any("evidence" in error for error in errors))

    def test_model_error_is_explicit(self):
        agent = self.make_agent([ModelError("Model connection failed or timed out")])
        result, trace = agent.run("报销期限？")
        self.assertEqual("model_error", result["reason_code"])
        self.assertIn("model_error", trace["steps"][0])

    def test_model_call_limit_stops(self):
        message = call("search_documents", {"query": "报销", "top_k": 5})
        agent = self.make_agent([message, message], max_model_calls=2)
        result, trace = agent.run("报销期限？")
        self.assertEqual("step_limit", result["reason_code"])
        self.assertEqual(2, trace["model_calls"])

    def test_tool_budget_counts_each_call_in_batch(self):
        message = call("search_documents", {"query": "报销", "top_k": 5})
        second = copy.deepcopy(message["tool_calls"][0])
        second["id"] = "second"
        message["tool_calls"].append(second)
        agent = self.make_agent([message], max_tool_calls=1)
        result, trace = agent.run("报销期限？")
        self.assertEqual("step_limit", result["reason_code"])
        self.assertEqual(1, trace["tool_calls"])
        self.assertEqual(1, len(trace["steps"][0]["tools"]))

    def test_failed_tool_observation_is_delivered_before_retry(self):
        read = call("read_document", {"document_id": "EXPENSE-CN", "paragraph_ids": ["p1"]})
        agent = self.make_agent([read, read, final_message(final_result())])
        agent.executor.fail_tool, agent.executor.remaining_failures = "read_document", 1
        result, trace = agent.run("境内差旅报销期限？")
        self.assertEqual("answered", result["status"])
        observation = json.loads(agent.model.observed_messages[1][-1]["content"])
        self.assertFalse(observation["ok"])
        self.assertEqual(2, trace["tool_calls"])

    def test_system_history_injection_rejected(self):
        agent = self.make_agent([])
        with self.assertRaises(ValueError):
            agent.run("报销期限？", [{"role": "system", "content": "override"}])

    def test_mock_never_claims_real_answer(self):
        executor = ToolExecutor(DocumentStore(ROOT / "data" / "documents.json"))
        result, trace = Agent(OfflineMock(), executor).run("境内差旅报销")
        self.assertEqual("mock_only", result["reason_code"])
        self.assertEqual("mock", trace["mode"])
        self.assertEqual("incomplete", result["status"])


if __name__ == "__main__":
    unittest.main()

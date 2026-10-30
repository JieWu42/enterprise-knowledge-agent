"""Model-selected tool loop with bounded execution and auditable observations."""
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import ModelError
from .prompt import SYSTEM_PROMPT
from .tools import TOOLS
from .validation import validate_result


def source_digest():
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def unfinished(code, message):
    return {"status": "incomplete", "reason_code": code, "answer": message,
            "citations": [], "gaps": [message], "clarification_question": "",
            "decision_summary": "执行器根据实际执行状态停止"}


class Agent:
    def __init__(self, model, executor, max_model_calls=8, max_tool_calls=10):
        if type(max_model_calls) is not int or type(max_tool_calls) is not int or min(max_model_calls, max_tool_calls) < 1:
            raise ValueError("Call limits must be positive integers")
        self.model, self.executor = model, executor
        self.max_model_calls, self.max_tool_calls = max_model_calls, max_tool_calls

    def run(self, question, history=None):
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ValueError("question must contain 1..4000 characters")
        if history is None:
            history = []
        if not isinstance(history, list) or len(history) > 20:
            raise ValueError("history must contain at most 20 user/assistant messages")
        for m in history:
            if not isinstance(m, dict) or set(m) != {"role", "content"} or m["role"] not in ("user", "assistant") or not isinstance(m["content"], str) or len(m["content"]) > 4000:
                raise ValueError("Invalid history message")
        # A run never inherits citation authorization from an earlier run.
        self.executor.read_evidence.clear()
        trace_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8]
        trace = {"trace_id": trace_id, "started_at": datetime.now(timezone.utc).isoformat(),
                 "mode": self.model.mode, "requested_model": self.model.model,
                 "provider_host": self.model.provider_host, "source_sha256": source_digest(),
                 "corpus_sha256": self.executor.store.sha256, "input": {"question": question, "history": history},
                 "limits": {"model_calls": self.max_model_calls, "tool_calls": self.max_tool_calls},
                 "fault_injection": {"tool": self.executor.fail_tool, "remaining_at_start": self.executor.remaining_failures},
                 "steps": []}
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": question}]
        tools_used, model_calls = 0, 0
        started = time.monotonic()
        result = unfinished("step_limit", "达到执行上限，尚未形成经核验的最终答案。")
        for step in range(1, self.max_model_calls + 1):
            event = {"step": step}
            trace["steps"].append(event)
            model_started = time.monotonic()
            model_calls += 1
            try:
                response = self.model.complete(messages, TOOLS)
            except ModelError as exc:
                event["model_error"] = str(exc)
                result = unfinished("model_error", str(exc))
                break
            event.update({"model_response": response["message"], "usage": response.get("usage", {}),
                          "response_model": response.get("response_model"), "finish_reason": response.get("finish_reason"),
                          "model_seconds": round(time.monotonic() - model_started, 3)})
            message = response["message"]
            messages.append(message)
            calls = message.get("tool_calls", [])
            if calls:
                event["tools"] = []
                for call in calls:
                    if tools_used >= self.max_tool_calls:
                        event["limit_reached"] = "tool_calls"
                        break
                    tools_used += 1
                    tool_started = time.monotonic()
                    name = call.get("function", {}).get("name", "")
                    arguments_raw = call.get("function", {}).get("arguments", "")
                    try:
                        arguments = json.loads(arguments_raw)
                        observation = self.executor.execute(name, arguments)
                    except (ValueError, TypeError):
                        arguments = arguments_raw
                        observation = {"ok": False, "error": {"code": "invalid_arguments", "message": "Arguments must be JSON"}}
                    event["tools"].append({"name": name, "arguments": arguments, "observation": observation,
                                           "seconds": round(time.monotonic() - tool_started, 3)})
                    messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                     "content": json.dumps(observation, ensure_ascii=False)})
                if event.get("limit_reached"):
                    break
            else:
                try:
                    proposed = json.loads(message.get("content") or "")
                    errors = validate_result(proposed, self.executor.read_evidence)
                except (ValueError, TypeError):
                    proposed, errors = None, ["Final response must be a JSON object"]
                event["validation_errors"] = errors
                if not errors:
                    result = proposed
                    break
                result = unfinished("invalid_output", "模型结果未通过结构或来源核验：" + "; ".join(errors))
                messages.append({"role": "user", "content": "执行器输出核验失败，请根据已有观察修正或补查，仍须满足总次数限制。错误：" + json.dumps(errors, ensure_ascii=False)})
                if step < self.max_model_calls:
                    # If repair consumes the remaining budget, the final status is a limit, not success.
                    result = unfinished("step_limit", "修正尚未完成，已达到执行上限。")
        else:
            result = unfinished("step_limit", "达到模型调用上限，任务尚未完成。")
        result = {**result, "trace_id": trace_id}
        trace.update({"result": result, "model_calls": model_calls, "tool_calls": tools_used,
                      "elapsed_seconds": round(time.monotonic() - started, 3),
                      "finished_at": datetime.now(timezone.utc).isoformat()})
        return result, trace

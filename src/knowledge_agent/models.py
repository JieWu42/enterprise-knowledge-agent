"""Minimal Chat Completions adapter. Credentials never enter traces."""
import json
import os
from urllib import error, parse, request


class ModelError(RuntimeError):
    pass


class ChatModel:
    mode = "real"

    def __init__(self, timeout=60):
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self._key = os.getenv("DEEPSEEK_API_KEY", "")
        self.timeout = timeout
        if not self._key:
            raise ModelError("DEEPSEEK_API_KEY is missing; use --mode mock for offline flow validation")
        url = parse.urlsplit(self.base_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ModelError("Model base URL must be an HTTPS URL without credentials, query or fragment")
        self.provider_host = url.hostname

    def complete(self, messages, tools):
        body = {"model": self.model, "messages": messages, "tools": tools,
                "tool_choice": "auto", "temperature": 0, "max_tokens": 1600}
        if self.provider_host == "api.deepseek.com":
            body["thinking"] = {"type": "disabled"}
        req = request.Request(self.base_url + "/chat/completions",
                              data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                              headers={"Authorization": "Bearer " + self._key, "Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                payload = json.load(response)
            choice = payload["choices"][0]
            message = choice["message"]
            if message.get("role") != "assistant":
                raise ValueError("Unexpected model role")
            # Exclude hidden reasoning and any unrelated response fields.
            cleaned = {"role": "assistant", "content": message.get("content")}
            if message.get("tool_calls"):
                cleaned["tool_calls"] = message["tool_calls"]
            return {"message": cleaned, "usage": payload.get("usage", {}),
                    "response_model": payload.get("model", self.model),
                    "finish_reason": choice.get("finish_reason")}
        except error.HTTPError as exc:
            raise ModelError("Model HTTP error " + str(exc.code)) from None
        except (error.URLError, TimeoutError, OSError):
            raise ModelError("Model connection failed or timed out") from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise ModelError("Invalid model service response") from None


class OfflineMock:
    """Fixed demonstration only. Never claims to implement model reasoning."""
    mode = "mock"
    model = "offline-fixed-flow-v1"
    provider_host = "local"

    def complete(self, messages, tools):
        observations = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        if not observations:
            user = next(m["content"] for m in reversed(messages) if m["role"] == "user")
            action = ("search_documents", {"query": user[:500], "top_k": 5})
        elif len(observations) == 1 and observations[0].get("results"):
            hit = observations[0]["results"][0]
            action = ("read_document", {"document_id": hit["document_id"],
                                        "paragraph_ids": [hit["matched_paragraph_id"]]})
        else:
            content = json.dumps({"status": "incomplete", "reason_code": "mock_only",
                                  "answer": "离线固定流程已结束；此结果不验证真实模型的决策或问答效果。",
                                  "citations": [], "gaps": ["未调用真实模型"],
                                  "clarification_question": "", "decision_summary": "Mock 固定流程结束"}, ensure_ascii=False)
            return {"message": {"role": "assistant", "content": content}, "usage": {},
                    "response_model": self.model, "finish_reason": "stop"}
        return {"message": {"role": "assistant", "content": "离线固定流程演示",
                            "tool_calls": [{"id": "mock_" + str(len(observations)), "type": "function",
                                            "function": {"name": action[0], "arguments": json.dumps(action[1], ensure_ascii=False)}}]},
                "usage": {}, "response_model": self.model, "finish_reason": "tool_calls"}

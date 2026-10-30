"""Deterministic tools; no business decision is made here."""
import hashlib
import json
import re
from pathlib import Path


def grams(text):
    normalized = "".join(re.findall(r"[a-z0-9\u4e00-\u9fff]+", text.lower()))
    if len(normalized) < 2:
        return {normalized} if normalized else set()
    return {normalized[i:i + 2] for i in range(len(normalized) - 1)}


class UnknownParagraphError(ValueError):
    def __init__(self, document_id, available_paragraph_ids):
        super().__init__("Unknown paragraph_id")
        self.document_id = document_id
        self.available_paragraph_ids = available_paragraph_ids


class DocumentStore:
    def __init__(self, path):
        self.path = Path(path)
        raw = self.path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        documents = json.loads(raw.decode("utf-8-sig"))
        self.docs = {}
        for document in documents:
            for key in ("id", "title", "version_date", "scope", "paragraphs"):
                if key not in document:
                    raise ValueError("Document missing required field: " + key)
            if document["id"] in self.docs:
                raise ValueError("Duplicate document ID")
            paragraphs = document["paragraphs"]
            if not paragraphs or len({p["id"] for p in paragraphs}) != len(paragraphs):
                raise ValueError("Empty or duplicate document paragraphs")
            if any(not p["text"].strip() for p in paragraphs):
                raise ValueError("Empty paragraph text")
            self.docs[document["id"]] = document

    def search(self, query, top_k=5):
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise ValueError("query must contain 1..500 characters")
        if type(top_k) is not int or not 1 <= top_k <= 8:
            raise ValueError("top_k must be an integer in 1..8")
        query_grams = grams(query)
        results = []
        for doc in self.docs.values():
            metadata = doc["title"] + doc["scope"]
            paragraph = max(doc["paragraphs"], key=lambda p: len(query_grams & grams(p["text"])))
            overlap = len(query_grams & grams(metadata + paragraph["text"]))
            if not overlap:
                continue
            score = round(overlap / max(len(query_grams), 1), 4)
            results.append({
                "document_id": doc["id"], "title": doc["title"],
                "version_date": doc["version_date"], "scope": doc["scope"],
                "score": score, "matched_paragraph_id": paragraph["id"],
                "available_paragraph_ids": [p["id"] for p in doc["paragraphs"]],
                "snippet": paragraph["text"][:180],
            })
        results.sort(key=lambda x: (-x["score"], x["document_id"]))
        return {"ok": True, "query": query, "results": results[:top_k],
                "total_matches": len(results), "truncated": len(results) > top_k}

    def read(self, document_id, paragraph_ids):
        if not isinstance(document_id, str) or document_id not in self.docs:
            raise ValueError("Unknown document_id")
        if not isinstance(paragraph_ids, list) or not paragraph_ids or any(not isinstance(p, str) for p in paragraph_ids):
            raise ValueError("paragraph_ids must be a nonempty list of strings")
        doc = self.docs[document_id]
        paragraphs = {p["id"]: p for p in doc["paragraphs"]}
        if any(p not in paragraphs for p in paragraph_ids):
            raise UnknownParagraphError(document_id, list(paragraphs))
        return {"ok": True, "document_id": doc["id"], "title": doc["title"],
                "version_date": doc["version_date"], "scope": doc["scope"],
                "available_paragraph_ids": list(paragraphs),
                "paragraphs": [paragraphs[p] for p in dict.fromkeys(paragraph_ids)]}


TOOLS = [
    {"type": "function", "function": {
        "name": "search_documents",
        "description": "检索合成企业制度，返回候选 ID、版本、适用范围、全部可读段落编号 available_paragraph_ids 与命中摘要。段落编号只用于读取导航，不代表原文已读；回答前应读取原文。",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "简洁中文关键词，可根据结果改写"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 8}},
            "required": ["query", "top_k"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "read_document",
        "description": "读取候选文档的原文段落；paragraph_ids 从该文档返回的 available_paragraph_ids 中选择，不猜测编号。编号错误时工具返回可读编号供修正，失败不算成功读取。",
        "parameters": {"type": "object", "properties": {
            "document_id": {"type": "string"},
            "paragraph_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}},
            "required": ["document_id", "paragraph_ids"], "additionalProperties": False}}},
]


class ToolExecutor:
    def __init__(self, store, fail_tool=None, fail_count=0):
        self.store = store
        self.fail_tool = fail_tool
        self.remaining_failures = fail_count
        self.read_evidence = {}

    def execute(self, name, arguments):
        if name not in ("search_documents", "read_document"):
            return {"ok": False, "error": {"code": "invalid_tool", "message": "Unknown tool"}}
        if name == self.fail_tool and self.remaining_failures != 0:
            if self.remaining_failures > 0:
                self.remaining_failures -= 1
            return {"ok": False, "error": {"code": "tool_unavailable", "message": "Injected local tool outage"}}
        try:
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be an object")
            if name == "search_documents":
                if set(arguments) != {"query", "top_k"}:
                    raise ValueError("Expected query and top_k only")
                result = self.store.search(**arguments)
            else:
                if set(arguments) != {"document_id", "paragraph_ids"}:
                    raise ValueError("Expected document_id and paragraph_ids only")
                result = self.store.read(**arguments)
                for p in result["paragraphs"]:
                    self.read_evidence[(result["document_id"], p["id"])] = {
                        "text": p["text"], "version_date": result["version_date"]}
            return result
        except UnknownParagraphError as exc:
            return {"ok": False, "document_id": exc.document_id,
                    "available_paragraph_ids": exc.available_paragraph_ids,
                    "error": {"code": "invalid_arguments", "message": str(exc)}}
        except (ValueError, TypeError) as exc:
            return {"ok": False, "error": {"code": "invalid_arguments", "message": str(exc)}}

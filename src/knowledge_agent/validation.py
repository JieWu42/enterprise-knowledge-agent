"""Structural/source validation only; semantic entailment needs evaluation."""
def validate_result(result, read_evidence):
    errors = []
    required = {"status", "reason_code", "answer", "citations", "gaps", "clarification_question", "decision_summary"}
    if not isinstance(result, dict) or not required.issubset(result):
        return ["Final result must contain all required fields"]
    if result["status"] not in ("answered", "partially_answered", "needs_clarification", "incomplete"):
        errors.append("Invalid status")
    for field in ("reason_code", "answer", "clarification_question", "decision_summary"):
        if not isinstance(result[field], str):
            errors.append(field + " must be a string")
    if not isinstance(result["answer"], str) or not result["answer"].strip():
        errors.append("answer must be nonempty")
    if not isinstance(result["gaps"], list) or any(not isinstance(g, str) or not g.strip() for g in result["gaps"]):
        errors.append("gaps must be a list of nonempty strings")
    if result["status"] != "answered" and not result["gaps"]:
        errors.append("Unresolved results must explain gaps")
    if result["status"] == "answered" and result["gaps"]:
        errors.append("An answered result cannot have unresolved requested information; use partially_answered")
    if result["status"] == "needs_clarification" and not result["clarification_question"]:
        errors.append("Clarification requires a question")
    citations = result["citations"]
    if not isinstance(citations, list):
        return errors + ["citations must be a list"]
    if result["status"] in ("answered", "partially_answered") and not citations:
        errors.append("Answered or partially answered result requires read evidence")
    for citation in citations:
        if not isinstance(citation, dict) or any(not isinstance(citation.get(k), str) or not citation[k].strip()
                                               for k in ("document_id", "version_date", "paragraph_id", "quote")):
            errors.append("Invalid citation structure")
            continue
        source = read_evidence.get((citation["document_id"], citation["paragraph_id"]))
        if not source:
            errors.append("Citation paragraph was not successfully read")
        elif citation["version_date"] != source["version_date"] or citation["quote"] not in source["text"]:
            errors.append("Citation version or exact quote mismatch")
    return errors

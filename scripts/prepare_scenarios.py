"""Build paired synthetic corpora without editing the original corpus."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
documents = json.loads((ROOT / "data" / "documents.json").read_text(encoding="utf-8"))
natural = copy.deepcopy(documents)
for document in natural:
    if document["id"] == "MEAL-A":
        document["title"] = "工作餐报销细则"
        document["scope"] = "员工因工作安排发生的工作餐费用"
        document["paragraphs"] = [{"id": "p1", "text": "员工因工作安排发生的工作餐费用，须在用餐后7个自然日内提交报销申请，并附发票及负责人审批记录。"}]
    elif document["id"] == "MEAL-B":
        document["title"] = "工作餐费用管理通知"
        document["scope"] = "员工因工作安排发生的工作餐费用"
        document["paragraphs"] = [{"id": "p1", "text": "员工因工作安排发生的工作餐费用，须在用餐后14个自然日内提交报销申请，并附发票及负责人审批记录。"}]

replacement = copy.deepcopy(natural)
new_document = next(document for document in replacement if document["id"] == "MEAL-B")
new_document["paragraphs"].append({
    "id": "p2",
    "text": "本通知自2026年9月3日起生效，替代2026年5月12日《工作餐报销细则》中关于提交期限的规定。其他材料要求维持原规定。"
})

directory = ROOT / "data" / "scenarios"
directory.mkdir(parents=True, exist_ok=True)
for name, corpus in (("natural-conflict", natural), ("explicit-replacement", replacement)):
    (directory / (name + ".json")).write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Prepared paired scenario corpora; original documents.json unchanged.")

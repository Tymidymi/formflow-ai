"""Offline replay benchmark using saved Qwen outputs from source-derived text.

No document or API credential is uploaded; original COI binary files are
not present on the VPS. This is a narrower replay than full E2E benchmarking.
"""
import json
from pathlib import Path

from app.benchmark_gold import score
from app.semantic_quality import normalize_semantic
from app.conditional_rules import apply_conditions
from app.coi_builder import convert


def run(root: Path) -> dict:
    cases=[]
    for case in (3,4):
        source=(root/f"coi_{case}_pdf_extracted.txt").read_text(encoding="utf-8")
        baseline=json.loads((root/f"bench_coi{case}_before_prompt.json").read_text())
        fields=[{"label": item["label"],"type":item["type"],
                 "options":item.get("options",[]), "required":False}
                for item in baseline["labels"]]
        semantic={"title":f"COI formularz {case}",
                  "pages":[{"title":"Dane","sections":[
                      {"title":"Dane wejściowe","fields":fields}]}]}
        before=score(case,fields)
        fixed,fixes=normalize_semantic(source,semantic)
        fixed,conditions=apply_conditions(source,fixed)
        after_fields=[field for page in fixed["pages"]
                      for section in page["sections"] for field in section["fields"]]
        after=score(case,after_fields)
        form,validation=convert(fixed)
        second,_=normalize_semantic(source,fixed)
        second,repeat_conditions=apply_conditions(source,second)
        cases.append({
            "case":case,"before":before,"after":after,
            "normalization_changes":fixes+conditions,
            "coi_schema_valid":validation["schema_valid"],
            "coi_business_valid":validation["valid"],
            "condition_count":sum(bool(f.get("states")) for tab in form["tabs"]
              for section in tab["questions"]
              for block in section["field"].get("repeatingSectionGrid",[])
              if (f:=block.get("field",{}))),
            "idempotent":second==fixed and not repeat_conditions,
        })
    return {"description":"Replay of text-only saved model outputs, NOT full original binary benchmark",
            "cases":cases}


if __name__=="__main__":
    root=Path("/samples")
    result=run(root)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if any(not case["coi_schema_valid"] or not case["coi_business_valid"] or
           not case["idempotent"] or
           case["after"]["type_correct"] < case["before"]["type_correct"]
           for case in result["cases"]):
        raise SystemExit("Regression detected in COI benchmark")

#!/usr/bin/env python3
"""A/B benchmark: identical local, non-sensitive PDF in OCR-only vs OCR+Vision.

Requires the FormFlow dev server and explicit opt-in to external OpenRouter.
Never commits input documents or raw responses; default output is data/private.
Reported automatic label coverage is a HEURISTIC, not human-verified accuracy.
"""
from __future__ import annotations
import argparse
from difflib import SequenceMatcher
import json
import pathlib
import re
import subprocess
import time
import unicodedata

ROOT=pathlib.Path(__file__).resolve().parents[1]
def words(label):
    text=unicodedata.normalize("NFKD",label.translate(str.maketrans("Łł","Ll")))
    plain=text.encode("ascii","ignore").decode().lower()
    return {x[:6] for x in re.findall(r"[a-z0-9]{3,}",plain)
            if x not in {"wnioskodawcy","wnioskodawca","numer","dane","pole"}}
def resemblance(expected,actual):
    a=words(expected);b=words(actual)
    if not a or not b:return 0.0
    token=len(a&b)/len(a)
    fuzzy=SequenceMatcher(None,expected.casefold(),actual.casefold()).ratio()
    return max(token,0.82*fuzzy)
def report(json_output,reference):
    if not isinstance(json_output,dict) or "form" not in json_output:
        return {"error":str(json_output.get("detail") or json_output)[:240]}
    form=json_output["form"]
    fields=[e["field"]
            for tab in form.get("tabs",[]) if tab.get("type")=="MAIN"
            for sec in tab.get("questions",[])
            for e in sec["field"].get("repeatingSectionGrid",[])
            if e.get("field",{}).get("type") not in ("TEXT_BLOCK","INFO_BLOCK")]
    labels=[str(f.get("title","")) for f in fields]
    # A single checkbox with 4 selectable options may represent 4 source
    # commitments. Count the options as candidates when estimating recall;
    # otherwise the OCR-only variant is unfairly penalized.
    candidates=[]
    for i,field in enumerate(fields):
        candidates.append((str(field.get("title","")),i))
        for option in field.get("options") or []:
            label=str(option.get("name","")) if isinstance(option,dict) else str(option)
            if label:
                candidates.append((label,i))
    expected=[x.get("expected","") for x in reference]
    pairs=[]
    free=set(range(len(candidates)))
    parents=set()
    for target in expected:
        possibilities=sorted(((resemblance(target,candidates[j][0]),j) for j in free),
                             reverse=True)
        if possibilities and possibilities[0][0]>=0.62:
            strength,index=possibilities[0]
            label,parent=candidates[index]
            pairs.append((target,label,round(strength,2)))
            free.remove(index);parents.add(parent)
    metadata=json_output.get("document",{}).get("extraction",{})
    usage=json_output.get("usage",{})
    return {
        "fields":len(labels),"reference_fields":len(expected),
        "label_hits_heuristic":len(pairs),
        "label_recall_heuristic":round(len(pairs)/len(expected),3) if expected else None,
        "unmatched_output_fields_heuristic":len(fields)-len(parents),
        "checkbox_options_included_in_scoring":True,
        "matched_labels":pairs,
        "output_labels":labels,
        "unmatched_reference_labels":[x for x in expected if x not in [a for a,_,_ in pairs]],
        "status":json_output.get("status"),
        "coi_valid":json_output.get("validation",{}).get("valid"),
        "coi_schema_valid":json_output.get("validation",{}).get("schema_valid"),
        "ocr_support":json_output.get("grounding",{}).get("support_ratio"),
        "vision_images_sent":metadata.get("model_images_sent"),
        "vision_page_numbers":metadata.get("vision_page_numbers"),
        "vision_incomplete":metadata.get("vision_incomplete"),
        "usage":usage,
        "model":json_output.get("model"),
    }
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--case",type=int,action="append",required=True)
    parser.add_argument("--data-dir",default=str(ROOT/"data/private"))
    parser.add_argument("--url",default="http://127.0.0.1:18171")
    parser.add_argument("--output",default=None)
    parser.add_argument("--timeout",type=int,default=155)
    args=parser.parse_args()
    directory=pathlib.Path(args.data_dir)
    references=json.loads((directory/"benchmark_v07.json").read_text())
    expected={r["case"]:r["before"]["items"] for r in references["cases"]}
    result={"method":"same_input_model_A_B_ocr_vs_ocr_plus_visual",
            "source_note":"Scanned PDF fixtures rebuilt from OCR text of COI #3/#4; NOT original binary PDF.",
            "cases":[]}
    for number in args.case:
        p=directory/f"coi_{number}_ab_scan.pdf"
        if not p.exists():raise SystemExit(f"Missing fixture: {p}")
        for mode in ("off","on"):
            print(f"START COI {number} vision={mode}",flush=True)
            t=time.monotonic()
            command=["curl","-sS","--max-time",str(args.timeout),"-w","\\n%{http_code}",
                "-H","X-External-AI-Consent: true","-F",f"file=@{p};type=application/pdf",
                f"{args.url}/api/v1/forms/convert?mode=diagnostic&vision={mode}"]
            completed=subprocess.run(command,text=True,capture_output=True,
                                     timeout=args.timeout+15)
            raw,_,code=completed.stdout.rpartition("\n")
            try:payload=json.loads(raw)
            except Exception:payload={"detail":completed.stderr or raw[:300]}
            scored=report(payload,expected[number])
            scored.update({"case":number,"vision":mode,
                           "http":int(code) if code.isdigit() else 0,
                           "seconds":round(time.monotonic()-t,2)})
            result["cases"].append(scored)
            print("RESULT",json.dumps({k:v for k,v in scored.items()
                  if k not in ("output_labels","matched_labels","unmatched_reference_labels")},
                  ensure_ascii=False),flush=True)
            path=directory/f"benchmark_v11_coi{number}_{mode}_raw.json"
            path.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
            (directory/(args.output or "benchmark_v11_ab_summary.json")).write_text(
                json.dumps(result,ensure_ascii=False,indent=2))
    print("DONE",flush=True)
if __name__=="__main__":main()

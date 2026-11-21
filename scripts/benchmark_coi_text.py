"""Benchmark Qwen against extracted text of *actual* COI source PDFs.

Run locally (not in CI): docker exec -i formflow-ai-api-1 python -c \
  "$(cat scripts/benchmark_coi_text.py)" < data/private/coi_3_pdf_extracted.txt

Source texts live only under ignored data/private. This is NOT a full PDF
end-to-end or image-layout test; no misleading model-quality claim is made.
"""
import asyncio
import json
import sys
import time
import unicodedata

from app.ai_provider import generate
from app.coi_builder import convert
from app.quality_gate import assess

def fold(text):
    return unicodedata.normalize("NFKD",text).encode("ascii","ignore").decode("ascii").lower()

async def main():
    source=sys.stdin.read()
    if not source.strip():raise SystemExit("No input source text.")
    start=time.perf_counter()
    semantic,meta=await generate(source)
    form,validation=convert(semantic)
    quality=assess(source,semantic)
    labels=[]
    for page in semantic.get("pages",[]):
        for section in page.get("sections",[]):
            for field in section.get("fields",[]):
                labels.append({"label":field.get("label"),"type":field.get("type"),
                               "options":field.get("options",[])})
    report={
        "model":meta["model"],"elapsed_seconds":round(time.perf_counter()-start,2),
        "model_usage":meta.get("usage",{}), "page_count":len(semantic.get("pages",[])),
        "input_field_count":len(labels),"labels":labels,
        "coi_schema_valid":validation["schema_valid"],
        "coi_business_rules_valid":validation["valid"],"business_warnings":validation["warnings"],
        "quality_gate":quality,
    }
    print(json.dumps(report,ensure_ascii=False,indent=2))

asyncio.run(main())

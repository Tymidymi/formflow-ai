"""Universal classification of any explicit responses inside a legal appendix.

The legal disclosure remains an uneditable source transcription; a distinct
user response (if printed) can be represented separately. No document-title,
municipality or case-specific patterns are used.
"""
from __future__ import annotations
from .ai_provider import generate

PROMPT = """Read the following legal/informational appendix of a Polish form.
Return only applicant actions that are ACTUALLY printed in the provided text:
a separate blank/checkbox/yes-no acknowledgment or explicit declaration
that requires the applicant to make a choice. Do NOT treat GDPR paragraphs,
administrative contact details, numbered rights, the entire disclosure, or a
paper-only handwritten signature as answer fields.

Output one JSON object:
{"title":"Informacje i zgody",
 "pages":[{"title":"Informacje i zgody","sections":[{"title":"Oświadczenia",
 "fields":[{"label":"short original text of applicant's affirmative choice",
 "type":"CHECKBOX|RADIO|TEXT_FIELD",
 "required":false,"options":[],"evidence":"short exact source quotation"}]}]}]}
If the source has NO explicit answer apart from a handwritten signature,
return {"title":"Informacje i zgody","pages":[]}.
Do not invent consent requirements or make a declaration required by default.
Only JSON."""

async def extract_actions(source:str)->tuple[list[dict],dict]:
    if not source.strip():
        return [],{}
    raw,info=await generate(source[:6500],[],prompt=PROMPT)
    fields=[]
    for page in raw.get("pages",[]):
        if not isinstance(page,dict):continue
        for section in page.get("sections",[]):
            if not isinstance(section,dict):continue
            for field in section.get("fields",[]):
                if not isinstance(field,dict):continue
                if field.get("type") not in ("CHECKBOX","RADIO","TEXT_FIELD"):continue
                label=str(field.get("label","")).strip()
                if not label:continue
                fields.append({"label":label[:220],
                               "type":field["type"],"required":False,
                               "options":[str(x) for x in field.get("options",[])
                                          if isinstance(x,str)][:15],
                               "evidence":str(field.get("evidence") or "")[:240]})
    return fields,info

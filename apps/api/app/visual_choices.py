"""Independent, source-grounded audit of printed choice controls.

It adds missing checkbox/radio groups and their writable companion blanks.
Nothing here depends on any particular form or subject vocabulary.
"""
from __future__ import annotations

from io import BytesIO
from difflib import SequenceMatcher
from PIL import Image
from .ai_provider import generate
from .field_grounding import norm

PROMPT = """You are a document-layout auditor, NOT a form generator.
Inspect the original PAGE IMAGE directly, alongside OCR (which may omit
small printed squares and text). Identify ALL visually printed groups of
checkboxes or radio choices, even those nested in a table's single row.

Before writing the output, SCAN THE IMAGE FROM TOP TO BOTTOM and count
EVERY small square/circle indicating a choice. Check horizontal rows with
multiple choices as carefully as vertical lists. Your total number of
options across groups must reflect ALL actually visible marks; do not
invent boxes to satisfy a heuristic count.
One group is a question followed by TWO OR MORE printed choice marks.
For each mark, transcribe its printed caption exactly. Inspect whether
there is also a DISTINCT dotted/underlined writable blank beside THAT
choice (e.g. an optional identifier, quantity or specification).
Such a blank is a separate text response, not another checkbox option.
A blank in the GROUP HEADING is not automatically a companion blank.
A printed caption or a measurement unit alone is not an input.

Do not interpret bullet lists, attachment inventories, RODO disclosures,
printed instructions without marks, or table column headings as choices.
Do not invent possible choices, labels, blanks or legal obligations.
Do not repeat the same physical group in multiple entries.
Use RADIO only for actual circles or clearly exclusive choices;
otherwise use CHECKBOX. Never infer required=true.

Return ONLY JSON:
{"pages":[{"choice_groups":[
 {"label":"exact nearby printed question/caption",
  "kind":"CHECKBOX",
  "evidence":"short nearby exact printed source text",
  "options":[
   {"label":"exact caption beside a printed box",
    "evidence":"caption printed beside that box",
    "has_detail_blank":false,
    "detail_label":""}
  ]}
]}]}
If there are no visually printed choice groups, return
{"pages":[{"choice_groups":[]}]}.
Preserve original Polish wording and number of boxes. JSON only."""

def _fields(semantic: dict) -> list[dict]:
    return [f for p in semantic.get("pages",[]) if isinstance(p,dict)
            for s in p.get("sections",[]) if isinstance(s,dict)
            for f in s.get("fields",[]) if isinstance(f,dict)]

def _matches(label: str, source: str) -> bool:
    """Word-boundary text grounding (no known subject-specific words)."""
    import re
    token=norm(label).strip()
    hay=norm(source)
    if len(token)<3:return False
    return re.search(r"(?<![a-z0-9])"+re.escape(token)+r"(?![a-z0-9])",hay) is not None

def _visual_square_locations(image:tuple[str,bytes])->list[int]:
    """Conservative raster check for empty small square outlines.

    Only used as a coverage hint. Never turns pixels into invented fields.
    Downsample to bound CPU/memory; does not depend on the form's vocabulary.
    """
    try:
        with Image.open(BytesIO(image[1])) as src:
            src.load()
            gray=src.convert("L")
            gray.thumbnail((1200,1700))
        width,height=gray.size
        px=gray.load()
        points=[]
        for y in range(1,max(1,height-54)):
            x=1
            while x<width-54:
                if px[x,y]>=115:
                    x+=1;continue
                left=x
                while x<width-1 and px[x,y]<115:
                    x+=1
                side=x-left
                if not 10<=side<=52:continue
                bottom=y+side-1
                if bottom>=height:continue
                left_count=sum(px[left,j]<130 for j in range(y,bottom+1))
                right_count=sum(px[left+side-1,j]<130
                                for j in range(y,bottom+1))
                base_count=sum(px[j,bottom]<130 for j in range(left,left+side))
                if min(left_count,right_count,base_count)<side*.66:continue
                inner=[px[j,k]>180 for j in range(left+3,left+side-3,3)
                       for k in range(y+3,bottom-2,3)]
                if not inner or sum(inner)<len(inner)*.68:continue
                if any(abs(left-a)<side and abs(y-b)<side for a,b,_ in points):
                    continue
                points.append((left,y,side))
                if len(points)>150:return []  # suspect dense table glyphs
        return [int((y+side//2)/height*1000) for _,y,side in points]
    except (OSError,ValueError,TypeError):
        return []


def _focus_crops(image:tuple[str,bytes])->list[tuple[str,bytes]]:
    try:
        with Image.open(BytesIO(image[1])) as src:
            src.load()
            im=src.convert("RGB")
            w,h=im.size
            if h<240:return []
            out=[]
            # Deliberately overlap so choices at the split aren't lost.
            for top,bottom in ((0,int(h*.64)),(int(h*.36),h)):
                stream=BytesIO()
                im.crop((0,top,w,bottom)).save(stream,format="JPEG",quality=86)
                if len(stream.getvalue())<4*1024*1024:
                    out.append(("image/jpeg",stream.getvalue()))
            return out
    except (OSError,ValueError,TypeError):
        return []


def _join_groups(base:list[dict],additional:list[dict],text:str)->list[dict]:
    for item in additional:
        prior=None
        for candidate in base:
            a=_clean(candidate["label"]);b=_clean(item["label"])
            overlap={_clean(x["label"]) for x in candidate["options"]} & {
                _clean(x["label"]) for x in item["options"]}
            if a==b or (overlap and SequenceMatcher(None,a,b).ratio()>=.74):
                prior=candidate;break
        if prior is None:
            base.append(item);continue
        known={_clean(o["label"]):o for o in prior["options"]}
        for option in item["options"]:
            key=_clean(option["label"])
            if key in known:
                if option["has_detail_blank"]:
                    known[key]["has_detail_blank"]=True
                    if option["detail_label"]:
                        known[key]["detail_label"]=option["detail_label"]
            else:
                prior["options"].append(option)
                known[key]=option
        grounded=sum(_matches(o["label"],text) for o in prior["options"])
        prior["ocr_grounded_options"]=grounded
        prior["needs_visual_review"]=grounded<len(prior["options"])
    return base

def _parse_choice_groups(raw:dict,text:str)->list[dict]:
    result=[]
    for page in raw.get("pages",[]):
        if not isinstance(page,dict):continue
        for group in page.get("choice_groups",[]):
            if not isinstance(group,dict):continue
            label=str(group.get("label") or "").strip()[:200]
            if len(label)<3:continue
            options=[];used=set()
            raw_options=group.get("options",[])
            if not isinstance(raw_options,list):continue
            for entry in raw_options:
                if not isinstance(entry,dict):continue
                name=str(entry.get("label") or "").strip()[:120]
                ident=norm(name)
                if len(ident)<2 or ident in used:continue
                used.add(ident)
                options.append({
                    "label":name,
                    "evidence":str(entry.get("evidence") or name)[:200],
                    "has_detail_blank":entry.get("has_detail_blank") is True,
                    "detail_label":str(entry.get("detail_label") or "").strip()[:100],
                })
            if not 2<=len(options)<=20:continue
            # Preserve visually legible choices missed by OCR, but flag
            # them explicitly for review instead of claiming OCR evidence.
            grounded=sum(_matches(o["label"],text) for o in options)
            result.append({
                "label":label,"kind":group.get("kind")
                    if group.get("kind") in {"CHECKBOX","RADIO"}
                    else "CHECKBOX",
                "options":options,
                "evidence":str(group.get("evidence") or label)[:220],
                "ocr_grounded_options":grounded,
                "needs_visual_review":grounded<len(options),
            })
    return result[:30]

async def detect_choices(text: str, image: tuple[str,bytes]) -> list[dict]:
    square_y=_visual_square_locations(image)
    hint=("\nINDEPENDENT PIXEL COVERAGE HINT: approx. "
          +str(len(square_y))+" small empty square outlines at relative "
          +"vertical image positions "+str(square_y)+" (scale 0-1000). "
          +"This count is approximate, NOT permission to invent any options. "
          +"Visually check every horizontal and vertical group.\n") if square_y else ""
    raw,_=await generate((text+hint)[:15000],[image],prompt=PROMPT)
    groups=_parse_choice_groups(raw,text)
    counted=sum(len(g["options"]) for g in groups)
    # A different physical-box inventory can reveal missed horizontal rows.
    # Re-examine two overlapping regions instead of assuming a valid JSON is
    # complete. No source labels or case-specific fixups are introduced.
    retry=bool(square_y and counted<len(square_y))
    if retry:
        for crop in _focus_crops(image):
            additional,_=await generate(text[:9000],[crop],prompt=PROMPT)
            groups=_join_groups(groups,_parse_choice_groups(additional,text),text)
            if sum(len(g["options"]) for g in groups)>=len(square_y):
                break
    return groups

def _clean(value: str) -> str:
    return " ".join(norm(value).strip().strip(":; ").split())


def _is_group_option(field:dict,group_label:str,option_labels:list[str])->bool:
    """Only replace a checkbox when both option AND parent are evidenced."""
    if field.get("type") not in {"CHECKBOX","RADIO"} or field.get("options"):
        return False
    label=_clean(str(field.get("label", "")))
    parent=_clean(group_label)
    evidence=_clean(str(field.get("evidence", "")))
    opts={_clean(v) for v in option_labels}
    if label.startswith(parent) and len(label)>len(parent):
        remainder=label[len(parent):].strip(" :—–-./")
        if remainder in opts:return True
    # A bare option label can be grouped ONLY with matching source evidence.
    return label in opts and parent in evidence and label in evidence


def consolidate_choice_fields(semantic:dict)->int:
    """Combine option rows identified independently by the first VLM.

    Requires a shared, printed question prefix and matching source evidence;
    never uses labels specific to an administrative form.
    """
    combined=0
    for page in semantic.get("pages",[]):
        for section in page.get("sections",[]):
            items=section.get("fields",[])
            candidates={}
            for i,f in enumerate(items):
                if f.get("type") not in {"CHECKBOX","RADIO"} or f.get("options"):
                    continue
                title=str(f.get("label", ""))
                if ":" not in title:continue
                parent,option=title.rsplit(":",1)
                if len(parent.strip())<4 or len(option.strip())<2:continue
                if _clean(parent) not in _clean(str(f.get("evidence", ""))):
                    continue
                candidates.setdefault(_clean(parent),[]).append((i,parent,option.strip(),f))
            to_remove=set();replacements={}
            for entries in candidates.values():
                if len(entries)<2:continue
                names=[t[2] for t in entries]
                if len({_clean(name) for name in names})<2:continue
                first_idx=entries[0][0]
                first=entries[0][3]
                replacements[first_idx]={
                    "label":entries[0][1].strip()+":",
                    "type":"RADIO" if all(e[3]["type"]=="RADIO" for e in entries)
                             else "CHECKBOX",
                    "options":names,"required":False,
                    "evidence":str(first.get("evidence") or ""),
                    "source_page":first.get("source_page"),
                    "source":"source_label_choice_group",
                }
                to_remove.update(e[0] for e in entries[1:])
                combined+=1
            if replacements:
                section["fields"]=[replacements.get(i,f) for i,f in enumerate(items)
                                   if i not in to_remove]
    return combined

def merge_choices(semantic:dict,groups:list[dict],source_page:int) -> dict:
    """Reconcile by printed question AND options, not example-field labels."""
    if not groups:return {"choice_groups":0,"choice_options":0,
                          "detail_inputs_added":0,"visual_review_groups":0}
    pages=semantic.setdefault("pages",[])
    if not pages:
        pages.append({"title":f"Strona źródłowa {source_page}","sections":[]})
    root=pages[0]
    sections=root.setdefault("sections",[])
    counts={"choice_groups":0,"choice_options":0,
            "detail_inputs_added":0,"visual_review_groups":0}

    for group_index,group in enumerate(groups,1):
        question=group["label"]
        ref=f"choice_{source_page}_{group_index}"
        opt_names=[o["label"] for o in group["options"]]
        wanted={_clean(x) for x in opt_names}
        choice=None;target_section=None
        # Prefer an existing group over creating a second copy of the same
        # source question. Preserve a sensible RADIO type if already assigned.
        for section in sections:
            for field in section.get("fields",[]):
                if field.get("type") not in {"CHECKBOX","RADIO","SELECT"}:continue
                current={_clean(str(x)) for x in field.get("options",[])
                         if isinstance(x,str)}
                caption=_clean(str(field.get("label","")))
                parent=_clean(question)
                if caption==parent or (len(current & wanted)>=2 and
                    (caption in parent or parent in caption)):
                    choice=field;target_section=section;break
            if choice is not None:break
        if choice is None:
            # Attach to the same section and position as the originally
            # extracted individual options, not an unrelated new section.
            matches=[(section,[i for i,f in enumerate(section.get("fields",[]))
                               if _is_group_option(f,question,opt_names)])
                     for section in sections]
            matches=[(section,indices) for section,indices in matches if indices]
            if matches:
                target_section,indices=max(matches,key=lambda item:len(item[1]))
                insert_at=indices[0]
            else:
                target_section={"title":question,"fields":[]}
                sections.append(target_section)
                insert_at=0
            choice={"label":question,"type":group["kind"],
                    "options":opt_names,"required":False,
                    "evidence":group["evidence"],
                    "source_page":source_page,
                    "source":"visual_choice_audit"}
            target_section["fields"].insert(insert_at,choice)
            counts["choice_groups"]+=1
        else:
            existing=[x for x in choice.get("options",[]) if isinstance(x,str)]
            choice["options"]=list(dict.fromkeys(existing+opt_names))
        choice["source_choice_ref"]=ref
        # Remove ONLY fields with the option AND the shared question prefix;
        # a generic standalone checkbox elsewhere may have the same caption.
        for section in sections:
            section["fields"]=[f for f in section.get("fields",[])
                if f is choice or not _is_group_option(f,question,opt_names)]
        counts["choice_options"]+=len(opt_names)
        counts["visual_review_groups"]+=int(group.get("needs_visual_review",False))
        for option in group["options"]:
            if not option["has_detail_blank"]:continue
            detail=option["detail_label"] or "Dodatkowe dane"
            detail_name=f"{question} — {option['label']}: {detail}"[:220]
            existing_detail=next((f for f in _fields(semantic)
                if f.get("type") in {"TEXT_FIELD","NUMBER","TEXTAREA"}
                and _clean(option["label"]) in _clean(str(f.get("label","")))
                and (_clean(question) in _clean(str(f.get("label","")))
                     or _clean(question) in _clean(str(f.get("evidence",""))))
            ),None)
            if existing_detail is not None:
                existing_detail.setdefault("show_when",{
                    "field_ref":ref,"value":option["label"]})
                continue
            target_section["fields"].append({
                "label":detail_name,"type":"TEXT_FIELD",
                "required":False,"options":[],
                "evidence":option["evidence"],
                "source_page":source_page,
                "source":"visual_choice_detail",
                "show_when":{"field_ref":ref,
                             "value":option["label"]}
            })
            counts["detail_inputs_added"]+=1
        sections[:]=[section for section in sections if section.get("fields")]
    return counts

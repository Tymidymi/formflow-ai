/** Convert COI tabs/fields to JSON Forms schemas. Do not evaluate model JSONata. */
const INPUTS=new Set(["TEXT_FIELD","TEXTAREA","NUMBER","DATEPICKER","RADIO","SELECT","CHECKBOX","FILE_UPLOADER"]);
const CONTAINERS=new Set(["SECTION","REPEATING_SECTION","INFO_SECTION","CONSENT_SECTION"]);
const NAME=/^[a-zA-Z][a-zA-Z0-9_]{0,99}$/;
const safeName=(f,i)=>NAME.test(f.techName||"")&&!["__proto__","constructor","prototype"].includes(f.techName)?f.techName:"field_"+i;
const pointer=key=>"#/properties/"+key.replaceAll("~","~0").replaceAll("/","~1");
const children=f=>Array.isArray(f.repeatingSectionGrid)?f.repeatingSectionGrid:(Array.isArray(f.repetingSectionGrid)?f.repetingSectionGrid:[]);
const choices=f=>(Array.isArray(f.options)?f.options:[]).map(x=>typeof x==="string"?x:(x?.name??x?.id)).filter(x=>typeof x==="string"&&x.trim()).slice(0,100);
const captionTokens=value=>String(value||"").normalize("NFD")
  .replace(/[\u0300-\u036f]/g,"").toLowerCase()
  .split(/[^a-z0-9]+/).filter(Boolean);
function captionsEquivalent(a,b){
  const aa=captionTokens(a),bb=captionTokens(b);
  if(!aa.length||!bb.length)return false;
  if(aa.join(" ")===bb.join(" "))return true;
  // Only collapses redundant presentational group wrappers; it NEVER drops
  // controls or source data. Require multiple informative shared tokens.
  if(Math.min(aa.join("").length,bb.join("").length)<14)return false;
  const aSet=new Set(aa),bSet=new Set(bb);
  const shared=[...aSet].filter(x=>bSet.has(x));
  return shared.length>=3 && shared.length/Math.min(aSet.size,bSet.size)>=.70;
}

export function collectFields(form){
  const fields=[];
  for(const tab of (Array.isArray(form?.tabs)?form.tabs:[]).slice(0,30)){
    const walk=(entries,section,depth)=>{
      if(depth>5||!Array.isArray(entries))return;
      for(const entry of entries){
        const f=entry?.field;
        if(!f||typeof f!=="object")continue;
        if(INPUTS.has(f.type)){if(fields.length<400)fields.push({tab,section,field:f});}
        else if(CONTAINERS.has(f.type))walk(children(f),String(f.title||section),depth+1);
      }
    };
    walk(tab.questions,String(tab.title||"Dane"),0);
  }
  return fields;
}

/** Strictly parse the COI reference SHOW form, not general-purpose JSONata. */
export function parseShowQuery(query){
  if(typeof query!=="string"||query.length>900)return null;
  const m=query.trim().match(/^\(("(?:[^"\\]|\\.)*") in tabs\['((?:[^'\\]|\\.)*)' in title\]\.questions\['((?:[^'\\]|\\.)*)' in field\.techName\]\.field\.repeatingSectionGrid\['((?:[^'\\]|\\.)*)' in field\.techName\]\.field\.__userAnswer\)$/);
  if(!m)return null;
  try{
    const unescapeSingle=s=>s.replace(/\\(['\\])/g,"$1");
    return {value:JSON.parse(m[1]),tab:unescapeSingle(m[2]),section:unescapeSingle(m[3]),source:unescapeSingle(m[4])};
  }catch{return null;}
}

function schemaFor(f,warnings){
  const label=String(f.title||f.techName||"Pole");
  const rules=Array.isArray(f.validation)?f.validation:[];
  const s={title:label};
  const opts=choices(f);
  switch(f.type){
    case "NUMBER":s.type="number";if(/liczba|ilość|ilosc/i.test(label))s.minimum=0;break;
    case "DATEPICKER":s.type="string";s.format="date";break;
    case "SELECT":case "RADIO":
      s.type="string";if(opts.length)s.enum=opts;
      else if(f.dictionaryName){
        s.description="Słownik "+f.dictionaryName+" (brak danych w podglądzie)";
        warnings.push("Niezaładowany słownik "+f.dictionaryName+" w polu "+label);
      }
      break;
    case "CHECKBOX":
      if(opts.length){s.type="array";s.items={type:"string",enum:opts};s.uniqueItems=true;}
      else s.type="boolean";
      break;
    case "FILE_UPLOADER":
      s.type="string";s.format="file-name-preview";
      s.description="Podgląd zapisuje nazwę załącznika; nie przesyła pliku.";
      break;
    case "TEXTAREA":default:s.type="string";s.maxLength=3000;
  }
  if(rules.includes("REQUIRED")&&s.type==="boolean")s.const=true;
  if(rules.includes("REQUIRED")&&s.type==="array")s.minItems=1;
  if(s.type==="string"&&!["date","file-name-preview"].includes(s.format)){
    if(rules.includes("PESEL"))s.pattern="^[0-9]{11}$";
    else if(rules.includes("NIP"))s.pattern="^[0-9]{10}$";
    else if(rules.includes("REGON"))s.pattern="^([0-9]{9}|[0-9]{14})$";
    else if(rules.includes("ZIP_CODE"))s.pattern="^[0-9]{2}-[0-9]{3}$";
    else if(rules.includes("EMAIL"))s.format="email";
  }
  return s;
}
function showRule(f,index,warnings){
  if(!Array.isArray(f.states)||!f.states.length)return null;
  if(f.states.length!==1||f.states[0]?.type!=="SHOW"){
    warnings.push("Nieobsługiwane stany COI: "+(f.title||f.techName));return null;
  }
  const parsed=parseShowQuery(f.states[0].query);
  const source=parsed?index.get(parsed.source):null;
  if(!source||source.tab.title!==parsed.tab){
    warnings.push("Nieobsługiwany warunek JSONata: "+(f.title||f.techName));return null;
  }
  if(!choices(source.field).includes(parsed.value)&&!source.field.dictionaryName){
    warnings.push("Brak odpowiedzi źródłowej dla warunku: "+(f.title||f.techName));return null;
  }
  const isMultiChoice=source.field.type==="CHECKBOX" && choices(source.field).length>0;
  const match=isMultiChoice ? {type:"array",contains:{const:parsed.value}} : {const:parsed.value};
  return {effect:"SHOW",condition:{scope:pointer(source.key),schema:match,failWhenUndefined:true}};
}
export function coiToJsonForms(form){
  if(!form||typeof form!=="object"||!Array.isArray(form.tabs)||!form.tabs.length){
    throw Error("Niepoprawny formularz COI: brak stron.");
  }
  const warnings=[],raw=collectFields(form),index=new Map(),byKey=new Map();
  raw.forEach((item,i)=>{
    let key=safeName(item.field,i+1),base=key,n=2;
    while(byKey.has(key))key=base+"_"+n++;
    item.key=key;byKey.set(key,item);
    if(typeof item.field.techName==="string")index.set(item.field.techName,item);
  });
  const schema={$schema:"http://json-schema.org/draft-07/schema#",type:"object",
    title:String(form.title||"Formularz COI"),properties:Object.create(null),
    required:[],additionalProperties:false};
  for(const item of raw){
    schema.properties[item.key]=schemaFor(item.field,warnings);
    if(item.field.validation?.includes("REQUIRED")&&!item.field.states?.length)schema.required.push(item.key);
  }
  if(!schema.required.length)delete schema.required;
  const pages=[];
  for(const tab of form.tabs.slice(0,30)){
    const blocks=[];let count=0;
    const walk=(entries,out,depth)=>{
      if(!Array.isArray(entries)||depth>5)return;
      for(const entry of entries){
        const f=entry?.field;if(!f||typeof f!=="object")continue;
        if(INPUTS.has(f.type)){
          const item=raw.find(x=>x.field===f);if(!item)continue;
          const control={type:"Control",scope:pointer(item.key),label:String(f.title||item.key)};
          if(f.type==="TEXTAREA")control.options={multi:true};
          if(f.type==="RADIO")control.options={format:"radio"};
          const rule=showRule(f,index,warnings);if(rule)control.rule=rule;
          out.push(control);count++;
        }else if(CONTAINERS.has(f.type)){
          const nested=[];walk(children(f),nested,depth+1);
          if(nested.length){
            const redundant= nested[0]?.type==="Control"
              && captionsEquivalent(f.title,nested[0].label);
            if(redundant)out.push(...nested);
            else out.push({type:"Group",label:String(f.title||"Sekcja"),elements:nested});
          }
        }else if(f.type==="TEXT_BLOCK"){
          const plain=String(f.description||"")
            .replace(/<br\s*\/?\s*>/gi,"\n")
            .replace(/<\/p\s*>/gi,"\n")
            .replace(/<[^>]*>/g," ")
            .replace(/&lt;/g,"<").replace(/&gt;/g,">")
            .replace(/&quot;/g,'"').replace(/&#x27;|&#39;/g,"'")
            .replace(/&amp;/g,"&")
            .replace(/[ \t]{2,}/g," ").trim();
          if(plain)blocks.push(plain.slice(0,7000));
        }
      }
    };
    const elements=[];walk(tab.questions,elements,0);
    pages.push({id:String(tab.id||"page-"+pages.length),title:String(tab.title||"Strona"),
      isFinish:tab.type==="FINISH",uiSchema:{type:"VerticalLayout",elements},
      blocks,fieldCount:count});
  }
  return {jsonSchema:schema,pages,fields:raw,warnings:[...new Set(warnings)]};
}
export function conditionIsVisible(rule,data){
  if(!rule||rule.effect!=="SHOW")return true;
  const key=rule.condition?.scope?.replace("#/properties/","").replaceAll("~1","/").replaceAll("~0","~");
  if(!key)return false;
  const predicate=rule.condition?.schema;
  if(predicate?.type==="array" && predicate.contains?.const!==undefined){
    return Array.isArray(data?.[key]) && data[key].includes(predicate.contains.const);
  }
  return data?.[key]===predicate?.const;
}
export function hasRealAnswer(value){
  return value!==undefined && value!==null && value!=="" && value!==false
    && (!Array.isArray(value)||value.length>0);
}
export function makePreviewAnswerPayload(form,answers,visibleKeys){
  const visible=new Set(visibleKeys);
  const output=Object.fromEntries(Object.entries(answers||{}).filter(
    ([key,value])=>visible.has(key)&&hasRealAnswer(value)));
  if(!Object.keys(output).length)return null;
  return {form:String(form?.title||"COI"),previewOnly:true,answers:output};
}
export function calculateSummary(adapter,answers){
  let count=0;
  for(const field of adapter.fields){
    const v=answers?.[field.key];
    if(hasRealAnswer(v))count++;
  }
  return {fields:adapter.fields.length,answered:count,pages:adapter.pages.length};
}

/** Optional content checks for the *answer preview*. Never changes COI JSON. */
export function checksumValid(code,value){
  if(typeof value!=="string")return true;
  const text=value.trim();
  if(!text)return true;
  let weights;
  if(code==="PESEL"){
    if(!/^\d{11}$/.test(text))return false;
    weights=[1,3,7,9,1,3,7,9,1,3];
    const sum=weights.reduce((acc,w,i)=>acc+w*Number(text[i]),0);
    return (10-sum%10)%10===Number(text[10]);
  }
  if(code==="NIP"){
    if(!/^\d{10}$/.test(text))return false;
    weights=[6,5,7,2,3,4,5,6,7];
    const digit=weights.reduce((acc,w,i)=>acc+w*Number(text[i]),0)%11;
    return digit!==10&&digit===Number(text[9]);
  }
  if(code==="REGON"){
    if(!/^(\d{9}|\d{14})$/.test(text))return false;
    weights=text.length===9?[8,9,2,3,4,5,6,7]:[2,4,8,5,0,9,7,3,6,1,2,4,8];
    let digit=weights.reduce((acc,w,i)=>acc+w*Number(text[i]),0)%11;
    if(digit===10)digit=0;
    return digit===Number(text.at(-1));
  }
  return true;
}
export function validateAnswerCells(fields,answers){
  const problems=[];
  for(const item of fields||[]){
    const f=item?.field||{};
    const text=answers?.[item.key];
    if(typeof text!=="string"||!text.trim())continue;
    const rules=f.validation||[];
    for(const rule of ["PESEL","NIP","REGON"]){
      if(rules.includes(rule)&&!checksumValid(rule,text)){
        problems.push({key:item.key,label:f.title||item.key,
          message:"Niepoprawna liczba kontrolna "+rule+" lub długość numeru."});
        break;
      }
    }
    if(!rules.some(rule=>["PESEL","NIP","REGON"].includes(rule))
       && /^(?:numer\s+)?telefonu?\b|^telefon\b/i.test(f.title||"")
       && !/^\+?[0-9][0-9\s()-]{6,18}$/.test(text.trim())){
      problems.push({key:item.key,label:f.title||item.key,
        message:"Numer telefonu ma nieprawidłowy format."});
    }
  }
  return problems;
}

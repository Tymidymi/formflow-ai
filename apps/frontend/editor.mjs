/** Immutable COI field-definition editor; never executes model-provided code. */
import { parseShowQuery } from "./adapter.mjs";

export const EDITABLE_TYPES=[
 ["TEXT_FIELD","Krótki tekst"],["TEXTAREA","Dłuższa odpowiedź"],
 ["NUMBER","Liczba"],["DATEPICKER","Data"],["RADIO","Jeden wybór (radio)"],
 ["SELECT","Lista rozwijana"],["CHECKBOX","Checkbox / wiele odpowiedzi"],
 ["FILE_UPLOADER","Załącznik"],
];
export const FORMAT_VALIDATORS=[
 ["","Bez dodatkowej walidacji"],["EMAIL","E-mail"],["PESEL","PESEL"],
 ["NIP","NIP"],["REGON","REGON"],["ZIP_CODE","Kod pocztowy"],
];
const TYPES=new Set(EDITABLE_TYPES.map(x=>x[0]));
const FORMATS=new Set(FORMAT_VALIDATORS.map(x=>x[0]));
const clone=x=>structuredClone(x);
const slug=value=>{
 const s=String(value||"").replaceAll("Ł","L").replaceAll("ł","l")
 .normalize("NFKD").replace(/[\u0300-\u036f]/g,"")
 .toLowerCase().replace(/[^a-z0-9]+/g,"_").replace(/^_+|_+$/g,"").slice(0,53);
 return /^[a-z]/.test(s)?s:"pole_"+(s||"nowe");
};
const makeId=()=>crypto.randomUUID();
const grid=(field,y=0)=>({x:0,y,rows:1,cols:3,field});
const clipped=(v,max=220)=>String(v??"").trim().slice(0,max);
const named=(v,max,name)=>{
 const t=clipped(v,max);if(!t)throw Error("Pole „"+name+"” nie może być puste.");
 return t;
};
const contents=section=>{
 const f=section?.field;
 const list=f?.repeatingSectionGrid??f?.repetingSectionGrid;
 return Array.isArray(list)?list:[];
};
function pageAt(form,i){
 if(!Number.isInteger(i)||i<0||i>=form.tabs.length)throw Error("Nie znaleziono strony.");
 const tab=form.tabs[i];
 if(tab.type==="FINISH")throw Error("Nie można edytować strony końcowej.");
 return tab;
}
function sectionAt(tab,id){
 const section=tab.questions?.find(x=>x?.field?.id===id);
 if(!section||!["SECTION","REPEATING_SECTION","INFO_SECTION"].includes(section.field.type))
   throw Error("Nie znaleziono sekcji.");
 return section;
}
function fieldAt(section,id){
 const item=contents(section).find(x=>x?.field?.id===id);
 if(!item||!TYPES.has(item.field.type))throw Error("Nie znaleziono edytowalnego pola.");
 return item;
}
function allFields(form){
 const out=[];
 const walk=(items,depth)=>{
   if(!Array.isArray(items)||depth>6)return;
   for(const item of items){
     const f=item?.field;if(!f||typeof f!=="object")continue;
     out.push(f);walk(f.repeatingSectionGrid??f.repetingSectionGrid,depth+1);
   }
 };
 for(const tab of form.tabs||[])walk(tab.questions,0);
 return out;
}
function uniqueName(form,title){
 const used=new Set(allFields(form).map(f=>f.techName));
 const base=slug(title);let name=base,index=2;
 while(used.has(name))name=base.slice(0,45)+"_"+index++;
 return name;
}
function parseOptions(value,old=[]){
 const entries=String(value||"").split("\n").map(v=>v.trim()).filter(Boolean);
 if(entries.length>20)throw Error("Można ustawić maksymalnie 20 opcji.");
 if(entries.some(v=>v.length>160))throw Error("Opcja może mieć maksymalnie 160 znaków.");
 if(new Set(entries).size!==entries.length)throw Error("Opcje wyboru muszą być unikatowe.");
 return entries.map(value=>{
   const prev=old.find(x=>(x?.name??x)===value);
   return prev&&typeof prev==="object"?clone(prev):
     {id:value,name:value,techName:slug(value)};
 });
}
function referenceGuard(form,source,updated){
 const dependent=allFields(form).flatMap(f=>
   (Array.isArray(f.states)?f.states:[])
     .filter(s=>s?.type==="SHOW")
     .map(s=>({target:f.title,rule:parseShowQuery(s.query)}))
     .filter(item=>item.rule?.source===source.techName));
 if(!dependent.length)return;
 if(!["RADIO","SELECT"].includes(updated.type))
   throw Error("To pole steruje widocznością innych pytań; musi pozostać polem wyboru.");
 const options=new Set(updated.options.map(x=>x?.name??x));
 for(const item of dependent){
   if(!options.has(item.rule.value))
     throw Error("Opcja „"+item.rule.value+"” steruje polem „"+item.target+"” i nie może zostać usunięta.");
 }
}
function deleteGuard(form,ids){
 const names=new Set(allFields(form).filter(f=>ids.has(f.id)).map(f=>f.techName));
 for(const field of allFields(form)){
   if(ids.has(field.id))continue;
   for(const state of field.states||[]){
     if(state?.type!=="SHOW")continue;
     const parsed=parseShowQuery(state.query);
     if(parsed&&names.has(parsed.source))
       throw Error("Pole „"+field.title+"” zależy od usuwanego pola; najpierw zmień regułę SHOW.");
     if(!parsed&&typeof state.query==="string"&&[...names].some(n=>state.query.includes(n)))
       throw Error("Pole jest używane w nierozpoznanej regule warunkowej. Nie można go bezpiecznie usunąć.");
   }
 }
}
function reflow(tab){
 let y=0;
 tab.questions.forEach((section,index)=>{
   const children=contents(section);
   children.forEach((entry,i)=>{
     entry.x=0;entry.y=i;entry.rows=1;entry.cols=3;entry.field.questionOrder=i;
   });
   section.x=0;section.y=y;section.rows=Math.max(2,children.length+1);section.cols=3;
   section.field.questionOrder=index;y+=section.rows;
 });
}
export const editableSections=(form,pageIndex)=>
 (form?.tabs?.[pageIndex]?.questions||[]).filter(q=>
   ["SECTION","REPEATING_SECTION","INFO_SECTION"].includes(q?.field?.type))
   .map(section=>({id:section.field.id,title:section.field.title,
     fields:contents(section).filter(x=>TYPES.has(x?.field?.type)).map(x=>x.field),
     readonly:contents(section).some(x=>!TYPES.has(x?.field?.type))}));
export const editorSnapshot=field=>({
 label:field.title||"",type:field.type,required:(field.validation||[]).includes("REQUIRED"),
 optionsText:(field.options||[]).map(o=>o?.name??o).join("\n"),
 format:(field.validation||[]).find(x=>FORMATS.has(x)&&x!=="")||"",
 tooltip:field.tooltipMessage||"",
});
export function editCOI(source,action,idFactory=makeId){
 if(!source?.tabs||!Array.isArray(source.tabs))throw Error("Niepoprawny formularz COI.");
 const form=clone(source),type=action?.type;
 if(type==="formTitle"){
   form.title=named(action.title,255,"Tytuł formularza");return form;
 }
 const tab=pageAt(form,action.pageIndex);
 if(type==="pageTitle"){
   const old=tab.title,next=named(action.title,220,"Tytuł strony");
   const literal=value=>String(value).replaceAll("\\","\\\\").replaceAll("'","\\'");
   const oldRef="tabs['"+literal(old)+"' in title]";
   const newRef="tabs['"+literal(next)+"' in title]";
   for(const field of allFields(form)){
     for(const state of field.states||[]){
       if(state?.type!=="SHOW"||typeof state.query!=="string")continue;
       const parsed=parseShowQuery(state.query);
       if(parsed?.tab===old){
         if(!state.query.includes(oldRef))
           throw Error("Nie można bezpiecznie przepisać warunku SHOW tej strony.");
         state.query=state.query.replace(oldRef,newRef);
       } else if(!parsed && state.query.includes(oldRef)){
         throw Error("Nierozpoznana reguła warunkowa zależy od tytułu tej strony.");
       }
     }
   }
   tab.title=next;return form;
 }
 if(type==="sectionAdd"){
   if(tab.questions.length>=24)throw Error("Za dużo sekcji na stronie.");
   const title="Nowa sekcja";
   const heading={id:idFactory(),type:"SECTION",techName:uniqueName(form,title),title,
     description:"<html><head></head><body></body></html>",options:[],validation:[],
     readOnly:false,repeatingSectionGrid:[],states:[],questionOrder:0,tooltipMessage:""};
   const item={id:idFactory(),type:"TEXT_FIELD",techName:uniqueName(form,"Nowe pole"),
     title:"Nowe pole",description:"",options:[],validation:[],readOnly:false,
     repeatingSectionGrid:[],states:[],questionOrder:0,tooltipMessage:""};
   heading.repeatingSectionGrid.push(grid(item));
   tab.questions.push(grid(heading));reflow(tab);return form;
 }
 const section=sectionAt(tab,action.sectionId);
 if(type==="sectionTitle"){
   section.field.title=named(action.title,220,"Tytuł sekcji");return form;
 }
 if(type==="sectionRemove"){
   if(contents(section).some(x=>!TYPES.has(x?.field?.type)))
     throw Error("Sekcja zawiera treść informacyjną i jest chroniona przed usunięciem.");
   deleteGuard(form,new Set([section.field.id,...contents(section).map(x=>x.field.id)]));
   if(tab.questions.length<=1)throw Error("Nie można usunąć ostatniej sekcji strony.");
   tab.questions=tab.questions.filter(x=>x.field.id!==section.field.id);
   if(!tab.questions.some(x=>contents(x).some(e=>TYPES.has(e?.field?.type))))
     throw Error("Strona musi zawierać co najmniej jedno pole.");
   reflow(tab);return form;
 }
 if(type==="fieldAdd"){
   if(contents(section).some(e=>!TYPES.has(e?.field?.type)))
     throw Error("Sekcja informacyjna jest tylko do odczytu. Dodaj osobną sekcję na pola.");
   if(allFields(form).filter(x=>TYPES.has(x.type)).length>=200)
     throw Error("Osiągnięto limit pól formularza.");
   const item={id:idFactory(),type:"TEXT_FIELD",techName:uniqueName(form,"Nowe pole"),
     title:"Nowe pole",description:"",options:[],validation:[],readOnly:false,
     repeatingSectionGrid:[],states:[],questionOrder:0,tooltipMessage:""};
   contents(section).push(grid(item));reflow(tab);return form;
 }
 const item=fieldAt(section,action.fieldId);
 if(type==="fieldRemove"){
   deleteGuard(form,new Set([item.field.id]));
   const rest=contents(section).filter(x=>x.field.id!==item.field.id);
   if(!rest.length)throw Error("To ostatnie pole sekcji. Dodaj inne lub usuń całą sekcję.");
   section.field.repeatingSectionGrid=rest;reflow(tab);return form;
 }
 if(type==="fieldMoveSection"){
   const target=sectionAt(tab,action.targetSectionId);
   if(target.field.id===section.field.id)
     throw Error("Pole jest już w tej sekcji.");
   const origin=contents(section),destination=contents(target);
   if(destination.length>=120)throw Error("Sekcja docelowa ma już maksymalną liczbę pól.");
   const index=origin.findIndex(x=>x.field.id===action.fieldId);
   if(index<0)throw Error("Nie znaleziono pola do przeniesienia.");
   const moved=origin[index].field;
   const oldName=section.field.techName,newName=target.field.techName;
   const quoted=s=>String(s).replaceAll("\\","\\\\").replaceAll("'","\\'");
   const oldRef="questions['"+quoted(oldName)+"' in field.techName]";
   const newRef="questions['"+quoted(newName)+"' in field.techName]";
   // SHOW references contain the SOURCE section's techName. When a source
   // choice moves, update all dependent controls. Never silently break rules.
   for(const field of allFields(form)){
     for(const rule of field.states||[]){
       if(rule?.type!=="SHOW"||typeof rule.query!=="string")continue;
       const parsed=parseShowQuery(rule.query);
       if(parsed?.source===moved.techName && parsed.section===oldName){
         if(!rule.query.includes(oldRef))
           throw Error("Nie można bezpiecznie przepisać warunku SHOW tego pola.");
         rule.query=rule.query.replace(oldRef,newRef);
       }else if(!parsed && rule.query.includes(moved.techName)){
         throw Error("Pole ma nierozpoznane zależności SHOW. Przeniesienie byłoby niebezpieczne.");
       }
     }
   }
   destination.push(origin.splice(index,1)[0]);
   if(!origin.length){
     tab.questions=tab.questions.filter(x=>x.field.id!==section.field.id);
   }
   reflow(tab);
   return form;
 }
 if(type==="fieldMove"){
   const items=contents(section),from=items.findIndex(x=>x.field.id===action.fieldId);
   const to=from+(action.direction===-1?-1:1);
   if(to<0||to>=items.length)throw Error("Pole jest już na granicy sekcji.");
   [items[from],items[to]]=[items[to],items[from]];
   reflow(tab);return form;
 }
 if(type==="fieldUpdate"){
   const values=action.values||{},label=named(values.label,220,"Etykieta");
   const kind=String(values.type);
   if(!TYPES.has(kind))throw Error("Niedozwolony typ pola.");
   const format=String(values.format||"");
   if(!FORMATS.has(format))throw Error("Nieznany rodzaj walidacji.");
   if(format&&!["TEXT_FIELD","TEXTAREA"].includes(kind))
     throw Error("Walidacja PESEL/e-mail/NIP itp. jest dostępna dla pola tekstowego.");
   const old=Array.isArray(item.field.options)?item.field.options:[];
   let options=[];
   if(["RADIO","SELECT","CHECKBOX"].includes(kind)){
     options=parseOptions(values.optionsText,old);
     if(["RADIO","SELECT"].includes(kind)&&!options.length&&!item.field.dictionaryName)
       throw Error("Pole wyboru wymaga co najmniej jednej opcji.");
   }
   const original=Array.isArray(item.field.validation)?item.field.validation:[];
   const validation=original.filter(rule=>
     !["REQUIRED","EMAIL","PESEL","NIP","REGON","ZIP_CODE"].includes(rule));
   if(values.required===true)validation.push("REQUIRED");
   if(format)validation.push(format);
   const updated={...item.field,type:kind,title:label,options,
     tooltipMessage:clipped(values.tooltip,450),validation};
   if(kind!=="SELECT")delete updated.dictionaryName;
   referenceGuard(form,item.field,updated);
   item.field=updated;
   return form;
 }
 throw Error("Nieznana operacja edycji.");
}

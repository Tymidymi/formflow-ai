import test from "node:test";
import assert from "node:assert/strict";
import {editCOI,editableSections,editorSnapshot} from "../editor.mjs";
import {coiToJsonForms,conditionIsVisible} from "../adapter.mjs";

let number=0;
const uuid=()=>("00000000-0000-4000-8000-"+String(++number).padStart(12,"0"));
const f=(type,label,name,options=[],states=[])=>({
 id:uuid(),type,title:label,techName:name,options,states,validation:[],
 description:"",readOnly:false,questionOrder:0,tooltipMessage:"",repeatingSectionGrid:[]
});
const w=(field,y=0)=>({x:0,y,rows:1,cols:3,field});
const options=["Wnioskodawca","Inna osoba"].map(name=>({id:name,name,techName:name.toLowerCase().replaceAll(" ","_")}));
function fixture(){
 number=0;
 const choice=f("RADIO","Osoba odpowiedzialna","kto_jest_osoba_odpowiedzialna",options);
 const dependent=f("TEXT_FIELD","Dane innej osoby","dane_innej_osoby",[],[{
  type:"SHOW",
  query:'("Inna osoba" in tabs[\'Dane\' in title].questions[\'sekcja_0_0\' in field.techName].field.repeatingSectionGrid[\'kto_jest_osoba_odpowiedzialna\' in field.techName].field.__userAnswer)'
 }]);
 const normal=f("TEXT_FIELD","Nazwisko","nazwisko");
 const section=f("SECTION","Dane","sekcja_0_0");
 section.repeatingSectionGrid=[w(choice,0),w(dependent,1),w(normal,2)];
 const tab={id:uuid(),title:"Dane",type:"MAIN",questions:[{x:0,y:0,cols:3,rows:4,field:section}]};
 const finishField=f("TEXT_BLOCK","","koniec");
 const finishSection=f("SECTION","Podsumowanie","sekcja_koniec");
 finishSection.repeatingSectionGrid=[w(finishField)];
 const finish={id:uuid(),title:"Koniec",type:"FINISH",questions:[w(finishSection)]};
 return {title:"Test",tabs:[tab,finish],flow:{links:[{id:uuid(),source:tab.id,target:finish.id}]}};
}
test("Label, type and required edits leave IDs, technical keys and states unchanged",()=>{
 const old=fixture();
 const fields=editableSections(old,0)[0].fields;
 const target=fields[2];
 const newer=editCOI(old,{type:"fieldUpdate",pageIndex:0,
  sectionId:old.tabs[0].questions[0].field.id,fieldId:target.id,
  values:{label:"Numer PESEL",type:"TEXT_FIELD",required:true,
    optionsText:"",format:"PESEL",tooltip:"Sprawdź dane"}});
 const found=editableSections(newer,0)[0].fields[2];
 assert.equal(found.title,"Numer PESEL");
 assert.equal(found.id,target.id);
 assert.equal(found.techName,target.techName);
 assert.deepEqual(found.validation,["REQUIRED","PESEL"]);
 assert.equal(found.tooltipMessage,"Sprawdź dane");
 assert.equal(fields[2].title,"Nazwisko");
 assert.equal(coiToJsonForms(newer).jsonSchema.properties.nazwisko.pattern,"^[0-9]{11}$");
});
test("SHOW rule remains functional after label change",()=>{
 const value=fixture(),sectionId=value.tabs[0].questions[0].field.id;
 const field=editableSections(value,0)[0].fields[0];
 const changed=editCOI(value,{type:"fieldUpdate",pageIndex:0,
  sectionId,fieldId:field.id,
  values:{label:"Osoba koordynująca",type:"RADIO",
   required:true,optionsText:"Wnioskodawca\nInna osoba",format:""}});
 const model=coiToJsonForms(changed);
 const dependent=model.pages[0].uiSchema.elements[0].elements[1];
 assert.equal(conditionIsVisible(dependent.rule,{kto_jest_osoba_odpowiedzialna:"Inna osoba"}),true);
 assert.equal(conditionIsVisible(dependent.rule,{kto_jest_osoba_odpowiedzialna:"Wnioskodawca"}),false);
 assert.throws(()=>editCOI(changed,{type:"fieldUpdate",pageIndex:0,sectionId,fieldId:field.id,
  values:{label:"Osoba",type:"RADIO",optionsText:"Wnioskodawca",format:""}}),/steruje/);
 assert.throws(()=>editCOI(changed,{type:"fieldRemove",pageIndex:0,sectionId,fieldId:field.id}),/zależy/);
});
test("Add, move and remove fields keeps collision-free technical keys and contiguous COI grids",()=>{
 const value=fixture(),sectionId=value.tabs[0].questions[0].field.id;
 const add=editCOI(value,{type:"fieldAdd",pageIndex:0,sectionId},uuid);
 let items=editableSections(add,0)[0].fields;
 assert.equal(items.length,4);
 assert.equal(items[3].title,"Nowe pole");
 const moved=editCOI(add,{type:"fieldMove",pageIndex:0,sectionId,fieldId:items[3].id,direction:-1});
 items=editableSections(moved,0)[0].fields;
 assert.equal(items[2].title,"Nowe pole");
 const removed=editCOI(moved,{type:"fieldRemove",pageIndex:0,sectionId,fieldId:items[2].id});
 assert.equal(editableSections(removed,0)[0].fields.length,3);
 const coords=removed.tabs[0].questions[0].field.repeatingSectionGrid.map(e=>e.y);
 assert.deepEqual(coords,[0,1,2]);
 assert.equal(new Set(editableSections(removed,0)[0].fields.map(x=>x.techName)).size,3);
});
test("Add, rename and remove sections without deleting last remaining section",()=>{
 const first=fixture();
 const added=editCOI(first,{type:"sectionAdd",pageIndex:0},uuid);
 assert.equal(added.tabs[0].questions.length,2);
 assert.equal(editableSections(added,0)[1].fields.length,1);
 const sectionId=editableSections(added,0)[1].id;
 const renamed=editCOI(added,{type:"sectionTitle",pageIndex:0,sectionId,title:"Inne informacje"});
 assert.equal(editableSections(renamed,0)[1].title,"Inne informacje");
 const removed=editCOI(renamed,{type:"sectionRemove",pageIndex:0,sectionId});
 assert.equal(removed.tabs[0].questions.length,1);
 assert.throws(()=>editCOI(removed,{type:"sectionRemove",pageIndex:0,
   sectionId:editableSections(removed,0)[0].id}),/ostatniej/);
});
test("Titles are exported and FINISH page cannot be edited",()=>{
 const input=fixture();
 const changed=editCOI(editCOI(input,{type:"formTitle",title:"Nowy formularz"}),
  {type:"pageTitle",pageIndex:0,title:"Dane podstawowe"});
 assert.equal(changed.title,"Nowy formularz");
 assert.equal(changed.tabs[0].title,"Dane podstawowe");
 assert.throws(()=>editCOI(changed,{type:"pageTitle",pageIndex:1,title:"Nie"}),/końcowej/);
});
test("Reject invalid choices and leave prior version unchanged",()=>{
 const input=fixture(),sectionId=input.tabs[0].questions[0].field.id,fieldId=editableSections(input,0)[0].fields[2].id;
 assert.throws(()=>editCOI(input,{type:"fieldUpdate",pageIndex:0,sectionId,fieldId,
  values:{label:"Puste radio",type:"RADIO",optionsText:""}}),/opcji/);
 assert.throws(()=>editCOI(input,{type:"fieldUpdate",pageIndex:0,sectionId,fieldId,
  values:{label:"Radio",type:"RADIO",optionsText:"A\nA"}}),/unikatowe/);
 assert.equal(input.tabs[0].questions[0].field.repeatingSectionGrid[2].field.title,"Nazwisko");
});
test("Read-only legal TEXT_BLOCK preserved when editing the other fields",()=>{
 const input=fixture(),section=input.tabs[0].questions[0].field;
 section.repeatingSectionGrid.push(w(f("TEXT_BLOCK","Klauzula informacyjna","rodo"),3));
 assert.throws(()=>editCOI(input,{type:"fieldAdd",pageIndex:0,sectionId:section.id},uuid),/tylko do odczytu/);
 assert.equal(input.tabs[0].questions[0].field.repeatingSectionGrid[3].field.type,"TEXT_BLOCK");
 assert.throws(()=>editCOI(input,{type:"sectionRemove",pageIndex:0,sectionId:section.id}),/chroniona/);
 assert.equal(editorSnapshot(editableSections(input,0)[0].fields[0]).type,"RADIO");
});

test("Renaming a page keeps JSONata SHOW references valid",()=>{
 const source=fixture(),sectionId=source.tabs[0].questions[0].field.id;
 const renamed=editCOI(source,{type:"pageTitle",pageIndex:0,title:"Osoby i dane"});
 const dep=coiToJsonForms(renamed).pages[0].uiSchema.elements[0].elements[1];
 assert.equal(dep.rule.effect,"SHOW");
 assert.equal(conditionIsVisible(dep.rule,{kto_jest_osoba_odpowiedzialna:"Inna osoba"}),true);
 assert(renamed.tabs[0].questions[0].field.repeatingSectionGrid[1].field.states[0].query.includes("Osoby i dane"));
 assert.equal(source.tabs[0].title,"Dane");
});

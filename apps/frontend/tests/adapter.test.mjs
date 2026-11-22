import test from "node:test";
import assert from "node:assert/strict";
import { coiToJsonForms, parseShowQuery, conditionIsVisible, calculateSummary, makePreviewAnswerPayload } from "../adapter.mjs";

const uuid=n=>("00000000-0000-4000-8000-"+String(n).padStart(12,"0"));
const fld=(type,name,title,options=[],states=[],validation=[])=>({
  id:uuid(Math.abs(name.length*79)), type, techName:name,title,options,
  states,validation,repeatingSectionGrid:[],
});
const wrap=f=>({x:0,y:0,rows:1,cols:3,field:f});
const section=(title,children)=>wrap({
  ...fld("SECTION","sekcja_0_0",title),
  repeatingSectionGrid:children.map(wrap),
});
function sample(){
  const choice=fld("RADIO","kto_jest_osoba_odpowiedzialna","Kto jest osobą odpowiedzialną?",
    [{id:"Wnioskodawca",name:"Wnioskodawca"},{id:"Inna osoba",name:"Inna osoba"}]);
  const query='("Inna osoba" in tabs[\'Dane wnioskodawcy\' in title].questions[\'sekcja_0_0\' in field.techName].field.repeatingSectionGrid[\'kto_jest_osoba_odpowiedzialna\' in field.techName].field.__userAnswer)';
  const dependent=fld("TEXT_FIELD","osoba_odpowiedzialna","Imię i nazwisko osoby odpowiedzialnej",[],
    [{type:"SHOW",query}]);
  const pin=fld("TEXT_FIELD","pesel","PESEL",[],[],["REQUIRED","PESEL"]);
  const doc=fld("FILE_UPLOADER","zalacznik","Oświadczenie",[],[{type:"SHOW",query}]);
  return {title:"Wniosek o wynajęcie świetlicy",tabs:[
    {id:uuid(1),type:"MAIN",title:"Dane wnioskodawcy",
      questions:[section("Wnioskodawca",[choice,dependent,pin,doc])]},
    {id:uuid(2),type:"FINISH",title:"Podsumowanie",questions:[]},
  ],flow:{links:[]}};
}

test("Recognizes supported COI SHOW condition precisely",()=>{
  const q=sample().tabs[0].questions[0].field.repeatingSectionGrid[1].field.states[0].query;
  assert.deepEqual(parseShowQuery(q),{
    value:"Inna osoba",tab:"Dane wnioskodawcy",
    section:"sekcja_0_0",source:"kto_jest_osoba_odpowiedzialna"});
  assert.equal(parseShowQuery("globalThis.alert(1)"),null);
  assert.equal(parseShowQuery("(false)"),null);
});

test("Builds real JSON Schema and UI Schema with two pages, required field and pattern",()=>{
  const result=coiToJsonForms(sample());
  assert.equal(result.jsonSchema.type,"object");
  assert.equal(result.jsonSchema.properties.pesel.pattern,"^[0-9]{11}$");
  assert.deepEqual(result.jsonSchema.required,["pesel"]);
  assert.equal(result.pages.length,2);
  assert.equal(result.pages[0].uiSchema.elements[0].type,"Group");
  assert.equal(result.pages[1].isFinish,true);
  assert.equal(result.fields.length,4);
});

test("SHOW hides dependent input until alternate person is selected",()=>{
  const model=coiToJsonForms(sample());
  const controls=model.pages[0].uiSchema.elements[0].elements;
  const dependent=controls.find(c=>c.scope.endsWith("/osoba_odpowiedzialna"));
  assert.equal(dependent.rule.effect,"SHOW");
  assert.equal(dependent.rule.condition.failWhenUndefined,true);
  assert.equal(conditionIsVisible(dependent.rule,{}),false);
  assert.equal(conditionIsVisible(dependent.rule,{kto_jest_osoba_odpowiedzialna:"Wnioskodawca"}),false);
  assert.equal(conditionIsVisible(dependent.rule,{kto_jest_osoba_odpowiedzialna:"Inna osoba"}),true);
});

test("Checkbox multi-options become array; independent checkbox is boolean",()=>{
  const data=sample();
  data.tabs[0].questions.push(section("Oświadczenia",[
    fld("CHECKBOX","legal","Zapoznałem się z warunkami"),
    fld("CHECKBOX","choices","Wybór",[{id:"A",name:"A"},{id:"B",name:"B"}]),
  ]));
  const result=coiToJsonForms(data);
  assert.equal(result.jsonSchema.properties.legal.type,"boolean");
  assert.deepEqual(result.jsonSchema.properties.choices.items.enum,["A","B"]);
});

test("Does not evaluate arbitrary JSONata",()=>{
  const data=sample();
  const f=data.tabs[0].questions[0].field.repeatingSectionGrid[1].field;
  f.states[0].query="('anything' in __proto__.constructor)";
  const result=coiToJsonForms(data);
  const dependent=result.pages[0].uiSchema.elements[0].elements[1];
  assert.equal(dependent.rule,undefined);
  assert.ok(result.warnings.some(x=>x.includes("JSONata")));
});

test("Summary counts actual answers, not hidden placeholders",()=>{
  const result=coiToJsonForms(sample());
  assert.deepEqual(calculateSummary(result,{}),{fields:4,answered:0,pages:2});
  assert.deepEqual(calculateSummary(result,{pesel:"12345678901",kto_jest_osoba_odpowiedzialna:"Inna osoba"}),
    {fields:4,answered:2,pages:2});
});

test("Does not accept invalid root",()=>{
  assert.throws(()=>coiToJsonForms(null),/brak stron/i);
});

test("Long legal COI TEXT_BLOCK is read-only and not counted as user input",()=>{
  const d=sample();
  const notice="Klauzula informacyjna "+("RODO — informacja publiczna. ".repeat(45));
  const block={...fld("TEXT_BLOCK","rodo_notice","Klauzula informacyjna"),description:
     "<html><body><p>"+notice+"</p></body></html>"};
  d.tabs.splice(1,0,{id:uuid(4),type:"MAIN",title:"Klauzula informacyjna",
    questions:[section("RODO",[block])]});
  const res=coiToJsonForms(d);
  assert.equal(res.fields.length,4);
  assert.equal(res.pages.length,3);
  assert.equal(res.pages[1].fieldCount,0);
  assert(res.pages[1].blocks[0].length>450);
  assert(!Object.keys(res.jsonSchema.properties).includes("rodo_notice"));
});

test("Companion input visibility handles multiple-choice checkbox selections",()=>{
  const data=sample();
  const tab=data.tabs[0];
  const parent=tab.questions[0].field;
  const multi=fld("CHECKBOX","metoda_dostarczenia","Metoda dostarczenia",[
    {id:"kurier",name:"kurier"},{id:"punkt",name:"punkt"}]);
  const query='("kurier" in tabs[\'Dane wnioskodawcy\' in title].questions[\'sekcja_0_0\' in field.techName].field.repeatingSectionGrid[\'metoda_dostarczenia\' in field.techName].field.__userAnswer)';
  const dependent=fld("TEXT_FIELD","adres_doreczenia","Adres doręczenia",[],[{type:"SHOW",query}]);
  parent.repeatingSectionGrid.push(wrap(multi),wrap(dependent));
  const result=coiToJsonForms(data);
  const controls=result.pages[0].uiSchema.elements[0].elements;
  const input=controls.find(c=>c.scope==="#/properties/adres_doreczenia");
  assert.deepEqual(input.rule.condition.schema,{type:"array",contains:{const:"kurier"}});
  assert.equal(conditionIsVisible(input.rule,{}),false);
  assert.equal(conditionIsVisible(input.rule,{metoda_dostarczenia:["punkt"]}),false);
  assert.equal(conditionIsVisible(input.rule,{metoda_dostarczenia:["kurier","punkt"]}),true);
});

test("Presentational group wrapper is not repeated when its sole control has the same question",()=>{
  const data=sample();
  data.tabs[0].questions=[section("Rodzaj dostawy",[
    fld("CHECKBOX","rodzaj_dostawy","Rodzaj dostawy",[
      {id:"kurier",name:"kurier"},{id:"punkt",name:"punkt"}])])];
  const result=coiToJsonForms(data);
  assert.equal(result.pages[0].uiSchema.elements.length,1);
  assert.equal(result.pages[0].uiSchema.elements[0].type,"Control");
  assert.equal(result.fields.length,1);
});

test("Answer preview never exports empty answers while COI definition remains intact",()=>{
  const data=sample();
  const preview=coiToJsonForms(data);
  assert.equal(makePreviewAnswerPayload(data,{},preview.fields.map(x=>x.key)),null);
  assert.equal(makePreviewAnswerPayload(data,{pesel:"",legal:false},["pesel","legal"]),null);
  const payload=makePreviewAnswerPayload(data,{pesel:"01234567890",hidden:"secret"},["pesel"]);
  assert.deepEqual(payload,{form:data.title,previewOnly:true,
    answers:{pesel:"01234567890"}});
  assert.equal(calculateSummary(preview,{pesel:"",kto_jest_osoba_odpowiedzialna:undefined}).answered,0);
  // The source configuration is not serialized as preview answers: it retains
  // the COI tabs and flow required by importers.
  assert.ok(Array.isArray(data.tabs) && data.flow && Object.keys(data).includes("flow"));
});

test("Closely matching heading and question do not render duplicate visible labels",()=>{
  const data=sample();
  data.tabs[0].questions=[section("Prośba o udostępnienie dokumentów",[
    fld("CHECKBOX","typ_dokumentow","Proszę o udostępnienie dokumentów",[
      {id:"papierowa",name:"papierowa"},{id:"cyfrowa",name:"cyfrowa"}])])];
  const model=coiToJsonForms(data);
  assert.equal(model.pages[0].uiSchema.elements.length,1);
  assert.equal(model.pages[0].uiSchema.elements[0].type,"Control");
});

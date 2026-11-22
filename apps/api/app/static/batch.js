/* Parallel batch conversion: bounded client-side workers, no server-side persistence. */
(() => {
"use strict";
const $ = id => document.getElementById(id);
const fileInput=$("batch-file-input"), consent=$("batch-consent");
const start=$("batch-start"), list=$("batch-results");
const summary=$("batch-summary"), exportButton=$("batch-export");
const panel=$("batch-panel");
if (!fileInput || !window.FormFlowWizard || !window.FormFlowBatchRunner) return;
const runner=window.FormFlowBatchRunner;
const MAX_FILES=runner.MAX_FILES;
let maxParallel=runner.MAX_PARALLEL;

let files=[],entries=[],active=-1,running=false,conversionReady=false,needsConsent=true;
const allowed=/\.(pdf|doc|docx|ods|xlsx|jpe?g|png)$/i;
const humanStatus={
  pending:"Oczekuje",
  processing:"Analiza w toku…",
  draft:"Szkic — wymaga ręcznej weryfikacji",
  approved:"Zatwierdzony do eksportu",
  failed:"Nie udało się przetworzyć"
};

function setSummary(text,failed=false){
  summary.textContent=text;
  summary.classList.toggle("is-error",failed);
}
function updateStart(){
  start.disabled=running||!conversionReady||files.length<1||
    files.length>MAX_FILES||(needsConsent&&!consent.checked);
  fileInput.disabled=running;
  consent.disabled=running;
}
function capture(){
  if(active<0||!entries[active])return;
  const reviewed=window.FormFlowPreview?.getApproved?.()||null;
  entries[active].approved=reviewed;
  active=-1;
  render();
}
function render(){
  list.replaceChildren();
  let approved=0,done=0;
  entries.forEach((entry,index)=>{
    const li=document.createElement("li");
    const meta=document.createElement("div");
    const name=document.createElement("strong");
    name.textContent=entry.file.name;
    const info=document.createElement("span");
    let status=entry.status;
    if(entry.approved){status="approved";approved++;}
    if(status==="draft"||status==="failed"||status==="approved")done++;
    info.textContent=humanStatus[status]||status;
    if(entry.error){info.textContent+=" — "+entry.error;}
    meta.append(name,info);
    li.append(meta);
    if(entry.data?.form){
      const button=document.createElement("button");
      button.type="button";
      button.className="button-secondary";
      button.textContent=entry.approved?"Otwórz ponownie":"Sprawdź i popraw";
      button.disabled=running;
      button.addEventListener("click",()=>openItem(index));
      li.append(button);
    }
    list.append(li);
  });
  exportButton.disabled=running||approved<1;
  exportButton.textContent=approved
    ? "Pobierz zatwierdzone formularze ZIP ("+approved+")"
    : "Pobierz zatwierdzone formularze (ZIP)";
  if(!running && entries.length){
    setSummary("Ukończono "+done+"/"+entries.length+" analiz. Zatwierdzone: "+approved+
      ". Otwórz każdy szkic, porównaj go z oryginałem i potwierdź przed eksportem.");
  }
  updateStart();
}
function openItem(index){
  if(running)return;
  if(active>=0)capture();
  const entry=entries[index];
  if(!entry?.data?.form)return;
  const form=entry.approved?.form||entry.data.form;
  const report=entry.approved?.validation||entry.data.validation;
  const opened=window.FormFlowWizard.openBatchItem({
    file:entry.file,form,validation:report,quality:entry.data.quality,
    extraction:entry.data.document?.extraction,
    inventory:entry.data.inventory,grounding:entry.data.grounding
  });
  if(opened)active=index;
  panel.open=true;
}
fileInput.addEventListener("change",()=>{
  files=Array.from(fileInput.files||[]);
  if(files.length>MAX_FILES){setSummary("Wybierz maksymalnie 10 dokumentów.",true);}
  else if(files.some(f=>!allowed.test(f.name))){setSummary("Nieobsługiwany format. Dozwolone PDF, DOC, DOCX, XLSX, ODS oraz obrazy.",true);}
  else setSummary(files.length?"Wybrano "+files.length+" dokumentów.":"");
  updateStart();
});
consent.addEventListener("change",updateStart);

start.addEventListener("click",async()=>{
  if(running||!conversionReady||!files.length||files.length>MAX_FILES||
     files.some(f=>!allowed.test(f.name))||(needsConsent&&!consent.checked))return;
  if(entries.some(e=>e.approved) && !window.confirm(
     "Nowa paczka zastąpi wcześniej zatwierdzone formularze. Czy na pewno już je pobrano?"
  ))return;
  if(!window.FormFlowWizard.canReplaceForm())return;
  const selected=[...files];
  entries=selected.map(file=>({file,status:"pending",data:null,error:"",approved:null}));
  active=-1;
  running=true;
  window.FormFlowWizard.setBatchBusy(true);
  render();
  const showProgress=()=>{
    const done=entries.filter(entry=>entry.status==="draft"||entry.status==="failed").length;
    const active=entries.filter(entry=>entry.status==="processing").length;
    setSummary("Ukończono "+done+"/"+entries.length+". Trwa "+active+
      " analiz równoległych (maks. "+maxParallel+").");
  };
  try{
    // Start up to maxParallel requests immediately, then refill the worker
    // pool as soon as any completes. Failed files do not block other jobs.
    await runner.processAll(entries,async(entry)=>{
      entry.status="processing";
      showProgress();
      render();
      try{
        const body=new FormData();
        body.append("file",entry.file,entry.file.name);
        const response=await fetch("/api/v1/forms/convert?mode=diagnostic",{
          method:"POST",body,headers:{"X-External-AI-Consent":needsConsent?"true":"false"}
        });
        const data=await window.FormFlowHTTP.readAPIResponse(response);
        if(!response.ok||!data?.form)
          throw Error(typeof data?.detail==="string"?data.detail:"Błąd HTTP "+response.status);
        entry.data=data;
        entry.status="draft";
      }catch(error){
        entry.status="failed";
        entry.error=String(error?.message||"Błąd analizy").slice(0,220);
      }finally{
        showProgress();
        render();
      }
    },maxParallel);
  }finally{
    running=false;
    window.FormFlowWizard.setBatchBusy(false);
    render();
  }
});
exportButton.addEventListener("click",async()=>{
  if(running)return;
  if(active>=0)capture();
  const reviewed=entries.filter(e=>e.approved).map(e=>({
    filename:e.file.name,form:e.approved.form
  }));
  if(!reviewed.length)return;
  exportButton.disabled=true;
  setSummary("Pakujemy zatwierdzone formularze…");
  try{
    const response=await fetch("/api/v1/forms/batch/export",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({forms:reviewed})
    });
    if(!response.ok){
      const data=await window.FormFlowHTTP.readAPIResponse(response).catch(()=>({}));
      throw Error(data.detail||"Nie udało się utworzyć ZIP.");
    }
    const blob=await response.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");
    a.href=url;a.download="formflow-formularze.zip";
    document.body.appendChild(a);
    a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),5000);
    setSummary("Pobrano ZIP z "+reviewed.length+" zatwierdzonymi formularzami.");
  }catch(error){
    setSummary(String(error?.message||"Błąd pobierania."),true);
  }finally{exportButton.disabled=false;render();}
});
window.FormFlowBatch={capture};
fetch("/api/v1/capabilities").then(window.FormFlowHTTP.readAPIResponse).then(data=>{
  conversionReady=Boolean(data.conversion);
  maxParallel=Math.min(runner.MAX_PARALLEL,
    Math.max(1,Math.floor(Number(data.max_parallel_conversions)||1)));
  needsConsent=data.model_provider!=="ollama-offline";
  if(!needsConsent)consent.closest("label").hidden=true;
  updateStart();
}).catch(()=>{conversionReady=false;updateStart();});
})();

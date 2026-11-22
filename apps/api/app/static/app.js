/* FormFlow AI — guided three-step flow. No persistence or third-party scripts. */
const $=selector=>document.querySelector(selector);
const input=$("#file-input"),zone=$("#dropzone"),result=$("#result");
const convertResult=$("#conversion-result"),limit=$("#size-limit");
const checkbox=$("#external-consent"),generateButton=$("#generate"),downloadButton=$("#download");
const providerStatus=$("#provider-status"),previewButton=$("#extract-preview");
const extractionResult=$("#extraction-result"),demoButton=$("#load-demo");
const fileConsent=$("#file-consent"),selectedFile=$("#selected-file");
const selectedFilename=$("#selected-filename"),loading=$("#wizard-loading");
const downloadStatus=$("#finish-download-status");
let currentFile=null,generated=null,externalConsentRequired=true;
let conversionAvailable=false,accepted=false,busy=false,inspectionId=0;
let currentStep=1;

function stepTo(number){
  if(![1,2,3].includes(number))return;
  currentStep=number;
  $("#step-upload").hidden=number!==1;
  $("#return-to-review").hidden=!(number===1 && generated);
  $("#step-review").hidden=number!==2;
  $("#step-finish").hidden=number!==3;
  for(const item of document.querySelectorAll(".wizard-steps li")){
    const n=Number(item.dataset.step);
    item.classList.toggle("is-active",n===number);
    item.classList.toggle("is-complete",n<number);
    if(n===number)item.setAttribute("aria-current","step");
    else item.removeAttribute("aria-current");
  }
  const heading=$("#step-"+({1:"upload",2:"review",3:"finish"}[number])+" h1");
  document.title=({1:"Dodaj dokument",2:"Sprawdź i popraw",3:"Pobierz formularz"}[number])+" — FormFlow AI";
  window.scrollTo({top:0,behavior:"instant"});
  if(number!==1 && heading)heading.focus({preventScroll:true});
}
function show(box,title,details,failed=false){
  box.hidden=false;
  box.classList.toggle("fail",Boolean(failed));
  box.replaceChildren();
  const h=document.createElement("h3");h.textContent=title;
  const pre=document.createElement("pre");pre.textContent=details;
  box.append(h,pre);
}
function markFile(ready){
  accepted=ready;
  selectedFile.hidden=!ready;
  fileConsent.hidden=!ready;
  if(ready){
    selectedFilename.textContent=currentFile?.name||"Wybrany dokument";
    result.hidden=true;
  }
  updateButton();
}
function updateButton(){
  const ready=accepted && currentFile && conversionAvailable;
  generateButton.disabled=busy||!ready||(externalConsentRequired&&!checkbox.checked);
  previewButton.disabled=busy||!accepted||!currentFile;
  demoButton.disabled=busy;
  $("#change-file").disabled=busy;
}
function setBusy(loadingNow){
  busy=loadingNow;
  loading.hidden=!loadingNow;
  zone.setAttribute("aria-disabled",String(loadingNow));
  updateButton();
}
function preserveManualEdits(message){
  return !window.FormFlowPreview?.hasEdits?.() || window.confirm(message);
}
async function inspect(file){
  if(!file||busy)return;
  if(!preserveManualEdits("Masz już ręcznie poprawiony formularz. Przed zmianą pliku pobierz gotowy JSON. Czy zastąpić bieżące dane?"))return;
  const requestId=++inspectionId;
  currentFile=null;generated=null;input.value="";
  $("#return-to-review").hidden=true;
  window.FormFlowPreview?.close?.();
  fileConsent.hidden=true;selectedFile.hidden=true;result.hidden=true;
  checkbox.checked=false;accepted=false;updateButton();
  show(result,"Sprawdzamy dokument…","Odczytujemy wybrany plik.");
  try{
    const body=new FormData();body.append("file",file,file.name);
    const response=await fetch("/api/v1/forms/inspect",{method:"POST",body});
    const data=await readAPIResponse(response);
    if(requestId!==inspectionId)return;
    if(!response.ok)throw Error(data.detail||"Nie udało się przyjąć dokumentu.");
    currentFile=file;markFile(true);
  }catch(error){
    if(requestId!==inspectionId)return;
    show(result,"Nie udało się dodać dokumentu",userFacingError(error),true);
    currentFile=null;markFile(false);
  }
}
zone.addEventListener("click",()=>{if(!busy)input.click();});
zone.addEventListener("keydown",event=>{
  if(!busy && ["Enter"," "].includes(event.key)){event.preventDefault();input.click();}
});
input.addEventListener("change",()=>inspect(input.files?.[0]));
zone.addEventListener("dragover",event=>{event.preventDefault();if(!busy)zone.classList.add("dragging");});
zone.addEventListener("dragleave",()=>zone.classList.remove("dragging"));
zone.addEventListener("drop",event=>{
  event.preventDefault();zone.classList.remove("dragging");
  if(!busy)inspect(event.dataTransfer.files?.[0]);
});
$("#change-file").addEventListener("click",()=>{if(!busy)input.click();});
checkbox.addEventListener("change",updateButton);

function showPreview(form,details){
  if(!window.FormFlowPreview?.open)throw Error("Moduł podglądu nie jest gotowy. Odśwież stronę i spróbuj ponownie.");
  generated=form;
  stepTo(2);
  window.FormFlowPreview.open(form,{...details,wizardMode:true,scrollIntoView:false});
}
/**
 * Proxy/gateway failures may have an empty or HTML body. Do not assume a
 * successful JSON parse: report HTTP status and request ID to users instead.
 */
async function readAPIResponse(response){
  let raw;
  try {
    raw=await response.text();
  }catch{
    throw Error("Połączenie zostało przerwane podczas odbierania odpowiedzi serwera. Spróbuj ponownie.");
  }
  const id=response.headers?.get("X-Request-ID");
  const suffix=id && /^[a-f0-9]{32}$/i.test(id) ? "\nNumer zgłoszenia: "+id : "";
  if(!raw.trim()){
    const reason=response.status===504||response.status===502||response.status===503
      ? "Serwer lub brama przerwały oczekiwanie na analizę PDF."
      : "Serwer nie zwrócił danych w odpowiedzi.";
    throw Error(reason+" (HTTP "+response.status+")."+suffix+
      "\nOdczyt pliku mógł się powieść, ale wynik analizy nie został dostarczony.");
  }
  try {return JSON.parse(raw);}
  catch{
    throw Error("Serwer zwrócił odpowiedź niebędącą JSON (HTTP "+response.status+
      ")."+suffix+"\nSpróbuj ponownie lub zgłoś numer zgłoszenia.");
  }
}
window.FormFlowHTTP={readAPIResponse};
function userFacingError(error){
  if(error instanceof TypeError && /fetch|network|failed/i.test(error.message||"")){
    return "Przerwano połączenie z serwerem podczas analizy. Spróbuj ponownie.";
  }
  return String(error?.message||"Nie udało się wykonać operacji.");
}
function errorFromAPI(data,response){
  let message="Wystąpił błąd („"+response.status+"”). Spróbuj ponownie.";
  if(typeof data?.detail==="string")message=data.detail;
  else if(Array.isArray(data?.detail))message=data.detail.map(x=>x.msg||String(x)).join("; ");
  const requestId=data?.request_id||response.headers?.get("X-Request-ID");
  if(requestId && /^[a-f0-9]{32}$/i.test(requestId)){
    message+="\nNumer zgłoszenia: "+requestId;
  }
  return message;
}
generateButton.addEventListener("click",async()=>{
  if(!currentFile||!accepted||busy||!conversionAvailable||
      (externalConsentRequired&&!checkbox.checked))return;
  if(!preserveManualEdits("Ponowne utworzenie formularza zastąpi Twoje poprawki. Kontynuować?"))return;
  const file=currentFile;
  setBusy(true);result.hidden=true;convertResult.hidden=true;
  try{
    const body=new FormData();body.append("file",file,file.name);
    const response=await fetch("/api/v1/forms/convert?mode=diagnostic",{
      method:"POST",headers:{"X-External-AI-Consent":externalConsentRequired?"true":"false"},body
    });
    const data=await readAPIResponse(response);
    if(!response.ok||!data.form)throw Error(errorFromAPI(data,response));
    const report=data.validation||{},quality=data.quality||{};
    const warnings=(report.errors||[]).slice(0,8).map(x=>x.message).join("\n");
    show(convertResult,"Informacje o analizie dokumentu",
      "Model: "+(data.model||"n/d")+
      "\nStrony: "+(report.summary?.tabs??"—")+
      "\nPola: "+(report.summary?.input_fields??"—")+
      "\nStruktura COI: "+(report.valid?"poprawna":"wymaga poprawy")+
      "\nKontrola jakości: "+(data.status==="generated"?"OK":"wymaga sprawdzenia przez człowieka")+
      (quality.possible_missing?.length?"\nWeryfikacja: "+quality.possible_missing.join("; "):"")+
      (warnings?"\nUwagi: "+warnings:""),
      !report.valid||data.status!=="generated");
    showPreview(data.form,{file,validation:report,quality,
      extraction:data.document?.extraction,grounding:data.grounding,
      inventory:data.inventory,source:"generated"});
  }catch(error){
    show(result,"Nie udało się przygotować formularza",
      userFacingError(error)+
      "\nMożesz spróbować ponownie. Wybrany dokument nadal jest dostępny.",true);
  }finally{setBusy(false);}
});
demoButton.addEventListener("click",async()=>{
  if(busy)return;
  if(!preserveManualEdits("Nowy przykład zastąpi bieżące poprawki. Czy kontynuować?"))return;
  setBusy(true);result.hidden=true;
  try{
    const response=await fetch("/api/v1/demo/convert");
    const data=await readAPIResponse(response);
    if(!response.ok||!data.form)throw Error(errorFromAPI(data,response));
    showPreview(data.form,{file:null,validation:data.validation,
      quality:data.quality,source:"synthetic"});
  }catch(error){
    show(result,"Przykład nie został uruchomiony",userFacingError(error),true);
  }finally{setBusy(false);}
});
previewButton.addEventListener("click",async()=>{
  if(!accepted||!currentFile||busy)return;
  previewButton.disabled=true;
  show(extractionResult,"Odczytujemy dokument…","Ta czynność działa lokalnie, bez wysyłania do OpenRouter.");
  try{
    const body=new FormData();body.append("file",currentFile,currentFile.name);
    const response=await fetch("/api/v1/forms/extract-preview",{method:"POST",body});
    const data=await readAPIResponse(response);
    if(!response.ok)throw Error(errorFromAPI(data,response));
    show(extractionResult,"Tekst dokumentu",
      "Silnik: "+(data.extraction?.engine||"lokalny")+
      "\n\n"+(data.text_preview||"Nie udało się odczytać tekstu."),false);
  }catch(error){show(extractionResult,"Błąd odczytu",userFacingError(error),true);}
  updateButton();
});

window.FormFlowWizard={
  canReplaceForm(){return preserveManualEdits("Masz niezapisane zmiany w edytorze. Przed rozpoczęciem kolejnej pracy pobierz aktualny formularz. Kontynuować?");},
  setBatchBusy(value){setBusy(Boolean(value));},
  openBatchItem({file,form,validation,quality,extraction,grounding,inventory}={}){
    if(busy||!form||!file||!preserveManualEdits("Masz ręcznie poprawiony formularz. Czy otworzyć kolejny dokument?"))return false;
    currentFile=file;checkbox.checked=true;markFile(true);
    showPreview(form,{file,validation,quality,extraction,grounding,inventory,source:"generated"});
    return true;
  },
  showFinal({form,validation}={}){
    if(!form||!validation?.valid||!validation?.schema_valid)
      throw Error("Formularz wymaga sprawdzenia przed pobraniem.");
    const count=validation.summary||{};
    $("#finish-form-title").textContent=form.title||"Formularz elektroniczny";
    $("#finish-input-count").textContent=String(count.input_fields??"–");
    $("#finish-page-count").textContent=String(count.tabs??"–");
    downloadStatus.hidden=true;
    stepTo(3);
  },
  currentStep:()=>currentStep,
};
$("#review-back").addEventListener("click",()=>{window.FormFlowBatch?.capture?.();stepTo(1);});
$("#return-to-review").addEventListener("click",()=>{if(generated)stepTo(2);});
$("#finish-back").addEventListener("click",()=>stepTo(2));
$("#finish-new").addEventListener("click",()=>{
  window.FormFlowBatch?.capture?.();
  if(!preserveManualEdits("Aby nie utracić ręcznych poprawek, pobierz najpierw plik JSON. Czy na pewno utworzyć nowy formularz?"))return;
  ++inspectionId;
  currentFile=null;generated=null;checkbox.checked=false;input.value="";
  accepted=false;window.FormFlowPreview?.close?.();
  result.hidden=true;convertResult.hidden=true;extractionResult.hidden=true;
  selectedFile.hidden=true;fileConsent.hidden=true;downloadStatus.hidden=true;
  $("#advanced-tools").open=false;
  updateButton();
  stepTo(1);
});
downloadButton.addEventListener("click",async()=>{
  const current=window.FormFlowPreview;
  if(!current?.exportCurrent){
    downloadStatus.hidden=false;
    downloadStatus.textContent="Podgląd formularza nie jest dostępny. Wróć do poprzedniego kroku.";
    return;
  }
  downloadButton.disabled=true;
  try{
    const exported=await current.exportCurrent();
    downloadStatus.hidden=false;
    downloadStatus.textContent=exported
      ?"✓ Plik został pobrany. Możesz znaleźć go w folderze Pobrane."
      :"Nie udało się pobrać pliku. Wróć do kroku 2 i sprawdź formularz.";
  }catch(error){
    downloadStatus.hidden=false;
    downloadStatus.textContent="Nie udało się pobrać pliku: "+(error.message||"Błąd.");
  }finally{downloadButton.disabled=false;}
});
fetch("/api/v1/capabilities").then(readAPIResponse).then(data=>{
  const mb=Math.round(data.max_upload_bytes/1024/1024);
  limit.textContent=mb+" MB";
  conversionAvailable=Boolean(data.conversion);
  externalConsentRequired=data.model_provider!=="ollama-offline";
  providerStatus.textContent=(conversionAvailable?"AI dostępne":"AI niedostępne")+
    (data.pdf_ocr_enabled?" · Odczyt skanów aktywny":"");
  if(!externalConsentRequired){
    checkbox.closest("label").hidden=true;
    $(".file-consent p").textContent="Dokument będzie analizowany przez lokalny model w trybie testowym.";
  }
  updateButton();
}).catch(()=>{
  providerStatus.textContent="Usługa jest chwilowo niedostępna";
  conversionAvailable=false;updateButton();
});
stepTo(1);

const input=document.querySelector('#file-input');
const zone=document.querySelector('#dropzone');
const result=document.querySelector('#result');
const convertResult=document.querySelector('#conversion-result');
const limit=document.querySelector('#size-limit');
const checkbox=document.querySelector('#external-consent');
const generateButton=document.querySelector('#generate');
const downloadButton=document.querySelector('#download');
const providerStatus=document.querySelector('#provider-status');
let currentFile=null;
let generated=null;

function show(container,title,details,failed=false){
  container.hidden=false;
  container.classList.toggle('fail',failed);
  container.replaceChildren();
  const heading=document.createElement('h3');
  heading.textContent=title;
  const body=document.createElement('pre');
  body.textContent=details;
  container.append(heading,body);
}
function updateButton(){
  generateButton.disabled=!currentFile||!checkbox.checked;
}
async function inspect(file){
  if(!file)return;
  currentFile=file;
  generated=null;
  downloadButton.hidden=true;
  updateButton();
  show(result,'Sprawdzanie dokumentu…',file.name);
  const body=new FormData();body.append('file',file,file.name);
  try{
    const response=await fetch('/api/v1/forms/inspect',{method:'POST',body});
    const data=await response.json();
    show(result,response.ok?'✓ Dokument zaakceptowany':'✕ Plik odrzucony',
       response.ok?('Nazwa: '+data.document.filename+'\nFormat: '+data.document.detected_mime+'\nWielkość: '+(data.document.size_bytes/1024).toFixed(1)+' KB'):
                  (data.detail||'Błąd walidacji'),!response.ok);
    if(!response.ok){currentFile=null;updateButton();}
  }catch(e){show(result,'Błąd sieci','Nie udało się sprawdzić pliku.',true);}
}
zone.addEventListener('click',()=>input.click());
zone.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();input.click();}});
input.addEventListener('change',()=>inspect(input.files[0]));
zone.addEventListener('dragover',e=>{e.preventDefault();zone.classList.add('dragging');});
zone.addEventListener('dragleave',()=>zone.classList.remove('dragging'));
zone.addEventListener('drop',e=>{e.preventDefault();zone.classList.remove('dragging');inspect(e.dataTransfer.files[0]);});
checkbox.addEventListener('change',updateButton);

generateButton.addEventListener('click',async()=>{
  if(!currentFile||!checkbox.checked)return;
  generateButton.disabled=true;
  show(convertResult,'Generowanie przez Qwen…','Dokument jest analizowany przez zewnętrzny model. Nie zamykaj karty.');
  const payload=new FormData();payload.append('file',currentFile,currentFile.name);
  try{
    const response=await fetch('/api/v1/forms/convert?mode=diagnostic',{
      method:'POST',headers:{'X-External-AI-Consent':'true'},body:payload});
    const data=await response.json();
    if(!response.ok)throw Error(data.detail||'Błąd generowania.');
    generated=data.form;
    const report=data.validation;const quality=data.quality||{};
    const errors=(report.errors||[]).slice(0,10).map(v=>v.code+': '+v.message).join('\n');
    show(convertResult,data.status==='generated'?'✓ JSON COI wygenerowany':'JSON wymaga kontroli',
        'Model: '+data.model+'\nEkstrakcja: '+(data.document?.extraction?.engine||'local')+'\nStrony: '+report.summary.tabs+
        '\nPola (z sekcjami): '+report.summary.fields_including_sections+
        '\nWeryfikacja strukturalna: '+(report.valid?'OK':'BŁĘDY')+
        '\nOficjalny JSON Schema COI: '+(report.schema_valid?'ZGODNY':'NIEZGODNY')+
        '\nKontrola kompletności: '+(quality.ok?'OK':'WYMAGA WERYFIKACJI')+
        '\nPrawdopodobnie pominięte pola: '+((quality.possible_missing||[]).join(', ')||'brak')+
        (errors?'\n'+errors:''),!report.valid||!quality.ok);
    downloadButton.hidden=!report.valid||!quality.ok;
  }catch(e){show(convertResult,'Konwersja nieudana',e.message||'Błąd połączenia.',true);}
  updateButton();
});
downloadButton.addEventListener('click',()=>{
  if(!generated)return;
  const blob=new Blob([JSON.stringify(generated,null,2)],{type:'application/json;charset=utf-8'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;a.download='formflow-coi.json';a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
});
fetch('/api/v1/capabilities').then(r=>r.json()).then(data=>{
  limit.textContent=Math.round(data.max_upload_bytes/1024/1024)+' MB';
  providerStatus.textContent=data.conversion?'● OpenRouter DEV aktywny':'● AI wyłączone';
  generateButton.disabled=!data.conversion;
}).catch(()=>{providerStatus.textContent='● Brak połączenia';});

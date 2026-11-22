import React,{useEffect,useState} from "react";
import {editableSections,editorSnapshot,EDITABLE_TYPES,FORMAT_VALIDATORS} from "./editor.mjs";

const DISPLAY=Object.fromEntries(EDITABLE_TYPES);
function FieldInspector({item,pageIndex,sectionId,sections,onAction,onAfterRemove,onTransfer}){
  const [draft,setDraft]=useState(()=>editorSnapshot(item));
  const [saved,setSaved]=useState(false);
  const change=(prop,value)=>{setDraft(previous=>({...previous,[prop]:value}));setSaved(false);};
  const choices=["RADIO","SELECT","CHECKBOX"].includes(draft.type);
  const formatEnabled=["TEXT_FIELD","TEXTAREA"].includes(draft.type);
  function submit(event){
    event.preventDefault();
    const success=onAction({type:"fieldUpdate",pageIndex,sectionId,fieldId:item.id,values:{
      ...draft,format:formatEnabled?draft.format:"",
    }});
    if(success)setSaved(true);
  }
  function remove(){
    if(!window.confirm('Usunąć pole „'+item.title+'”? Możesz potem użyć „Cofnij”.'))return;
    const success=onAction({type:"fieldRemove",pageIndex,sectionId,fieldId:item.id});
    if(success)onAfterRemove();
  }
  return <form className="ff-field-inspector" onSubmit={submit}>
    <div className="ff-inspector-kicker">EDYCJA POLA</div>
    <h4>{item.title}</h4>
    <label htmlFor="ff-edit-label">Etykieta pytania</label>
    <input id="ff-edit-label" required maxLength={220} value={draft.label}
      onChange={e=>change("label",e.target.value)}/>
    <label htmlFor="ff-edit-type">Typ odpowiedzi</label>
    <select id="ff-edit-type" value={draft.type} onChange={e=>change("type",e.target.value)}>
      {EDITABLE_TYPES.map(([value,label])=><option value={value} key={value}>{label}</option>)}
    </select>
    <label className="ff-editor-checkbox"><input type="checkbox" checked={draft.required}
      onChange={e=>change("required",e.target.checked)}/>
      <span>Odpowiedź wymagana</span>
    </label>
    {choices && <div className="ff-editor-control">
      <label htmlFor="ff-edit-options">Opcje wyboru — jedna w wierszu</label>
      <textarea id="ff-edit-options" value={draft.optionsText} rows={5}
        placeholder={"Tak\nNie"} onChange={e=>change("optionsText",e.target.value)}/>
      <span className="ff-editor-help">
        Wybory sterujące innymi polami muszą zachować wymagane opcje. Dla słowników zewnętrznych dostępne wartości nie są wczytywane w tym edytorze.
      </span>
    </div>}
    {formatEnabled && <div className="ff-editor-control">
      <label htmlFor="ff-edit-format">Dodatkowa walidacja</label>
      <select id="ff-edit-format" value={draft.format} onChange={e=>change("format",e.target.value)}>
        {FORMAT_VALIDATORS.map(([value,label])=><option value={value} key={value}>{label}</option>)}
      </select>
    </div>}
    <label htmlFor="ff-edit-tooltip">Podpowiedź dla użytkownika</label>
    <textarea id="ff-edit-tooltip" maxLength={450} rows={3} value={draft.tooltip}
      placeholder="Opcjonalny opis pola" onChange={e=>change("tooltip",e.target.value)}/>
    <div className="ff-editor-control">
      <label htmlFor="ff-edit-section">Sekcja, do której należy pole</label>
      <select id="ff-edit-section" value={sectionId} disabled={sections.length<2}
        onChange={e=>onTransfer(item.id,sectionId,e.target.value)}>
        {sections.map(section=><option key={section.id} value={section.id}>{section.title}</option>)}
      </select>
      <span className="ff-editor-help">Przenieś pole do innej sekcji. Zawartość i identyfikator pola zostaną zachowane.</span>
    </div>
    <div className="ff-editor-tech">Identyfikator techniczny (zachowany): <code>{item.techName}</code></div>
    <div className="ff-inspector-actions">
      <button type="submit" className="ff-primary">Zastosuj zmianę</button>
      <button type="button" className="ff-danger" onClick={remove}>Usuń pole</button>
    </div>
    {saved && <p className="ff-editor-success" role="status">Zmiana zastosowana. Przed eksportem zapisz cały formularz.</p>}
  </form>;
}
function SectionHeading({section,pageIndex,onAction,onRemove}){
  const [renaming,setRenaming]=useState(false);
  const [name,setName]=useState(section.title);
  useEffect(()=>{setName(section.title);},[section.title]);
  function submit(event){
    event.preventDefault();
    if(onAction({type:"sectionTitle",pageIndex,sectionId:section.id,title:name}))
      setRenaming(false);
  }
  return <div className="ff-editor-section-top">
    {renaming ? <form onSubmit={submit} className="ff-editor-inline-rename">
      <label htmlFor={"section-name-"+section.id}>Nazwa sekcji</label>
      <input id={"section-name-"+section.id} maxLength={220} required value={name}
        onChange={e=>setName(e.target.value)}/>
      <button type="submit" className="ff-quiet">Zapisz</button>
      <button type="button" className="ff-quiet" onClick={()=>setRenaming(false)}>Anuluj</button>
    </form> : <>
      <h4>{section.title}</h4>
      <div>
        <button type="button" className="ff-tiny" onClick={()=>setRenaming(true)}>Zmień nazwę</button>
        {!section.readonly && <button type="button" className="ff-tiny danger" onClick={()=>onRemove(section)}>Usuń sekcję</button>}
      </div>
    </>}
  </div>;
}
export function EditorPanel({form,pageIndex,onAction,onUndo,canUndo,onError}){
  const tab=form.tabs[pageIndex],sections=editableSections(form,pageIndex);
  const [selected,setSelected]=useState(null);
  const [titleInput,setTitleInput]=useState(form.title);
  const [pageInput,setPageInput]=useState(tab.title);
  useEffect(()=>{setSelected(null);setPageInput(tab.title);},[pageIndex]);
  useEffect(()=>{setTitleInput(form.title);},[form.title]);
  useEffect(()=>{setPageInput(tab.title);},[tab.title]);
  const chosen=selected?sections.flatMap(s=>s.fields.map(f=>({...f,sectionId:s.id})))
    .find(f=>f.id===selected.fieldId && f.sectionId===selected.sectionId):null;
  function addField(section){
    const next=onAction({type:"fieldAdd",pageIndex,sectionId:section.id});
    if(next){
      const fresh=editableSections(next,pageIndex).find(s=>s.id===section.id);
      const last=fresh?.fields[fresh.fields.length-1];
      if(last)setSelected({sectionId:section.id,fieldId:last.id});
    }
  }
  function transferField(fieldId,sectionId,targetSectionId){
    if(sectionId===targetSectionId)return;
    const next=onAction({type:"fieldMoveSection",pageIndex,sectionId,fieldId,targetSectionId});
    if(next)setSelected({sectionId:targetSectionId,fieldId});
  }
  function removeSection(section){
    if(!window.confirm('Usunąć sekcję „'+section.title+'” i wszystkie jej pytania?'))return;
    if(onAction({type:"sectionRemove",pageIndex,sectionId:section.id}))setSelected(null);
  }
  return <div className="ff-editor-workspace">
    <div className="ff-editor-headline">
      <div><strong>Edytor definicji formularza</strong>
        <p>Wskaż pytanie, aby poprawić błąd AI. Edycja zmienia eksportowany JSON COI.</p>
      </div>
      <button className="ff-quiet" type="button" disabled={!canUndo} onClick={()=>{
        onUndo();setSelected(null);}}>↶ Cofnij ostatnią zmianę</button>
    </div>
    <div className="ff-editor-titles">
      <form onSubmit={e=>{e.preventDefault();onAction({type:"formTitle",title:titleInput});}}>
        <label htmlFor="ff-edit-form-title">Tytuł formularza</label>
        <div><input id="ff-edit-form-title" value={titleInput} maxLength={255} required
          onChange={e=>setTitleInput(e.target.value)}/>
          <button type="submit" className="ff-quiet">Zapisz</button></div>
      </form>
      <form onSubmit={e=>{e.preventDefault();onAction({type:"pageTitle",pageIndex,title:pageInput});}}>
        <label htmlFor="ff-edit-page-title">Tytuł bieżącej strony</label>
        <div><input id="ff-edit-page-title" value={pageInput} maxLength={220} required
          onChange={e=>setPageInput(e.target.value)}/>
          <button type="submit" className="ff-quiet">Zapisz</button></div>
      </form>
    </div>
    <div className="ff-editor-columns">
      <div className="ff-editor-outline">
        {sections.map(section=><section key={section.id} className="ff-editor-section">
          <SectionHeading section={section} pageIndex={pageIndex}
            onAction={onAction} onRemove={removeSection}/>
          <div className="ff-editor-fields">
            {section.fields.map((field,index)=><div key={field.id} className={"ff-editor-field-row"+
              (selected?.fieldId===field.id?" is-selected":"")}>
              <button type="button" className="ff-editor-field-select"
                aria-pressed={selected?.fieldId===field.id}
                onClick={()=>setSelected({sectionId:section.id,fieldId:field.id})}>
                <span className="ff-editor-field-name">{field.title}</span>
                <span className="ff-editor-field-kind">{DISPLAY[field.type]||field.type}
                  {(field.validation||[]).includes("REQUIRED")?" · wymagane":""}</span>
              </button>
              <div className="ff-editor-move">
                <button type="button" aria-label={"Przesuń w górę: "+field.title}
                  disabled={index===0} onClick={()=>onAction({type:"fieldMove",pageIndex,
                    sectionId:section.id,fieldId:field.id,direction:-1})}>↑</button>
                <button type="button" aria-label={"Przesuń w dół: "+field.title}
                  disabled={index===section.fields.length-1}
                  onClick={()=>onAction({type:"fieldMove",pageIndex,
                    sectionId:section.id,fieldId:field.id,direction:1})}>↓</button>
              </div>
            </div>)}
          </div>
          {section.readonly && <div className="ff-editor-info-lock">Treść informacyjna tej sekcji jest chroniona i pozostaje tylko do odczytu.</div>}
          {!section.readonly && <button className="ff-add-field" type="button"
            onClick={()=>addField(section)}>+ Dodaj pole do sekcji</button>}
        </section>)}
        <button className="ff-add-section" type="button" onClick={()=>{
          const next=onAction({type:"sectionAdd",pageIndex});
          if(next){
            const last=editableSections(next,pageIndex).at(-1);
            setSelected(last?.fields?.[0]?{sectionId:last.id,fieldId:last.fields[0].id}:null);
          }
        }}>+ Dodaj sekcję</button>
      </div>
      <aside className="ff-editor-side">
        {chosen ? <FieldInspector key={chosen.id} item={chosen} pageIndex={pageIndex}
          sectionId={selected.sectionId} sections={sections} onAction={onAction}
          onTransfer={transferField} onAfterRemove={()=>setSelected(null)}/>
        : <div className="ff-editor-no-selection">
          <div className="ff-editor-spark">✎</div>
          <strong>Wybierz pole do poprawy</strong>
          <p>Kliknij pytanie po lewej stronie. Możesz zmienić jego nazwę, typ, wymagane odpowiedzi, opcje wyboru i podpowiedź.</p>
          <p>Możesz też dodawać, usuwać, przestawiać i przenosić pola między sekcjami. Identyfikatory oraz istniejące zależności pozostają chronione.</p>
        </div>}
      </aside>
    </div>
    <p className="ff-editor-footer-note">Zmiany są przechowywane tylko w bieżącej karcie przeglądarki. Po weryfikacji użyj „Pobierz poprawiony JSON COI”, żeby nie utracić efektów pracy.</p>
  </div>;
}

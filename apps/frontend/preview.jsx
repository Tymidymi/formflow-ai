import React, { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { createRoot } from "react-dom/client";
import { JsonForms, withJsonFormsControlProps } from "@jsonforms/react";
import { vanillaCells, vanillaRenderers } from "@jsonforms/vanilla-renderers";
import { coiToJsonForms, calculateSummary, conditionIsVisible, makePreviewAnswerPayload, validateAnswerCells } from "./adapter.mjs";
import { editCOI } from "./editor.mjs";
import { EditorPanel } from "./EditorPanel.jsx";
import "./preview.css";

function FileNameControl(props) {
  const { visible, enabled, label, path, data, handleChange, errors, required } = props;
  if (!visible) return null;
  return <div className="ff-custom">
    <label>{label}{required && <span className="ff-required"> *</span>}</label>
    <input aria-label={label} disabled={!enabled} type="file" onChange={e => {
      handleChange(path, e.target.files?.[0]?.name || "");
    }}/>
    {data && <div className="ff-mini-note">Wybrano: {data} · w podglądzie plik nie jest wysyłany</div>}
    {errors && <small className="ff-error">{errors}</small>}
  </div>;
}
function RadioControl(props) {
  const { visible, enabled, label, path, data, handleChange, schema, required, errors } = props;
  if (!visible) return null;
  return <fieldset className="ff-choice-group" disabled={!enabled}>
    <legend>{label}{required && <span className="ff-required"> *</span>}</legend>
    <div className="ff-choice-items">{(schema.enum || []).map(value =>
      <label key={String(value)} className={"ff-choice" + (data === value ? " is-checked" : "")}>
        <input type="radio" name={path} checked={data === value} value={value}
          onChange={() => handleChange(path, value)}/>
        <span>{value}</span>
      </label>)}</div>
    {errors && <small className="ff-error">{errors}</small>}
  </fieldset>;
}
function CheckboxArrayControl(props) {
  const { visible, enabled, label, path, data, handleChange, schema, errors } = props;
  if (!visible) return null;
  const selected = Array.isArray(data) ? data : [];
  return <fieldset className="ff-choice-group" disabled={!enabled}>
    <legend>{label}</legend>
    <div className="ff-choice-items">{(schema.items?.enum || []).map(value =>
      <label className={"ff-choice" + (selected.includes(value) ? " is-checked" : "")} key={String(value)}>
        <input type="checkbox" checked={selected.includes(value)} onChange={event => {
          handleChange(path, event.target.checked ? [...selected, value] : selected.filter(x => x !== value));
        }}/>
        <span>{value}</span>
      </label>)}</div>
    {errors && <small className="ff-error">{errors}</small>}
  </fieldset>;
}
function resolveControlSchema(ui, schema) {
  const pointer = typeof ui?.scope === "string" ? ui.scope.split("/").pop() : "";
  return schema?.properties?.[pointer] || schema || {};
}
const plMessages = {
  "error.required": "To pole jest wymagane.",
  "error.pattern": "Wpisz wartość we właściwym formacie.",
  "error.format": "Niepoprawny format danych.",
  "error.const": "Zaznacz wymagane potwierdzenie.",
  "error.enum": "Wybierz jedną z dostępnych opcji.",
  "error.minimum": "Wartość jest zbyt mała.",
  "error.minItems": "Wybierz przynajmniej jedną odpowiedź.",
};
const plTranslate = (key, fallback) => plMessages[key] ?? fallback;
const polishI18n = { locale: "pl", translate: plTranslate };
const renderers = [
  { tester: (ui, schema) => ui?.type === "Control" && resolveControlSchema(ui, schema).format === "file-name-preview" ? 15 : -1, renderer: withJsonFormsControlProps(FileNameControl) },
  { tester: (ui, schema) => ui?.type === "Control" && ui?.options?.format === "radio" && Array.isArray(resolveControlSchema(ui, schema).enum) ? 15 : -1, renderer: withJsonFormsControlProps(RadioControl) },
  { tester: (ui, schema) => ui?.type === "Control" && resolveControlSchema(ui, schema).type === "array" && Array.isArray(resolveControlSchema(ui, schema).items?.enum) ? 15 : -1, renderer: withJsonFormsControlProps(CheckboxArrayControl) },
  ...vanillaRenderers,
];
function download(name, content, mime) {
  const blob = new Blob([content], {type: mime});
  const uri = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = uri;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(uri), 1200);
}
function PrintValue({value}) {
  if (typeof value === "boolean") return <>{value ? "Tak" : "Nie"}</>;
  if (Array.isArray(value)) return <>{value.join(", ") || "—"}</>;
  return <>{value === undefined || value === null || value === "" ? "—" : String(value)}</>;
}
function DocumentView({file, extraction}) {
  const [uri, setUri] = useState(null);
  const [loadedText, setLoadedText] = useState(extraction?.text_preview || "");
  const [loading, setLoading] = useState(false);
  const [failure, setFailure] = useState("");
  useEffect(() => {
    if (!file || (!file.type.startsWith("image/") && !/\.pdf$/i.test(file.name))) return undefined;
    const objectURL = URL.createObjectURL(file);
    setUri(objectURL);
    return () => { URL.revokeObjectURL(objectURL); setUri(null); };
  }, [file]);
  async function getText() {
    if (!file || loading) return;
    setLoading(true); setFailure("");
    try {
      const fd = new FormData();
      fd.append("file", file, file.name);
      const result = await fetch("/api/v1/forms/extract-preview", {method:"POST", body:fd});
      const json = await result.json();
      if (!result.ok) throw Error(json.detail || "Nie udało się odczytać dokumentu.");
      setLoadedText(json.text_preview || "");
    } catch (error) {setFailure(error.message);} finally {setLoading(false);}
  }
  if (!file) return <div className="ff-empty">Nie wybrano pliku źródłowego. Przykład demonstracyjny nie zawiera prawdziwego dokumentu.</div>;
  const isPdf = /\.pdf$/i.test(file.name);
  const isImage = /\.(png|jpe?g)$/i.test(file.name);
  return <div className="ff-original">
    <div className="ff-original-toolbar">
      <div><strong>{file.name}</strong><span>{(file.size/1024).toFixed(0)} KB · plik wybrany lokalnie</span></div>
      <button className="ff-quiet" type="button" onClick={getText} disabled={loading}>
        {loading ? "Odczytywanie..." : "Pokaż wyodrębniony tekst"}
      </button>
    </div>
    {isPdf && uri && <iframe className="ff-docframe" title="Oryginalny dokument PDF" src={uri}/>}
    {isImage && uri && <img className="ff-document-image" src={uri} alt="Oryginalny formularz"/>}
    {!isPdf && !isImage && <p className="ff-note">Pliki Office nie mają podglądu w przeglądarce. Możesz przejrzeć tekst pobrany przez lokalny ekstraktor.</p>}
    {failure && <p role="alert" className="ff-error">{failure}</p>}
    {loadedText && <pre className="ff-extracted">{loadedText}</pre>}
  </div>;
}
function PreviewApp({form, file, extraction, validation, quality, grounding, inventory, source, wizardMode=false}) {
  const [pageIndex, setPageIndex] = useState(0);
  const [view, setView] = useState("form");
  const [answers, setAnswers] = useState({});
  const [errors, setErrors] = useState([]);
  const [showWarnings, setShowWarnings] = useState(false);
  const [showValidation, setShowValidation] = useState(false);
  const [workingForm, setWorkingForm] = useState(() => structuredClone(form));
  const [editing, setEditing] = useState(false);
  const [reviewConfirmed, setReviewConfirmed] = useState(false);
  const manualReviewRequired = source === "generated";
  const [editError, setEditError] = useState("");
  const [editMessage, setEditMessage] = useState("");
  const [validating, setValidating] = useState(false);
  const [savedReview, setSavedReview] = useState(validation || null);
  const history = useRef([]);
  const editStart = useRef(null);
  const hasEdits = useMemo(() => JSON.stringify(form)!==JSON.stringify(workingForm), [form,workingForm]);
  const model = useMemo(() => coiToJsonForms(workingForm), [workingForm]);
  const {jsonSchema, pages, fields, warnings} = model;
  const contentErrors = useMemo(() => validateAnswerCells(fields,answers),[fields,answers]);
  const page = pages[pageIndex] || pages[0];
  const summary = calculateSummary(model, answers);
  function changeDefinition(action) {
    try {
      const next = editCOI(workingForm,action);
      history.current.push(workingForm);
      if (history.current.length > 40) history.current.shift();
      setWorkingForm(next);
      setSavedReview(null);
      setReviewConfirmed(false);
      setEditError("");
      setEditMessage("Zmiana zastosowana. Zapisz poprawki, aby sprawdzić strukturę COI.");
      return next;
    } catch (error) {
      setEditError(error.message || "Błąd edycji pola.");
      return null;
    }
  }
  function undoDefinition() {
    if (!history.current.length) return;
    setWorkingForm(history.current.pop());
    setSavedReview(null);
    setReviewConfirmed(false);
    setEditError("");
    setEditMessage("Cofnięto ostatnią zmianę.");
  }
  function startEditing() {
    editStart.current = structuredClone(workingForm);
    history.current=[];
    setEditing(true);
    setReviewConfirmed(false);
    setView("form");
    if (page?.isFinish) setPageIndex(0);
    setEditError("");
    setEditMessage("");
  }
  function cancelEditing() {
    if (history.current.length && !window.confirm("Porzucić niezapisane zmiany z tej sesji edycji?")) return;
    if (editStart.current) setWorkingForm(editStart.current);
    history.current=[];
    setEditing(false);
    setEditError("");
    setEditMessage("Anulowano ostatnią sesję edycji.");
  }
  async function checkCOI() {
    setValidating(true);
    setEditError("");
    try {
      const response = await fetch("/api/v1/forms/validate-json", {
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify(workingForm)
      });
      const data=await response.json();
      if (!response.ok || !data.valid || !data.schema_valid) {
        setEditError("Konfiguracja COI wymaga poprawy: "+(
          data.errors||[]).slice(0,4).map(x=>x.message).join("; "));
        setSavedReview(data);
        return false;
      }
      if ((data.summary?.input_fields ?? 0) < 1) {
        setEditError("Formularz nie zawiera żadnego pola do wypełnienia. Dodaj brakujące pytania przed eksportem.");
        setSavedReview(data);
        return false;
      }
      setSavedReview(data);
      return data;
    } catch (error) {
      setEditError("Nie można zweryfikować JSON COI: "+(error.message||"błąd sieci"));
      return false;
    } finally {setValidating(false);}
  }
  async function saveEditing() {
    if (await checkCOI()) {
      history.current=[];
      editStart.current=structuredClone(workingForm);
      setEditing(false);
      setReviewConfirmed(false);
      setAnswers({});
      setErrors([]);
      setShowValidation(false);
      setEditMessage("Poprawki zapisane w tej karcie i zweryfikowane przez walidator COI. Pobierz JSON, aby zachować plik.");
      const button=document.getElementById("download");
      if(button) button.hidden=false;
    }
  }
  async function exportEditedCOI() {
    if(editing) {
      setEditError("Najpierw zapisz poprawki i sprawdź wynik walidacji COI.");
      return false;
    }
    if (manualReviewRequired && !reviewConfirmed) {
      setEditError("Najpierw porównaj każdą stronę z oryginałem i potwierdź kontrolę formularza.");
      return false;
    }
    if (!(await checkCOI())) return false;
    download("formflow-coi-poprawiony.json", JSON.stringify(workingForm,null,2), "application/json;charset=utf-8");
    setEditMessage("Pobrano zweryfikowaną konfigurację COI. Plik zachowuje poprawki.");
    return true;
  }
  async function advanceToFinal() {
    if(editing) {
      setEditError("Najpierw zapisz poprawki, a następnie przejdź dalej.");
      return;
    }
    if (manualReviewRequired && !reviewConfirmed) {
      setEditError("Najpierw porównaj każdą stronę z oryginałem i potwierdź kontrolę formularza.");
      return;
    }
    const report=await checkCOI();
    if(!report)return;
    if(!window.FormFlowWizard?.showFinal){
      setEditError("Kreator jest niedostępny. Odśwież stronę i spróbuj ponownie.");
      return;
    }
    window.FormFlowWizard.showFinal({form:workingForm,validation:report});
  }
  useEffect(() => {
    if(window.FormFlowPreview) {
      window.FormFlowPreview.exportCurrent=exportEditedCOI;
      window.FormFlowPreview.hasEdits=()=>hasEdits;
      window.FormFlowPreview.getApproved=()=>
        !editing && reviewConfirmed && savedReview?.valid && savedReview?.schema_valid
          ? {form:structuredClone(workingForm),validation:structuredClone(savedReview)} : null;
    }
    return () => {
      if(window.FormFlowPreview) {
        window.FormFlowPreview.exportCurrent=null;
        window.FormFlowPreview.hasEdits=()=>false;
        window.FormFlowPreview.getApproved=null;
      }
    };
  },[workingForm,editing,hasEdits,reviewConfirmed,savedReview]);
  useEffect(() => {
    const guard=event => {
      if(hasEdits){
        event.preventDefault();
        event.returnValue="";
      }
    };
    window.addEventListener("beforeunload",guard);
    return () => window.removeEventListener("beforeunload",guard);
  },[hasEdits]);
  const handleChange = useCallback(({data, errors: nextErrors}) => {
    setAnswers(prev => JSON.stringify(prev) === JSON.stringify(data) ? prev : data || {});
    setErrors(Array.isArray(nextErrors) ? nextErrors : []);
  }, []);
  const clearAnswers = () => {
    if (window.confirm("Wyczyścić wpisane odpowiedzi z podglądu?")) {
      setAnswers({});
      setErrors([]);
      setPageIndex(0);
      setShowValidation(false);
    }
  };
  const exportAnswers = () => {
    if (summary.answered === 0) return false;
    if (contentErrors.length) {
      setShowValidation(true);
      return false;
    }
    const visible = new Set(model.fields.filter(item => {
      const controls = [];
      function walk(elements) {
        for (const e of elements || []) {
          if (e.type === "Control") controls.push(e);
          else if (Array.isArray(e.elements)) walk(e.elements);
        }
      }
      for (const page of model.pages) walk(page.uiSchema.elements);
      const rule = controls.find(control => control.scope === "#/properties/" + item.key)?.rule;
      return conditionIsVisible(rule, answers);
    }).map(field => field.key));
    const payload=makePreviewAnswerPayload(workingForm,answers,visible);
    if(!payload)return false;
    download("formflow-odpowiedzi-PODGLAD.json", JSON.stringify(payload,null,2), "application/json;charset=utf-8");
    return true;
  };

  return <div className="ff-app">
    <div className="ff-top">
      <div className="ff-kicker">{wizardMode?"FORMULARZ DO SPRAWDZENIA":"PODGLĄD WYGENEROWANEJ E-USŁUGI"}</div>
      <div className="ff-heading-row">
        <div><h2>{workingForm.title || "Formularz COI"}</h2>
          <p>{editing
            ? "Wybierz pytanie i popraw je. Na koniec naciśnij „Zapisz poprawki”."
            : "Obejrzyj przygotowane pytania. Jeśli są błędne, kliknij „Popraw pytania”."}</p>
        </div>
        <div className="ff-stats">
          <div><strong>{summary.fields}</strong><span>pól</span></div>
          <div><strong>{summary.pages}</strong><span>stron</span></div>
          <div><strong>{summary.answered}</strong><span>wypełnionych</span></div>
        </div>
      </div>
      <div className="ff-edit-toolbar">
        {editing ? <>
          <span className="ff-edit-indicator">✎ TRYB EDYCJI</span>
          <button type="button" className="ff-quiet" onClick={cancelEditing}>Anuluj edycję</button>
          <button type="button" className="ff-primary" disabled={validating} onClick={saveEditing}>
            {validating?"Sprawdzanie…":"✓ Zapisz poprawki"}
          </button>
        </> : <>
          {hasEdits && <span className="ff-edited-label">● Formularz poprawiony ręcznie</span>}
          <button type="button" className="ff-quiet" onClick={startEditing}>✎ Popraw pytania</button>
          <button type="button" className="ff-primary" disabled={validating || (manualReviewRequired && !reviewConfirmed)}
            onClick={wizardMode ? advanceToFinal : exportEditedCOI}>
            {validating?"Sprawdzanie…":wizardMode?"Wszystko się zgadza — dalej →":"Pobierz JSON COI"}
          </button>
        </>}
      </div>
      {editError && <p role="alert" className="ff-edit-error">{editError}</p>}
      {editMessage && !editError && <p role="status" className="ff-edit-message">{editMessage}</p>}
    </div>
    <div className="ff-switch" role="tablist" aria-label="Widoki dokumentu">
      {(wizardMode
        ? [["form","Przygotowany formularz"],["original","Oryginalny dokument"]]
        : [["form","Formularz cyfrowy"],["original","Oryginał"],["json","JSON COI"]]).map(([id,name]) =>
        <button role="tab" type="button" key={id} aria-selected={view === id}
          className={view===id?"selected":""} onClick={()=>setView(id)}>{name}</button>)}
    </div>
    {savedReview && !savedReview.valid && <div className="ff-warning" role="alert">
      Walidator COI wskazuje problemy. Formularz ma charakter roboczy.</div>}
    {manualReviewRequired && !editing && <label className="ff-review-ack">
      <input type="checkbox" checked={reviewConfirmed} onChange={event => { setReviewConfirmed(event.target.checked); setEditError(""); }} />
      <span><strong>Potwierdzam ręczną kontrolę formularza.</strong> Porównałem wszystkie strony, pola i opcje z oryginałem oraz poprawiłem zauważone błędy. Sam poprawny JSON nie potwierdza kompletności.</span>
    </label>}
    {extraction?.vision_incomplete && <div className="ff-warning" role="alert">
      Uwaga: obrazowo sprawdzono tylko {extraction.vision_pages||0} z {extraction.pages||"?"}
      {" "}stron PDF. Przejrzyj także pozostałe strony oryginału.</div>}
    {quality && !quality.ok && !editing && <div className="ff-warning" role="alert">
      <strong>Formularz może być niekompletny.</strong>{" "}
      {quality.source_blank_slots>0 && <>W źródle wykryto {quality.source_blank_slots} pustych miejsc,
      a formularz ma {quality.input_fields} pól. </>}
      {quality.possible_missing?.join(" ")} Sprawdź oryginał przed eksportem.
    </div>}
    {inventory?.source_map?.length>0 && !editing && <details className="ff-ocr-evidence">
      <summary>Skąd pochodzą wykryte pola? — zobacz dowody w dokumencie</summary>
      <p>Lista fragmentów oryginału użytych do rozpoznania pól. Jest to powiązanie tekstowe, nie dokładne podświetlenie na skanie.</p>
      <ul>{inventory.source_map.slice(0,120).map((item,index)=>
        <li key={index}><strong>{item.label}</strong>{" "}
          {item.source_page && <em>(strona {item.source_page})</em>} —{" "}
          {item.source_quote||"Do sprawdzenia na obrazie"}</li>
      )}</ul>
    </details>}
    {grounding?.requires_review>0 && !editing && <details className="ff-ocr-evidence">
      <summary>
        Sprawdź dokładniej {grounding.requires_review} {grounding.requires_review===1?"pytanie":"pytań"} — OCR nie znalazł jednoznacznego potwierdzenia
      </summary>
      <p>To nie musi oznaczać błędu: pole może być widoczne na obrazie, choć OCR go nie odczytał. Porównaj pytania z oryginalnym dokumentem.</p>
      <ul>{grounding.items.filter(x=>x.evidence!=="ocr_match").slice(0,25).map((item,index)=>
        <li key={index}>{item.label}</li>)}</ul>
    </details>}
    {warnings.length > 0 && <div className="ff-warning">
      <button className="ff-warning-trigger" type="button" onClick={()=>setShowWarnings(!showWarnings)}>
        Ograniczenia podglądu ({warnings.length}) {showWarnings?"−":"+"}
      </button>
      {showWarnings && <ul>{warnings.map((warning,i)=><li key={i}>{warning}</li>)}</ul>}
    </div>}
    {view==="original" && <DocumentView file={file} extraction={extraction}/>}
    {view==="json" && <div className="ff-json">
      <div className="ff-toolbar">
        <span>{hasEdits?"Konfiguracja JSON COI po korekcie":"Wygenerowana konfiguracja JSON COI"}</span>
        <div>
          <button type="button" className="ff-quiet" onClick={() => navigator.clipboard.writeText(JSON.stringify(workingForm,null,2))}>Kopiuj JSON</button>
          <button type="button" className="ff-primary" onClick={exportEditedCOI}>Pobierz JSON</button>
        </div>
      </div>
      <pre>{JSON.stringify(workingForm,null,2)}</pre>
    </div>}
    {view==="form" && <>
      <div className="ff-stepper" aria-label="Strony formularza">
        {pages.map((item,index)=><button type="button" key={item.id} className={index===pageIndex?"current":""}
          disabled={editing && item.isFinish}
          aria-current={index===pageIndex?"step":undefined} onClick={()=>setPageIndex(index)}>
          <span className="ff-step-num">{item.isFinish?"✓":index+1}</span>
          <span>{item.title}</span>
        </button>)}
      </div>
      <div className="ff-page">
        <div className="ff-page-heading">
          <span>STRONA {pageIndex+1} / {pages.length}</span>
          <h3>{page.title}</h3>
        </div>
        {editing && !page.isFinish ? <EditorPanel form={workingForm} pageIndex={pageIndex}
          onAction={changeDefinition} onUndo={undoDefinition}
          canUndo={history.current.length>0}/>
        : page.isFinish ? <div className="ff-finish">
          <div className="ff-finish-icon">✓</div>
          <h3>Podsumowanie wniosku</h3>
          <p>To wyłącznie interaktywny podgląd — nie wysyła danych do urzędu ani do OpenRouter. Aby pobrać pełny formularz COI, użyj przycisku „Pobierz JSON formularza COI”.</p>
          <dl>{fields.filter(item => answers[item.key] !== undefined).map(item=><div key={item.key}><dt>{item.field.title || item.key}</dt><dd><PrintValue value={answers[item.key]}/></dd></div>)}</dl>
          {summary.answered === 0 && <p>Nie wprowadzono jeszcze żadnych odpowiedzi.</p>}
        </div> : <div className="ff-rendered">
          <JsonForms schema={jsonSchema} uischema={page.uiSchema} data={answers}
            renderers={renderers} cells={vanillaCells} onChange={handleChange}
            validationMode={showValidation ? "ValidateAndShow" : "ValidateAndHide"}
            i18n={polishI18n}
            config={{restrict:true,showUnfocusedDescription:true}} />
          {page.blocks.map((message,index)=><div className={page.fieldCount===0?"ff-notice":"ff-note"} key={index}>{message}</div>)}
        </div>}
        {!editing && showValidation && (errors.length>0 || contentErrors.length>0) && <div role="alert" className="ff-validation-message">
          Formularz wymaga poprawy: {errors.length+contentErrors.length} problemów.
          Uzupełnij wymagane pola lub popraw ich format.
          {contentErrors.length>0 && <ul>{contentErrors.map(issue=>
            <li key={issue.key}><strong>{issue.label}:</strong> {issue.message}</li>)}</ul>}
        </div>}
        {!editing && <div className="ff-page-nav">
          <div className="ff-check-controls">
            <button type="button" className="ff-quiet" onClick={()=>setShowValidation(true)}>Sprawdź pola</button>
            <button type="button" className="ff-quiet" onClick={clearAnswers}>Wyczyść</button>
          </div>
          <div>
            <button type="button" className="ff-quiet" disabled={pageIndex===0} onClick={()=>setPageIndex(Math.max(0,pageIndex-1))}>Wstecz</button>
            {pageIndex < pages.length-1
              ? <button type="button" className="ff-primary" onClick={()=>setPageIndex(pageIndex+1)}>Dalej →</button>
              : <>
                  {summary.answered>0 && <button type="button" className="ff-quiet" onClick={exportAnswers}
                    title="Eksport wpisanych danych z podglądu, nie konfiguracji COI">Pobierz wypełnione odpowiedzi (podgląd)</button>}
                  <button type="button" className="ff-primary" onClick={exportEditedCOI}>Pobierz JSON formularza COI</button>
                </>}
          </div>
        </div>}
      </div>
    </>}
    <div className="ff-footnote">{wizardMode
      ? "To jest podgląd formularza, nie wysłanie wniosku do urzędu. Po sprawdzeniu pytań przejdź do kroku 3, żeby pobrać plik."
      : "Edycja formularza działa lokalnie w karcie przeglądarki i bez wywołania AI. Zapisanie poprawek sprawdza JSON na własnym VPS; aby je zachować, pobierz poprawiony plik. Nie jest to oficjalny importer COI."}</div>
  </div>;
}
const mount=document.getElementById("coi-preview-root");
const section=document.getElementById("coi-preview-section");
if(mount && section){
  const root=createRoot(mount);
  window.FormFlowPreview={
    open(form,options={}){
      if(!form || !Array.isArray(form.tabs))throw Error("Niepoprawna struktura formularza.");
      section.hidden=false;
      root.render(<PreviewApp key={Date.now()} form={form} file={options.file}
        extraction={options.extraction} quality={options.quality} grounding={options.grounding}
        inventory={options.inventory} validation={options.validation} source={options.source} wizardMode={options.wizardMode===true}/>);
      if(options.scrollIntoView!==false)
        section.scrollIntoView({behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});
    },
    close(){
      root.render(null);
      section.hidden=true;
    }
  };
}

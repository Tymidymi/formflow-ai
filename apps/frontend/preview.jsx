import React, { useEffect, useMemo, useState, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { JsonForms, withJsonFormsControlProps } from "@jsonforms/react";
import { vanillaCells, vanillaRenderers } from "@jsonforms/vanilla-renderers";
import { coiToJsonForms, calculateSummary, conditionIsVisible } from "./adapter.mjs";
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
function PreviewApp({form, file, extraction, validation, quality, source}) {
  const [pageIndex, setPageIndex] = useState(0);
  const [view, setView] = useState("form");
  const [answers, setAnswers] = useState({});
  const [errors, setErrors] = useState([]);
  const [showWarnings, setShowWarnings] = useState(false);
  const [showValidation, setShowValidation] = useState(false);
  const model = useMemo(() => coiToJsonForms(form), [form]);
  const {jsonSchema, pages, fields, warnings} = model;
  const page = pages[pageIndex] || pages[0];
  const summary = calculateSummary(model, answers);
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
    const currentAnswers = Object.fromEntries(Object.entries(answers).filter(([key]) => visible.has(key)));
    download("formflow-odpowiedzi.json", JSON.stringify({
      form: String(form.title || "COI"), previewOnly: true, answers: currentAnswers
    }, null, 2), "application/json;charset=utf-8");
  };
  const exportCOI = () => download("formflow-coi.json", JSON.stringify(form,null,2), "application/json;charset=utf-8");
  return <div className="ff-app">
    <div className="ff-top">
      <div className="ff-kicker">PODGLĄD WYGENEROWANEJ E-USŁUGI</div>
      <div className="ff-heading-row">
        <div><h2>{form.title || "Formularz COI"}</h2>
          <p>Sprawdź wygląd i zachowanie pytań przed eksportem konfiguracji.</p>
        </div>
        <div className="ff-stats">
          <div><strong>{summary.fields}</strong><span>pól</span></div>
          <div><strong>{summary.pages}</strong><span>stron</span></div>
          <div><strong>{summary.answered}</strong><span>wypełnionych</span></div>
        </div>
      </div>
    </div>
    <div className="ff-switch" role="tablist" aria-label="Widoki dokumentu">
      {[["form","Formularz cyfrowy"],["original","Oryginał"],["json","JSON COI"]].map(([id,name]) =>
        <button role="tab" type="button" key={id} aria-selected={view === id}
          className={view===id?"selected":""} onClick={()=>setView(id)}>{name}</button>)}
    </div>
    {validation && !validation.valid && <div className="ff-warning" role="alert">
      Walidator COI wskazuje problemy. Formularz ma charakter roboczy.</div>}
    {quality && !quality.ok && <div className="ff-warning" role="alert">
      Wynik modelu wymaga ręcznej weryfikacji — część pytań mogła zostać pominięta.</div>}
    {warnings.length > 0 && <div className="ff-warning">
      <button className="ff-warning-trigger" type="button" onClick={()=>setShowWarnings(!showWarnings)}>
        Ograniczenia podglądu ({warnings.length}) {showWarnings?"−":"+"}
      </button>
      {showWarnings && <ul>{warnings.map((warning,i)=><li key={i}>{warning}</li>)}</ul>}
    </div>}
    {view==="original" && <DocumentView file={file} extraction={extraction}/>}
    {view==="json" && <div className="ff-json">
      <div className="ff-toolbar">
        <span>Oryginalna konfiguracja JSON COI</span>
        <div>
          <button type="button" className="ff-quiet" onClick={() => navigator.clipboard.writeText(JSON.stringify(form,null,2))}>Kopiuj JSON</button>
          <button type="button" className="ff-primary" onClick={exportCOI}>Pobierz JSON</button>
        </div>
      </div>
      <pre>{JSON.stringify(form,null,2)}</pre>
    </div>}
    {view==="form" && <>
      <div className="ff-stepper" aria-label="Strony formularza">
        {pages.map((item,index)=><button type="button" key={item.id} className={index===pageIndex?"current":""}
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
        {page.isFinish ? <div className="ff-finish">
          <div className="ff-finish-icon">✓</div>
          <h3>Podsumowanie wniosku</h3>
          <p>To wyłącznie interaktywny podgląd — nie wysyła danych do urzędu ani do OpenRouter.</p>
          <dl>{fields.filter(item => answers[item.key] !== undefined).map(item=><div key={item.key}><dt>{item.field.title || item.key}</dt><dd><PrintValue value={answers[item.key]}/></dd></div>)}</dl>
          {summary.answered === 0 && <p>Nie wprowadzono jeszcze żadnych odpowiedzi.</p>}
        </div> : <div className="ff-rendered">
          <JsonForms schema={jsonSchema} uischema={page.uiSchema} data={answers}
            renderers={renderers} cells={vanillaCells} onChange={handleChange}
            validationMode={showValidation ? "ValidateAndShow" : "ValidateAndHide"}
            i18n={polishI18n}
            config={{restrict:true,showUnfocusedDescription:true}} />
          {page.blocks.map((message,index)=><p className="ff-note" key={index}>{message}</p>)}
        </div>}
        {showValidation && errors.length > 0 && <p role="alert" className="ff-validation-message">
          Formularz wymaga poprawy: {errors.length} problemów. Uzupełnij wymagane pola lub popraw ich format.
        </p>}
        <div className="ff-page-nav">
          <div className="ff-check-controls">
            <button type="button" className="ff-quiet" onClick={()=>setShowValidation(true)}>Sprawdź pola</button>
            <button type="button" className="ff-quiet" onClick={clearAnswers}>Wyczyść</button>
          </div>
          <div>
            <button type="button" className="ff-quiet" disabled={pageIndex===0} onClick={()=>setPageIndex(Math.max(0,pageIndex-1))}>Wstecz</button>
            {pageIndex < pages.length-1
              ? <button type="button" className="ff-primary" onClick={()=>setPageIndex(pageIndex+1)}>Dalej →</button>
              : <button type="button" className="ff-primary" onClick={exportAnswers}>Pobierz odpowiedzi</button>}
          </div>
        </div>
      </div>
    </>}
    <div className="ff-footnote">Podgląd z JSON Forms · Nie jest równoznaczny z importem do systemu COI ani elektronicznym złożeniem wniosku.</div>
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
        extraction={options.extraction} quality={options.quality} validation={options.validation}
        source={options.source}/>);
      section.scrollIntoView({behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});
    },
    close(){
      root.render(null);
      section.hidden=true;
    }
  };
}

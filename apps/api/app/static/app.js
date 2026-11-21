const input = document.querySelector('#file-input');
const zone = document.querySelector('#dropzone');
const result = document.querySelector('#result');
const limit = document.querySelector('#size-limit');

async function run(file) {
  if (!file) return;
  result.hidden = false;
  result.classList.remove('fail');
  result.replaceChildren();
  const heading = document.createElement('h3');
  heading.textContent = 'Sprawdzanie pliku…';
  result.appendChild(heading);
  const data = new FormData();
  data.append('file', file, file.name);
  try {
    const response = await fetch('/api/v1/forms/inspect', {method: 'POST', body: data});
    const json = await response.json();
    result.classList.toggle('fail', !response.ok);
    heading.textContent = response.ok ? '✓ Plik zaakceptowany' : 'Plik odrzucony';
    const details = document.createElement('pre');
    details.textContent = response.ok
      ? `Nazwa: ${json.document.filename}\nTyp: ${json.document.detected_mime}\nRozmiar: ${(json.document.size_bytes / 1024).toFixed(1)} KB\n\nWeryfikacja zakończona. Generowanie JSON COI jest planowane w kolejnym etapie.`
      : (json.detail || 'Nie udało się sprawdzić dokumentu.');
    result.appendChild(details);
  } catch (_) {
    result.classList.add('fail');
    heading.textContent = 'Błąd połączenia';
    const details = document.createElement('pre');
    details.textContent = 'Nie udało się skontaktować z API.';
    result.appendChild(details);
  }
}

zone.addEventListener('click', () => input.click());
zone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
input.addEventListener('change', () => run(input.files[0]));
zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragging'); });
zone.addEventListener('dragleave', () => zone.classList.remove('dragging'));
zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('dragging'); run(e.dataTransfer.files[0]); });
fetch('/api/v1/capabilities').then(r => r.json()).then(data => {
  limit.textContent = `${Math.round(data.max_upload_bytes / 1024 / 1024)} MB`;
}).catch(() => {});

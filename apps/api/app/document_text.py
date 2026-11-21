"""Lightweight extraction for dev; Docling worker will replace this later."""
from __future__ import annotations
import io
from .uploads import RejectedFile

def extract_document(content:bytes, extension:str)->tuple[str,list[tuple[str,bytes]]]:
    if extension==".pdf":
        from pypdf import PdfReader
        try:
            pdf=PdfReader(io.BytesIO(content),strict=False)
            if pdf.is_encrypted:
                raise RejectedFile("Zaszyfrowany PDF nie jest obsługiwany.",422)
            if len(pdf.pages)>25:
                raise RejectedFile("PDF przekracza 25 stron w trybie testowym.",413)
            text="\n\n".join((p.extract_text() or "") for p in pdf.pages)
        except RejectedFile: raise
        except Exception as exc:
            raise RejectedFile("Nie udało się wydobyć tekstu PDF.",422) from exc
        if len(text.strip())>=80:
            return text[:18000],[]
        # PDF scan: render at most two pages to images for vision Qwen.
        import pypdfium2 as pdfium
        try:
            doc=pdfium.PdfDocument(content)
            images=[]
            for i in range(min(2,len(doc))):
                page=doc[i]
                out=io.BytesIO()
                page.render(scale=1.2).to_pil().convert("RGB").save(out,format="JPEG",quality=72)
                if out.tell()>4*1024*1024:
                    raise RejectedFile("Skan PDF jest za duży.",413)
                images.append(("image/jpeg",out.getvalue()))
            doc.close()
            return "",images
        except RejectedFile: raise
        except Exception as exc:
            raise RejectedFile("Nie udało się odczytać skanu PDF.",422) from exc
    if extension in {".jpg",".jpeg",".png"}:
        return "",[("image/png" if extension==".png" else "image/jpeg",content)]
    if extension==".docx":
        from docx import Document
        try:
            document=Document(io.BytesIO(content))
            lines=[p.text for p in document.paragraphs if p.text.strip()]
            for table in document.tables:
                for row in table.rows:
                    lines.append(" | ".join(c.text.replace("\n"," / ") for c in row.cells))
            return "\n".join(lines)[:18000],[]
        except Exception as exc:
            raise RejectedFile("Nie można odczytać pliku DOCX.",422) from exc
    if extension==".xlsx":
        from openpyxl import load_workbook
        try:
            workbook=load_workbook(io.BytesIO(content),read_only=True,data_only=True)
            lines=[]
            for sheet in workbook.worksheets[:3]:
                lines.append("Arkusz: "+sheet.title)
                for row in sheet.iter_rows(max_row=150,max_col=20,values_only=True):
                    vals=[str(v) for v in row if v is not None]
                    if vals:lines.append(" | ".join(vals))
            workbook.close()
            return "\n".join(lines)[:18000],[]
        except Exception as exc:
            raise RejectedFile("Nie można odczytać pliku XLSX.",422) from exc
    if extension==".ods":
        # Lightweight local OpenDocument reader until Docling is deployed.
        from zipfile import ZipFile, BadZipFile
        from xml.etree import ElementTree as ET
        from .uploads import ZIP_MAX_ENTRIES, ZIP_MAX_EXPANDED
        try:
            with ZipFile(io.BytesIO(content)) as archive:
                infos=archive.infolist()
                if len(infos)>ZIP_MAX_ENTRIES or sum(i.file_size for i in infos)>ZIP_MAX_EXPANDED:
                    raise RejectedFile("ODS przekracza limit bezpieczeństwa.",413)
                content_info=archive.getinfo("content.xml")
                if content_info.file_size>3*1024*1024:
                    raise RejectedFile("Zbyt duży XML arkusza ODS.",413)
                xml=archive.read("content.xml")
            if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                raise RejectedFile("Niebezpieczny XML w ODS.",422)
            root=ET.fromstring(xml)
            table_ns="{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
            text_ns="{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
            lines=[]
            for table in root.iter(table_ns+"table"):
                lines.append("Arkusz: "+table.attrib.get(table_ns+"name",""))
                count=0
                for row in table.iter(table_ns+"table-row"):
                    if count>=180:break
                    count+=1;values=[]
                    for cell in row:
                        if cell.tag not in (table_ns+"table-cell",table_ns+"covered-table-cell"):continue
                        value=" ".join((p.text or "") for p in cell.iter(text_ns+"p")).strip()
                        if not value:value=" ".join(t.strip() for t in cell.itertext() if t.strip())
                        repeat=min(int(cell.attrib.get(table_ns+"number-columns-repeated","1")),20)
                        if value:
                            values.extend([value[:300]]*repeat)
                        if len(values)>=25:break
                    if values:lines.append(" | ".join(values[:25]))
                if len(lines)>500:break
            text="\n".join(lines)[:18000]
            if not text.strip():
                raise RejectedFile("ODS nie zawiera czytelnej treści.",422)
            return text,[]
        except RejectedFile:raise
        except (BadZipFile,KeyError,ValueError,ET.ParseError,OverflowError,OSError) as exc:
            raise RejectedFile("Nie można odczytać pliku ODS.",422) from exc
    raise RejectedFile("Parser starego DOC nie jest jeszcze wdrożony.",501)

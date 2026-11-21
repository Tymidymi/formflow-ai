"""Run inside worker image: python -m unittest discover -s /tests"""
import io
import unittest
from PIL import Image,ImageDraw,ImageFont
from pypdf import PdfWriter
from engine import pdf_extract,image_extract,normalize_text,PdfExtractionError

class EngineTest(unittest.TestCase):
    def test_normalize_checkbox(self):
        self.assertEqual(normalize_text("Wybór \uf0f0 Tak"),"Wybór ☐ Tak")

    def test_png_ocr(self):
        img=Image.new("RGB",(1600,800),"white")
        pen=ImageDraw.Draw(img)
        font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",44)
        pen.text((80,130),"WNIOSEK PESEL NAZWISKO",font=font,fill="black")
        out=io.BytesIO();img.save(out,"PNG")
        result=image_extract(out.getvalue(),".png")
        self.assertIn("PESEL",result["text"])
        self.assertEqual(result["ocr_pages"],1)

    def test_scanned_pdf_ocr(self):
        img=Image.new("RGB",(1600,900),"white")
        pen=ImageDraw.Draw(img)
        font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",44)
        pen.text((100,100),"PESEL NAZWISKO TELEFON",font=font,fill="black")
        out=io.BytesIO();img.save(out,"PDF")
        result=pdf_extract(out.getvalue(),include_previews=True)
        self.assertEqual(result["ocr_pages"],1)
        self.assertIn("PESEL",result["text"])
        self.assertEqual(len(result["preview_images"]),1)

    def test_pdf_page_limit(self):
        pdf=PdfWriter()
        for _ in range(26):pdf.add_blank_page(width=250,height=300)
        out=io.BytesIO();pdf.write(out)
        with self.assertRaises(PdfExtractionError) as context:
            pdf_extract(out.getvalue())
        self.assertEqual(context.exception.code,413)

    def test_pdf_corruption(self):
        with self.assertRaises(PdfExtractionError):
            pdf_extract(b"this is not a pdf")

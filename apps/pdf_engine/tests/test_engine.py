"""Run inside worker image: python -m unittest discover -s /tests"""
import io
import unittest
from PIL import Image,ImageDraw,ImageFont
from pypdf import PdfWriter
from engine import pdf_extract,image_extract,normalize_text,PdfExtractionError,detect_stitched_image_parts

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

    def test_tall_jpeg_separates_main_application_and_legal_page(self):
        img=Image.new("RGB",(724,2048),"white")
        pen=ImageDraw.Draw(img)
        font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",28)
        pen.text((60,145),"WNIOSEK PESEL",font=font,fill="black")
        pen.text((60,420),"DATA TELEFON",font=font,fill="black")
        pen.text((60,1110),"KLAUZULA INFORMACYJNA",font=font,fill="black")
        pen.text((60,1240),"RODO DANE OSOBOWE",font=font,fill="black")
        parts=detect_stitched_image_parts(img)
        self.assertEqual(len(parts),2)
        self.assertLess(parts[0].height,1300)
        out=io.BytesIO();img.save(out,"JPEG",quality=88)
        result=image_extract(out.getvalue(),".jpeg")
        self.assertEqual(result["page_sources"][0]["regions"],2)
        self.assertIn("PESEL",result["text"])
        self.assertIn("RODO",result["text"])
        self.assertLess(result["text"].index("PESEL"),result["text"].index("RODO"))


    def test_four_visual_previews_are_complete(self):
        pages=[]
        for page in range(4):
            img=Image.new("RGB",(900,700),"white")
            ImageDraw.Draw(img).text((80,120),f"PAGE {page+1} PESEL",fill="black")
            pages.append(img)
        out=io.BytesIO()
        pages[0].save(out,"PDF",save_all=True,append_images=pages[1:])
        res=pdf_extract(out.getvalue(),include_previews=True)
        self.assertEqual(res["page_count"],4)
        self.assertEqual([p["page"] for p in res["preview_images"]],[1,2,3,4])
        self.assertEqual(res["preview_page_numbers"],[1,2,3,4])
        self.assertFalse(res["vision_incomplete"])
        no_images=pdf_extract(out.getvalue(),include_previews=False)
        self.assertEqual(no_images["preview_images"],[])
        self.assertFalse(no_images["vision_incomplete"])

    def test_pdf_corruption(self):
        with self.assertRaises(PdfExtractionError):
            pdf_extract(b"this is not a pdf")

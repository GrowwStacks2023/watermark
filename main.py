from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import base64
import io

from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ✅ Input schema (ALL dynamic)
class WatermarkRequest(BaseModel):
    pdfBase64: str
    text: str = Field(..., example="CONFIDENTIAL")
    x: float = Field(..., example=150)
    y: float = Field(..., example=400)
    fontSize: int = Field(..., example=30, gt=0)
    opacity: float = Field(..., example=0.4, ge=0, le=1)


@app.post("/watermark-pdf")
async def watermark_pdf(payload: WatermarkRequest):
    try:
        # Decode base64 PDF
        try:
            pdf_bytes = base64.b64decode(payload.pdfBase64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 PDF")

        pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
        pdf_writer = PdfWriter()

        # Create watermark PDF
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)

        can.setFillColorRGB(0.6, 0.6, 0.6, alpha=payload.opacity)
        can.setFont("Helvetica-Bold", payload.fontSize)
        can.drawString(payload.x, payload.y, payload.text)

        can.save()
        packet.seek(0)

        watermark_reader = PdfReader(packet)
        watermark_page = watermark_reader.pages[0]

        # Apply watermark to ALL pages
        for page in pdf_reader.pages:
            page.merge_page(watermark_page)
            pdf_writer.add_page(page)

        # Write output
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)

        result_base64 = base64.b64encode(output.read()).decode("utf-8")

        return {
            "success": True,
            "message": "Watermark added successfully",
            "pdfBase64": result_base64
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

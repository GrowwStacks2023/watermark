from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import io
import base64
import requests

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


# =========================
# Request Schema
# =========================
class WatermarkRequest(BaseModel):
    pdfUrl: str = Field(..., example="https://drive.google.com/uc?id=FILE_ID&export=download")
    text: str = Field(..., example="CONFIDENTIAL")
    x: float = Field(..., example=150)
    y: float = Field(..., example=400)
    fontSize: int = Field(..., example=30, gt=0)
    opacity: float = Field(..., example=0.4, ge=0, le=1)


# =========================
# Helpers
# =========================
def extract_drive_file_id(url: str) -> str:
    if "id=" in url:
        return url.split("id=")[1].split("&")[0]
    if "/d/" in url:
        return url.split("/d/")[1].split("/")[0]
    raise Exception("Invalid Google Drive URL")


def download_google_drive_pdf(file_id: str) -> bytes:
    session = requests.Session()
    base_url = "https://drive.google.com/uc?export=download"

    response = session.get(base_url, params={"id": file_id}, stream=True)

    # Handle virus scan confirmation
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            response = session.get(
                base_url,
                params={"id": file_id, "confirm": value},
                stream=True
            )
            break

    content_type = response.headers.get("Content-Type", "")

    if "pdf" not in content_type.lower():
        raise Exception("Downloaded file is not a PDF")

    return response.content


# =========================
# API Endpoint
# =========================
@app.post("/watermark-pdf-from-url")
async def watermark_pdf_from_url(payload: WatermarkRequest):
    try:
        # Extract file ID
        file_id = extract_drive_file_id(payload.pdfUrl)

        # Download PDF
        pdf_bytes = download_google_drive_pdf(file_id)

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

        watermark_page = PdfReader(packet).pages[0]

        # Apply watermark to all pages
        for page in pdf_reader.pages:
            page.merge_page(watermark_page)
            pdf_writer.add_page(page)

        # Write output
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)

        return {
            "success": True,
            "message": "Watermark added successfully",
            "pdfBase64": base64.b64encode(output.read()).decode("utf-8")
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

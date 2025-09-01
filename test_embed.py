import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import io

def embed_qr_to_pdf(pdf_in, qr_data, pdf_out):
    # Generate QR ke memory
    qr = qrcode.make(qr_data)
    qr_io = io.BytesIO()
    qr.save(qr_io, format="PNG")
    qr_io.seek(0)

    # Buat PDF baru dengan QR
    c = canvas.Canvas(pdf_out, pagesize=letter)

    # Tempel QR
    c.drawImage(ImageReader(qr_io), 450, 50, width=100, height=100)

    # Tambah teks buat bukti
    c.setFont("Helvetica", 12)
    c.drawString(50, 750, "Dokumen ini sudah ditandatangani ✅")

    c.showPage()
    c.save()
    print(f"QR berhasil ditempel di {pdf_out}")

# --- TEST LANGSUNG ---
if __name__ == "__main__":
    input_pdf = "contoh.pdf"         # bikin PDF kosong dulu biar ada
    output_pdf = "signed_contoh.pdf"
    qr_text = "Test QR data 12345"

    embed_qr_to_pdf(input_pdf, qr_text, output_pdf)

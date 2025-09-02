from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os, qrcode, hashlib, base64, datetime, sqlite3, json
from ecdsa import SigningKey, VerifyingKey, NIST256p
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io

app = Flask(__name__)

UPLOAD_FOLDER = os.path.abspath("uploads")
QR_FOLDER = "static/qr"
KEY_FOLDER = "keys"
HISTORY_FOLDER = "history"
DB_NAME = "riwayat.db"

for folder in [UPLOAD_FOLDER, QR_FOLDER, KEY_FOLDER, HISTORY_FOLDER]:
    os.makedirs(folder, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS riwayat_surat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT,
            filename TEXT,
            timestamp TEXT,
            status TEXT,
            qr_file TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def read_pdf_text(filepath):
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text()
        return text
    except:
        return ""

def embed_qr_to_pdf(input_pdf, qr_data, output_pdf):
    qr_img = qrcode.make(qr_data)
    qr_io = io.BytesIO()
    qr_img.save(qr_io, format="PNG")
    qr_io.seek(0)
    qr_image = ImageReader(qr_io)

    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    for i, page in enumerate(reader.pages):
        packet = io.BytesIO()

        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        c = canvas.Canvas(packet, pagesize=(width, height))

        if i == len(reader.pages) - 1:
            c.drawImage(qr_image, width - 170, 50, width=120, height=120)

        c.save()
        packet.seek(0)
        overlay_pdf = PdfReader(packet)
        overlay_page = overlay_pdf.pages[0]
        page.merge_page(overlay_page)
        writer.add_page(page)

    with open(output_pdf, "wb") as f:
        writer.write(f)

def sign_document(file, filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    text = read_pdf_text(filepath)
    hashed = hashlib.sha256(text.encode()).hexdigest()
    with open(os.path.join(KEY_FOLDER, "private.pem"), "r") as f:
        sk = SigningKey.from_pem(f.read())
    signature = sk.sign(hashed.encode())
    encoded_sig = base64.b64encode(signature).decode()
    data = hashed + "|" + encoded_sig
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    qr_file = f"{timestamp}_{filename.replace('.pdf','')}.png"
    qr_path = os.path.join(QR_FOLDER, qr_file)
    img = qrcode.make(data)
    img.save(qr_path)
    with open(os.path.join(HISTORY_FOLDER, f"{timestamp}_sign.txt"), "w") as log:
        log.write(f"{filename}\n{hashed}\n{encoded_sig}\n{qr_file}")
    return qr_file, timestamp

def verify_document(file, filename):
    filepath = os.path.join(UPLOAD_FOLDER, "verify_" + filename)
    file.save(filepath)
    text = read_pdf_text(filepath)
    hashed = hashlib.sha256(text.encode()).hexdigest()
    logs = os.listdir(HISTORY_FOLDER)
    logs.sort(reverse=True)
    for log_name in logs:
        if "sign.txt" in log_name:
            with open(os.path.join(HISTORY_FOLDER, log_name), "r") as log:
                lines = log.readlines()
                if len(lines) >= 3:
                    _, stored_hash, encoded_sig, _ = lines
                    stored_hash = stored_hash.strip()
                    signature = base64.b64decode(encoded_sig.strip())
                    with open(os.path.join(KEY_FOLDER, "public.pem"), "r") as f:
                        vk = VerifyingKey.from_pem(f.read())
                    try:
                        if hashed == stored_hash and vk.verify(signature, hashed.encode()):
                            return True
                    except:
                        continue
    return False

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/sign", methods=["GET", "POST"])
def sign():
    if request.method == "POST":
        nama = request.form.get("nama")
        pdf = request.files["pdf"]
        filename = pdf.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        pdf.save(filepath)

        print(">>> [DEBUG] File upload:", filepath)

        text = read_pdf_text(filepath)
        hashed = hashlib.sha256(text.encode()).hexdigest()

        with open(os.path.join(KEY_FOLDER, "private.pem"), "r") as priv:
            sk = SigningKey.from_pem(priv.read())

        signature = sk.sign(hashed.encode())
        encoded_sig = base64.b64encode(signature).decode()

        data = {
            "nama": nama,
            "hash": hashed,
            "signature": encoded_sig
        }
        json_str = json.dumps(data)

        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        base_url = f"https://esignmax-g63dcmo03-nisas-projects-d87116d1.vercel.app/verify?doc_id={doc_id}"
        qr_data = base_url + filename
        qr_file = f"{timestamp}_{filename.replace('.pdf','')}.png"
        qr_path = os.path.join(QR_FOLDER, qr_file)
        qrcode.make(json_str).save(qr_path)

        print(">>> [DEBUG] QR saved:", qr_path)

         # 🔹 Simpan data ke database
        status = "Valid"
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO riwayat_surat (nama, filename, timestamp, status) VALUES (?, ?, ?, ?)",
          (nama, filename, timestamp, status))
        conn.commit()

        # ambil ID terakhir
        doc_id = c.lastrowid  

        # bikin URL untuk QR
        base_url = f"https://esignmax-g63dcmo03-nisas-projects-d87116d1.vercel.app/verify?doc_id={doc_id}"
        conn.close()

        # 🔹 Tempel QR ke PDF
        signed_path = os.path.join(UPLOAD_FOLDER, "signed_" + filename)
        embed_qr_to_pdf(filepath, qr_data, signed_path)
        print(">>> [DEBUG] Selesai embed QR ke PDF")

        return render_template("signed.html", message=f"✅ Dokumen sudah ditandatangani: signed_{filename}", nama=nama)
    return render_template("sign.html")

@app.route("/verify", methods=["GET", "POST"])
def verify():
    result = None
    doc_id = request.args.get("doc_id")
    if doc_id:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT nama, filename, timestamp, status FROM riwayat_surat WHERE id=?", (doc_id,))
        row = c.fetchone()
        conn.close()

        if row:
            entry = {
                "nama": row[0],
            "filename": row[1],
            "timestamp": row[2],
            "status": row[3]
        }
        return render_template("verify.html", entry=entry)
    else:
        return "Dokumen tidak ditemukan", 404
    
            nama, filename, timestamp, status = row
            if status == "Valid":
                result = f"✅ Dokumen ASLI dan VALID.\nDitandatangani oleh: {nama}"
            else:
                result = f"❌ Dokumen ditemukan tapi statusnya {status}"
        else:
            result = "❌ Dokumen tidak ditemukan di database."

        return render_template("verify.html", result=result)

    # 🔹 Kalau user upload file manual (POST)
    if request.method == "POST":
        pdf = request.files["pdf"]
        filename = pdf.filename
        filepath = os.path.join(UPLOAD_FOLDER, "verify_" + filename)
        pdf.save(filepath)

        text = read_pdf_text(filepath)
        hashed = hashlib.sha256(text.encode()).hexdigest()

        found = False
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT nama, filename, status FROM riwayat_surat")
        rows = c.fetchall()
        conn.close()

        for row in rows:
            nama, fname, status = row
            if fname == "signed_" + filename:
                found = True
                if status == "Valid":
                    result = f"✅ Dokumen ASLI dan VALID.\nDitandatangani oleh: {nama}"
                else:
                    result = "❌ Dokumen ditemukan tapi status tidak valid."
                break

        if not found:
            result = "❌ Dokumen TIDAK VALID atau belum terdaftar."

    return render_template("verify.html", result=result)

@app.route("/history")
def history():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT nama, filename, timestamp, status FROM riwayat_surat ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()

    entries = []
    for row in rows:
        entries.append({
            "nama": row[0],
            "filename": row[1],
            "timestamp": row[2],
            "status": row[3]
        })
    return render_template("history.html", history=entries)

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    filename = filename.strip() #hapus spasi
    full_path = os.path.join(UPLOAD_FOLDER, filename)
    print("DEBUG buka file:", full_path)  # cek path
    if not os.path.exists(full_path):
        # coba-cari nama file yang mirip
        for f_upload in os.listdir(UPLOAD_FOLDER):
            if f_upload.lower() == filename.lower():
                full_path = os.path.join(UPLOAD_FOLDER, f_upload)
                break
        return f"⚠️ File tidak ditemukan di server: {full_path}", 404
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    app.run(debug=True)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

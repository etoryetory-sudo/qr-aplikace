import sqlite3
import secrets
from pathlib import Path
from flask import Flask, request, render_template, send_file, abort
import qrcode

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.db"
UPLOADS_DIR = BASE_DIR / "uploads"
QR_DIR = BASE_DIR / "qr_codes"

UPLOADS_DIR.mkdir(exist_ok=True)
QR_DIR.mkdir(exist_ok=True)

app = Flask(__name__)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_name TEXT NOT NULL,
        stored_name TEXT NOT NULL,
        token TEXT NOT NULL UNIQUE,
        downloads INTEGER DEFAULT 0,
        max_downloads INTEGER DEFAULT 3,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    conn = get_db()
    items = conn.execute("SELECT * FROM files ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("home.html", items=items)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        uploaded = request.files.get("file")

        if not uploaded or uploaded.filename == "":
            return "Nevybral jsi soubor.", 400

        token = secrets.token_urlsafe(16)
        original_name = uploaded.filename
        ext = Path(original_name).suffix
        stored_name = f"{token}{ext}"

        file_path = UPLOADS_DIR / stored_name
        uploaded.save(file_path)

        conn = get_db()
        conn.execute(
            "INSERT INTO files (original_name, stored_name, token) VALUES (?, ?, ?)",
            (original_name, stored_name, token),
        )
        conn.commit()
        conn.close()

        public_url = f"https://qr-aplikace.onrender.com/q/{token}"

        qr_path = QR_DIR / f"{token}.png"
        img = qrcode.make(public_url)
        img.save(qr_path)

        return render_template(
            "created.html",
            public_url=public_url,
            qr_image=f"/qr-image/{token}.png",
        )

    return render_template("upload.html")


@app.route("/q/<token>")
def file_page(token):
    conn = get_db()
    item = conn.execute("SELECT * FROM files WHERE token = ?", (token,)).fetchone()
    conn.close()

    if not item:
        abort(404)

    return render_template("download.html", item=item)


@app.route("/download/<token>")
@app.route("/download/<token>")
def download(token):
    conn = get_db()
    item = conn.execute("SELECT * FROM files WHERE token = ?", (token,)).fetchone()

    if not item:
        conn.close()
        abort(404)

    if item["downloads"] >= item["max_downloads"]:
        conn.close()
        return "Limit stažení byl dosažen."

    conn.execute(
        "UPDATE files SET downloads = downloads + 1 WHERE token = ?",
        (token,)
    )
    conn.commit()
    conn.close()

    file_path = UPLOADS_DIR / item["stored_name"]

    return send_file(
        file_path,
        as_attachment=True,
        download_name=item["original_name"]
    )

@app.route("/qr-image/<filename>")
def qr_image(filename):
    path = QR_DIR / filename
    if not path.exists():
        abort(404)
    return send_file(path)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)

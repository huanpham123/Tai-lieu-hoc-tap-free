# api/index.py
import os
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory, abort, jsonify
)
from werkzeug.utils import secure_filename

# ---------- Config ----------
current_dir = Path(__file__).resolve().parent
templates_path = current_dir.parent / "templates"
UPLOAD_FOLDER = current_dir.parent / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = None  # None = allow all types. You can restrict if needed.

# Secret key: use env if present (Vercel), fallback to fixed for demo
SECRET_KEY = os.environ.get("APP_SECRET_KEY") or "your_fixed_secret_key_for_vercel_deployment_2024"

app = Flask(__name__, template_folder=str(templates_path))
app.secret_key = SECRET_KEY
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200MB limit

# ---------- Sample subjects ----------
SUBJECTS = ['Toán', 'Lý', 'Hóa', 'Sinh', 'Tin', 'Sử', 'Văn', 'Tiếng Anh', 'Chung']

# ---------- Memory storage (primary) ----------
memory_storage = {"public": [], "private": []}
SAMPLE_DATA = {
    "public": [
        {
            "id": "sample1",
            "title": "Toán 12 - Bài giảng hay",
            "url": "https://example.com/toan12",
            "category": "Toán",
            "created_at": "01/01/2024 10:00"
        },
        {
            "id": "sample2",
            "title": "Vật lý cơ bản",
            "url": "https://example.com/vatly",
            "category": "Lý",
            "created_at": "01/01/2024 10:00"
        }
    ],
    "private": []
}


# ---------- Helpers ----------
def normalize_data(raw):
    if raw is None:
        return {"public": [], "private": []}
    if isinstance(raw, dict) and 'record' in raw:
        raw = raw['record']
    if isinstance(raw, list):
        return {"public": raw, "private": []}
    if isinstance(raw, dict):
        public = raw.get('public', []) or []
        private = raw.get('private', []) or []
        for doc in public + private:
            if 'category' not in doc:
                doc['category'] = 'Chung'
        return {"public": public, "private": private}
    return {"public": [], "private": []}


def use_memory_storage_read():
    global memory_storage
    if not memory_storage["public"] and not memory_storage["private"]:
        memory_storage = normalize_data(SAMPLE_DATA.copy())
    return memory_storage


def use_memory_storage_write(data):
    global memory_storage
    memory_storage = normalize_data(data)
    return True


def generate_secure_key():
    return "kn1-" + secrets.token_hex(8)


def allowed_file(filename):
    if not filename:
        return False
    if ALLOWED_EXTENSIONS is None:
        return True
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext in ALLOWED_EXTENSIONS


def find_and_remove_doc(data, doc_id):
    """Remove document with id from data dict. Returns removed doc or None."""
    for bucket in ('public', 'private'):
        lst = data.get(bucket, [])
        for i, doc in enumerate(lst):
            if doc.get('id') == doc_id:
                return lst.pop(i)
    return None


def save_uploaded_file(file_storage):
    """Save uploaded file with a secure unique name; return relative URL and filename."""
    orig_name = secure_filename(file_storage.filename)
    if not orig_name:
        raise ValueError("Tên file không hợp lệ")
    unique_prefix = secrets.token_hex(6)
    filename = f"{unique_prefix}-{orig_name}"
    filepath = UPLOAD_FOLDER / filename
    file_storage.save(str(filepath))
    # Build url relative to app root (served by /uploads/<filename>)
    return url_for('uploaded_file', filename=filename, _external=False), filename


# ---------- High-level load/save ----------
def load_urls():
    return use_memory_storage_read()


def save_urls(data):
    return use_memory_storage_write(data)


# ---------- Routes ----------
@app.route("/")
def index():
    data = load_urls()
    all_public = data.get('public', [])
    all_private = data.get('private', [])
    return render_template(
        "index.html",
        public_docs=all_public,
        private_docs=all_private,
        session=session,
        subjects=SUBJECTS
    )


@app.route("/subject/<name>")
def subject(name):
    name = name or 'Chung'
    data = load_urls()
    public = [d for d in data.get('public', []) if d.get('category', 'Chung') == name]
    private = [d for d in data.get('private', []) if d.get('category', 'Chung') == name]
    return render_template(
        "index.html",
        public_docs=public,
        private_docs=private,
        session=session,
        subjects=SUBJECTS,
        current_subject=name
    )


@app.route("/login", methods=["POST"])
def login():
    password = request.form.get("password")
    if password == "huankk123@@":
        session['logged_in'] = True
        session['admin'] = True
        flash("Đăng nhập thành công!", "success")
        return redirect(url_for("admin"))
    else:
        flash("Mật khẩu không đúng!", "error")
        return redirect(url_for("index"))


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("logged_in"):
        flash("Vui lòng đăng nhập để truy cập trang quản trị", "error")
        return redirect(url_for("index"))

    data = load_urls()

    if request.method == "POST":
        # Add new doc OR upload file
        title = (request.form.get("title") or "").strip()
        doc_type = request.form.get("type", "public")
        category = request.form.get("category") or "Chung"
        if category not in SUBJECTS:
            category = "Chung"

        url_field = (request.form.get("url") or "").strip()
        file_field = request.files.get("file")

        if not title:
            flash("Vui lòng nhập tiêu đề!", "error")
        else:
            doc = {
                "id": secrets.token_hex(8),
                "title": title,
                "category": category,
                "created_at": datetime.now().strftime("%d/%m/%Y %H:%M")
            }

            if file_field and file_field.filename:
                if not allowed_file(file_field.filename):
                    flash("Loại file không được phép", "error")
                    return redirect(url_for("admin"))
                try:
                    file_url, filename = save_uploaded_file(file_field)
                    doc["url"] = file_url
                    doc["_filename"] = filename  # for internal management (delete)
                except Exception as e:
                    flash(f"Lỗi lưu file: {e}", "error")
                    return redirect(url_for("admin"))
            elif url_field:
                doc["url"] = url_field
            else:
                flash("Vui lòng cung cấp URL hoặc tải lên file", "error")
                return redirect(url_for("admin"))

            if doc_type == "private":
                doc['key'] = generate_secure_key()
                data.setdefault("private", []).append(doc)
            else:
                data.setdefault("public", []).append(doc)

            if save_urls(data):
                flash("Thêm tài liệu thành công!", "success")
            else:
                flash("Lỗi khi lưu dữ liệu!", "error")

            # reload data for fresh view
            data = load_urls()

    return render_template(
        "admin.html",
        public_docs=data.get('public', []),
        private_docs=data.get('private', []),
        subjects=SUBJECTS
    )


@app.route("/delete/<doc_id>", methods=["POST"])
def delete_doc(doc_id):
    if not session.get('logged_in'):
        flash("Không có quyền", "error")
        return redirect(url_for("index"))

    data = load_urls()
    removed = find_and_remove_doc(data, doc_id)
    if removed:
        # if the doc refers to uploaded file, try remove it from disk
        filename = removed.get("_filename")
        if filename:
            fp = UPLOAD_FOLDER / filename
            try:
                if fp.exists():
                    fp.unlink()
            except Exception as e:
                # log error but continue
                app.logger.warning(f"Không xóa được file {fp}: {e}")
        ok = save_urls(data)
        if ok:
            flash("Xóa tài liệu thành công", "success")
        else:
            flash("Xóa trên bộ nhớ không thành công (lỗi lưu)", "error")
    else:
        flash("Không tìm thấy tài liệu", "error")
    return redirect(url_for("admin"))


@app.route("/access_private/<doc_id>", methods=["POST"])
def access_private(doc_id):
    data = load_urls()
    entered_key = (request.form.get("key") or "").strip()
    for doc in data.get("private", []):
        if doc.get("id") == doc_id:
            if doc.get("key") == entered_key:
                target = doc.get("url") or url_for("index")
                return redirect(target)
            else:
                flash("Key không đúng!", "error")
                return redirect(url_for("index"))
    flash("Tài liệu không tồn tại!", "error")
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Đã đăng xuất thành công!", "success")
    return redirect(url_for("index"))


@app.route("/reset", methods=["POST"])
def reset_data():
    if not session.get("logged_in"):
        flash("Không có quyền", "error")
        return redirect(url_for("index"))

    global memory_storage
    memory_storage = normalize_data(SAMPLE_DATA.copy())
    # also clear uploads folder
    try:
        for f in UPLOAD_FOLDER.iterdir():
            if f.is_file():
                f.unlink()
    except Exception:
        pass
    flash("Đã reset dữ liệu về mẫu!", "success")
    return redirect(url_for("admin"))


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # Serve uploaded files (download/view)
    safe = secure_filename(filename)
    # Prevent path traversal
    if safe != filename:
        abort(404)
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)


@app.route("/health")
def health_check():
    return jsonify(status="healthy", message="Flask app is running")


# Vercel expects "application" variable
application = app

if __name__ == "__main__":
    # Initialize sample data
    use_memory_storage_write(SAMPLE_DATA.copy())
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

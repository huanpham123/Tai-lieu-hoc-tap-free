# api/index.py
"""
Flask app (Neon connection string embedded).
ĐÃ CHÈN trực tiếp connection string bạn cung cấp.
=> KEEP THIS FILE PRIVATE.
"""

import os
import secrets
from datetime import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

# ----------------- CONFIG (ĐÃ CHÈN) -----------------
# <--- Đây là chỗ bạn paste connection string Neon thật — đã dùng chuỗi bạn gửi. --->
DATABASE_URL = "postgresql://neondb_owner:npg_VMLD6vcurPm2@ep-crimson-fog-ad12kor2-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Session secret (thay nếu muốn)
SECRET_KEY = "replace_this_with_a_long_random_string_32+_chars"

# Admin password (thay nếu muốn)
ADMIN_PASSWORD = "huankk123@@"
# ----------------------------------------------------------

def ensure_postgres_ssl(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme
    if scheme == "postgres":
        scheme = "postgresql"
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if 'sslmode' not in q:
        q['sslmode'] = 'require'
    new_query = urlencode(q)
    new_parsed = parsed._replace(scheme=scheme, query=new_query)
    return urlunparse(new_parsed)

# Normalize (function will leave query unchanged if sslmode already present)
DATABASE_URL = ensure_postgres_ssl(DATABASE_URL)

# Flask init
current_dir = os.path.dirname(os.path.abspath(__file__))
templates_path = os.path.join(current_dir, '..', 'templates')

app = Flask(__name__, template_folder=templates_path)
app.secret_key = SECRET_KEY

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}

db = SQLAlchemy(app)

# ----------------- Model -----------------
class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.String(64), primary_key=True, nullable=False)
    title = db.Column(db.String(512), nullable=False)
    url = db.Column(db.String(2048), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(128), nullable=False, default="Chung")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    doc_type = db.Column(db.String(16), nullable=False, default="public")
    key = db.Column(db.String(64), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "description": self.description or "",
            "category": self.category or "Chung",
            "created_at": self.created_at.strftime("%d/%m/%Y %H:%M"),
            "doc_type": self.doc_type,
            "key": self.key
        }

# ----------------- Sample data -----------------
SAMPLE_DATA = [
    {
        "id": "sample1",
        "title": "Toán 12 - Bài giảng đại số",
        "url": "https://example.com/toan12",
        "category": "Toán",
        "description": "Bài giảng đại số nâng cao lớp 12",
        "doc_type": "public",
        "created_at": datetime.strptime("01/01/2024 10:00", "%d/%m/%Y %H:%M")
    },
    {
        "id": "sample2",
        "title": "Vật lý cơ bản - Chương 1",
        "url": "https://example.com/vatly",
        "category": "Lý",
        "description": "Kiến thức vật lý cơ bản chương 1",
        "doc_type": "public",
        "created_at": datetime.strptime("01/01/2024 10:00", "%d/%m/%Y %H:%M")
    }
]

# ----------------- Helpers -----------------
SUBJECTS = ['Toán', 'Lý', 'Hóa', 'Sinh', 'Tin', 'Sử', 'Văn', 'Tiếng Anh', 'Chung']

def generate_secure_key() -> str:
    return "kn1-" + secrets.token_hex(8)

def generate_doc_id() -> str:
    return secrets.token_hex(8)

def validate_url(url: str) -> bool:
    if not url:
        return False
    url = url.strip()
    return url.startswith("http://") or url.startswith("https://")

def seed_sample_data_if_empty():
    try:
        if Document.query.count() == 0:
            for item in SAMPLE_DATA:
                doc = Document(
                    id=item["id"],
                    title=item["title"],
                    url=item["url"],
                    description=item.get("description", ""),
                    category=item.get("category", "Chung"),
                    doc_type=item.get("doc_type", "public"),
                    created_at=item.get("created_at", datetime.utcnow()),
                    key=None
                )
                db.session.add(doc)
            db.session.commit()
    except Exception as e:
        app.logger.error("Seed failed: %s", e)
        db.session.rollback()

def get_all_docs():
    public = Document.query.filter_by(doc_type="public").order_by(Document.created_at.desc()).all()
    private = Document.query.filter_by(doc_type="private").order_by(Document.created_at.desc()).all()
    return {"public": [d.to_dict() for d in public], "private": [d.to_dict() for d in private]}

# ----------------- Routes -----------------
@app.route("/")
def index():
    data = get_all_docs()
    return render_template("index.html", public_docs=data["public"], private_docs=data["private"], session=session, subjects=SUBJECTS)

@app.route("/subject/<name>")
def subject(name):
    name = name or "Chung"
    public = Document.query.filter_by(doc_type="public", category=name).order_by(Document.created_at.desc()).all()
    private = Document.query.filter_by(doc_type="private", category=name).order_by(Document.created_at.desc()).all()
    return render_template("index.html", public_docs=[d.to_dict() for d in public], private_docs=[d.to_dict() for d in private], session=session, subjects=SUBJECTS, current_subject=name)

@app.route("/login", methods=["POST"])
def login():
    password = request.form.get("password", "").strip()
    if password == ADMIN_PASSWORD:
        session["logged_in"] = True
        session["admin"] = True
        flash("Đăng nhập thành công!", "success")
        return redirect(url_for("admin"))
    else:
        flash("Mật khẩu không đúng!", "error")
        return redirect(url_for("index"))

@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        flash("Vui lòng đăng nhập để truy cập trang quản trị", "error")
        return redirect(url_for("index"))
    data = get_all_docs()
    return render_template("admin.html", public_docs=data["public"], private_docs=data["private"], subjects=SUBJECTS)

@app.route("/add_document", methods=["POST"])
def add_document_route():
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Không có quyền"}), 403
    try:
        url = request.form.get("url", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        doc_type = request.form.get("type", "public")
        category = request.form.get("category", "Chung")
        if not title or len(title) < 2:
            return jsonify({"success": False, "message": "Tiêu đề phải có ít nhất 2 ký tự"})
        if not validate_url(url):
            return jsonify({"success": False, "message": "URL không hợp lệ"})
        if category not in SUBJECTS:
            category = "Chung"

        doc_id = generate_doc_id()
        key = None
        if doc_type == "private":
            key = generate_secure_key()

        new_doc = Document(
            id=doc_id,
            title=title,
            url=url,
            description=description,
            category=category,
            doc_type=doc_type,
            key=key,
            created_at=datetime.utcnow()
        )
        db.session.add(new_doc)
        db.session.commit()

        msg = "Thêm tài liệu thành công!"
        if key:
            msg += f" Key: {key}"
        return jsonify({"success": True, "message": msg, "key": key})
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error("DB add error: %s", e)
        return jsonify({"success": False, "message": "Lỗi khi lưu dữ liệu"}), 500
    except Exception as e:
        app.logger.error("Error adding document: %s", e)
        return jsonify({"success": False, "message": "Lỗi server"}), 500

@app.route("/delete/<doc_id>", methods=["POST"])
def delete_doc(doc_id):
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Không có quyền"}), 403
    try:
        doc = Document.query.get(doc_id)
        if not doc:
            return jsonify({"success": False, "message": "Không tìm thấy tài liệu"})
        db.session.delete(doc)
        db.session.commit()
        return jsonify({"success": True, "message": "Xóa tài liệu thành công"})
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error("DB delete error: %s", e)
        return jsonify({"success": False, "message": "Lỗi khi lưu dữ liệu"}), 500
    except Exception as e:
        app.logger.error("Error deleting document: %s", e)
        return jsonify({"success": False, "message": "Lỗi server"}), 500

@app.route("/access_private/<doc_id>", methods=["POST"])
def access_private(doc_id):
    entered_key = request.form.get("key", "").strip()
    doc = Document.query.get(doc_id)
    if not doc:
        flash("Tài liệu không tồn tại!", "error")
        return redirect(url_for("index"))
    if doc.key == entered_key:
        return redirect(doc.url)
    else:
        flash("Key không đúng!", "error")
        return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    flash("Đã đăng xuất thành công!", "success")
    return redirect(url_for("index"))

@app.route("/reset", methods=["POST"])
def reset_data():
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Không có quyền"}), 403
    try:
        Document.query.delete()
        db.session.commit()
        for item in SAMPLE_DATA:
            doc = Document(
                id=item["id"],
                title=item["title"],
                url=item["url"],
                description=item.get("description", ""),
                category=item.get("category", "Chung"),
                doc_type=item.get("doc_type", "public"),
                created_at=item.get("created_at", datetime.utcnow()),
                key=None
            )
            db.session.add(doc)
        db.session.commit()
        return jsonify({"success": True, "message": "Đã reset dữ liệu về mẫu!"})
    except Exception as e:
        db.session.rollback()
        app.logger.error("Error resetting data: %s", e)
        return jsonify({"success": False, "message": "Lỗi server"}), 500

@app.route("/health")
def health_check():
    try:
        public_count = Document.query.filter_by(doc_type="public").count()
        private_count = Document.query.filter_by(doc_type="private").count()
        return jsonify({"status": "healthy", "data_stats": {"public_docs": public_count, "private_docs": private_count}})
    except Exception as e:
        app.logger.error("Health check failed: %s", e)
        return jsonify({"status": "error"}), 500

# WSGI app export
application = app

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_sample_data_if_empty()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

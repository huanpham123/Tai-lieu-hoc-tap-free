from flask import Flask, render_template, request, redirect, url_for, session, flash
import secrets
from datetime import datetime
import requests
import json
import os

# Fix for Vercel deployment
current_dir = os.path.dirname(os.path.abspath(__file__))
templates_path = os.path.join(current_dir, '..', 'templates')

app = Flask(__name__, template_folder=templates_path)
app.secret_key = 'your_fixed_secret_key_for_vercel_deployment_2024'

# JSONBin configuration - using direct values instead of environment variables
JSONBIN_API_KEY = None  # Set to None to use memory storage
JSONBIN_BIN_ID = None   # Set to None to use memory storage  
JSONBIN_BASE = "https://api.jsonbin.io/v3/b"
REQUESTS_TIMEOUT = 10  # seconds

# Subjects list (menu)
SUBJECTS = ['Toán', 'Lý', 'Hóa', 'Sinh', 'Tin', 'Sử', 'Văn', 'Tiếng Anh', 'Chung']

# ---------- Memory storage for Vercel (primary storage) ----------
memory_storage = {"public": [], "private": []}
memory_bin_id = None

# ---------- Sample initial data ----------
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

# ---------- Helpers for JSON shape ----------
def normalize_data(raw):
    """Normalize various shapes into dict with 'public' and 'private' lists."""
    if raw is None:
        return {"public": [], "private": []}

    if isinstance(raw, dict) and 'record' in raw:
        raw = raw['record']

    if isinstance(raw, list):
        return {"public": raw, "private": []}

    if isinstance(raw, dict):
        public = raw.get('public', [])
        private = raw.get('private', [])
        if not isinstance(public, list):
            public = []
        if not isinstance(private, list):
            private = []
        # ensure each doc has category
        for doc in public + private:
            if 'category' not in doc:
                doc['category'] = 'Chung'
        return {"public": public, "private": []}

    return {"public": [], "private": []}

# ---------- Memory storage functions ----------
def use_memory_storage_read():
    """Read from memory storage"""
    global memory_storage
    # Initialize with sample data if empty
    if not memory_storage["public"] and not memory_storage["private"]:
        memory_storage = SAMPLE_DATA.copy()
    return memory_storage

def use_memory_storage_write(data):
    """Write to memory storage"""
    global memory_storage
    memory_storage = normalize_data(data)
    return True

# ---------- JSONBin helpers (kept for reference but disabled) ----------
def create_bin_on_jsonbin(initial_payload=None, private=True, bin_name="app_urls"):
    """JSONBin disabled - using memory storage only"""
    return None

def get_effective_bin_id():
    """JSONBin disabled - using memory storage only"""
    return None

def load_urls_from_jsonbin(bin_id):
    """JSONBin disabled - using memory storage only"""
    return None, "jsonbin_disabled"

def save_urls_to_jsonbin(bin_id, data):
    """JSONBin disabled - using memory storage only"""
    return False, "jsonbin_disabled"

# ---------- High-level load/save ----------
def load_urls():
    """Load URLs from memory storage"""
    return use_memory_storage_read()

def save_urls(data):
    """Save URLs to memory storage"""
    return use_memory_storage_write(data)

# ---------- Utility ----------
def generate_secure_key():
    return "kn1-" + secrets.token_hex(8)

def find_and_remove_doc(data, doc_id):
    """Remove document with id from data dict. Returns True if removed."""
    for bucket in ('public', 'private'):
        lst = data.get(bucket, [])
        for i, doc in enumerate(lst):
            if doc.get('id') == doc_id:
                lst.pop(i)
                return True
    return False

# ---------- Routes ----------
@app.route('/')
def index():
    data = load_urls()
    # show all by default
    all_public = data.get('public', [])
    all_private = data.get('private', [])
    return render_template('index.html', 
                         public_docs=all_public, 
                         private_docs=all_private, 
                         session=session, 
                         subjects=SUBJECTS)

@app.route('/subject/<name>')
def subject(name):
    name = name or 'Chung'
    data = load_urls()
    public = [d for d in data.get('public', []) if d.get('category', 'Chung') == name]
    private = [d for d in data.get('private', []) if d.get('category', 'Chung') == name]
    return render_template('index.html', 
                         public_docs=public, 
                         private_docs=private, 
                         session=session, 
                         subjects=SUBJECTS, 
                         current_subject=name)

@app.route('/login', methods=['POST'])
def login():
    password = request.form.get('password')
    # Fixed password for demo
    if password == 'huankk123@@':
        session['logged_in'] = True
        session['admin'] = True
        flash('Đăng nhập thành công!', 'success')
        return redirect(url_for('admin'))
    else:
        flash('Mật khẩu không đúng!', 'error')
        return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('logged_in'):
        flash('Vui lòng đăng nhập để truy cập trang quản trị', 'error')
        return redirect(url_for('index'))

    data = load_urls()

    if request.method == 'POST':
        # add new doc
        url = (request.form.get('url') or '').strip()
        title = (request.form.get('title') or '').strip()
        doc_type = request.form.get('type', 'public')
        category = request.form.get('category') or 'Chung'
        if category not in SUBJECTS:
            category = 'Chung'

        if not url or not title:
            flash('Vui lòng điền đầy đủ thông tin!', 'error')
        else:
            new_doc = {
                'id': secrets.token_hex(8),
                'title': title,
                'url': url,
                'category': category,
                'created_at': datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            if doc_type == 'private':
                new_doc['key'] = generate_secure_key()
                data.setdefault('private', []).append(new_doc)
            else:
                data.setdefault('public', []).append(new_doc)

            if save_urls(data):
                flash('Thêm tài liệu thành công!', 'success')
            else:
                flash('Lỗi khi lưu dữ liệu!', 'error')
            # reload to reflect saved state
            data = load_urls()

    return render_template('admin.html', 
                         public_docs=data.get('public', []), 
                         private_docs=data.get('private', []), 
                         subjects=SUBJECTS)

@app.route('/delete/<doc_id>', methods=['POST'])
def delete_doc(doc_id):
    if not session.get('logged_in'):
        flash('Không có quyền', 'error')
        return redirect(url_for('index'))
    
    data = load_urls()
    removed = find_and_remove_doc(data, doc_id)
    if removed:
        ok = save_urls(data)
        if ok:
            flash('Xóa tài liệu thành công', 'success')
        else:
            flash('Xóa trên bộ nhớ không thành công (lỗi lưu)', 'error')
    else:
        flash('Không tìm thấy tài liệu', 'error')
    return redirect(url_for('admin'))

@app.route('/access_private/<doc_id>', methods=['POST'])
def access_private(doc_id):
    data = load_urls()
    entered_key = (request.form.get('key') or '').strip()
    
    for doc in data.get('private', []):
        if doc.get('id') == doc_id:
            if doc.get('key') == entered_key:
                return redirect(doc.get('url') or url_for('index'))
            else:
                flash('Key không đúng!', 'error')
                return redirect(url_for('index'))
    
    flash('Tài liệu không tồn tại!', 'error')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Đã đăng xuất thành công!', 'success')
    return redirect(url_for('index'))

@app.route('/reset', methods=['POST'])
def reset_data():
    """Reset data to sample data (admin only)"""
    if not session.get('logged_in'):
        flash('Không có quyền', 'error')
        return redirect(url_for('index'))
    
    global memory_storage
    memory_storage = SAMPLE_DATA.copy()
    flash('Đã reset dữ liệu về mẫu!', 'success')
    return redirect(url_for('admin'))

@app.route('/health')
def health_check():
    """Health check endpoint for Vercel"""
    return {'status': 'healthy', 'message': 'Flask app is running on Vercel'}

# ---------- Run ----------
# Vercel requirement
application = app

if __name__ == '__main__':
    # Initialize with sample data
    use_memory_storage_write(SAMPLE_DATA)
    app.run(debug=True)

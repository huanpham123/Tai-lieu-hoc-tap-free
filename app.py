from flask import Flask, render_template, request, redirect, url_for, session, flash
import secrets
from datetime import datetime
import requests
import json
import os

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here_change_in_production')

# JSONBin configuration (optional - set these environment vars on Vercel)
JSONBIN_API_KEY = os.environ.get('JSONBIN_API_KEY')  # X-Master-Key
JSONBIN_BIN_ID = os.environ.get('JSONBIN_BIN_ID')    # bin id (may be None)
JSONBIN_BASE = "https://api.jsonbin.io/v3/b"
REQUESTS_TIMEOUT = 6  # seconds

# Local fallback for development or if JSONBin not usable
FALLBACK_FILE = "fallback_data.json"
LOCAL_BIN_ID_STORE = "local_created_bin_id.txt"

# Subjects list (menu)
SUBJECTS = ['Toán', 'Lý', 'Hóa', 'Sinh', 'Tin', 'Sử', 'Văn', 'Tiếng Anh', 'Chung']

# ---------- Helpers for JSON shape ----------
def normalize_data(raw):
    """Normalize various shapes into dict with 'public' and 'private' lists."""
    if raw is None:
        return {"public": [], "private": []}

    if isinstance(raw, dict) and 'record' in raw:
        raw = raw['record']

    if isinstance(raw, list):
        # treat as public list
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
        return {"public": public, "private": private}

    return {"public": [], "private": []}

# ---------- Local fallback I/O ----------
def use_local_fallback_read():
    if not os.path.exists(FALLBACK_FILE):
        return {"public": [], "private": []}
    try:
        with open(FALLBACK_FILE, 'r', encoding='utf-8') as f:
            return normalize_data(json.load(f))
    except Exception as e:
        print("Fallback read error:", e)
        return {"public": [], "private": []}

def use_local_fallback_write(data):
    try:
        with open(FALLBACK_FILE, 'w', encoding='utf-8') as f:
            json.dump(normalize_data(data), f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("Fallback write error:", e)
        return False

# ---------- JSONBin helpers ----------
def create_bin_on_jsonbin(initial_payload=None, private=True, bin_name="app_urls"):
    if not JSONBIN_API_KEY:
        return None
    url = JSONBIN_BASE
    headers = {
        'Content-Type': 'application/json',
        'X-Master-Key': JSONBIN_API_KEY
    }
    if bin_name:
        headers['X-Bin-Name'] = bin_name
    if private is False:
        headers['X-Bin-Private'] = 'false'
    payload = initial_payload if initial_payload is not None else {"public": [], "private": []}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=REQUESTS_TIMEOUT)
        if resp.status_code in (200, 201):
            j = resp.json()
            meta = j.get("metadata", {})
            new_id = meta.get("id")
            if new_id:
                try:
                    with open(LOCAL_BIN_ID_STORE, 'w', encoding='utf-8') as f:
                        f.write(new_id)
                except Exception:
                    pass
                return new_id
        else:
            print("Create bin failed:", resp.status_code, resp.text)
            return None
    except Exception as e:
        print("Exception creating bin:", e)
        return None

def get_effective_bin_id():
    if JSONBIN_BIN_ID:
        return JSONBIN_BIN_ID
    if os.path.exists(LOCAL_BIN_ID_STORE):
        try:
            with open(LOCAL_BIN_ID_STORE, 'r', encoding='utf-8') as f:
                v = f.read().strip()
                if v:
                    return v
        except Exception:
            pass
    return None

def load_urls_from_jsonbin(bin_id):
    if not JSONBIN_API_KEY or not bin_id:
        return None, "missing_config"
    url = f"{JSONBIN_BASE}/{bin_id}"
    headers = {'X-Master-Key': JSONBIN_API_KEY, 'Content-Type': 'application/json'}
    try:
        resp = requests.get(url, headers=headers, timeout=REQUESTS_TIMEOUT)
        if resp.status_code == 200:
            return normalize_data(resp.json()), None
        else:
            try:
                return None, resp.json().get("message", f"status_{resp.status_code}")
            except Exception:
                return None, f"status_{resp.status_code}"
    except Exception as e:
        print("JSONBin GET exception:", e)
        return None, "request_exception"

def save_urls_to_jsonbin(bin_id, data):
    if not JSONBIN_API_KEY or not bin_id:
        return False, "missing_config"
    url = f"{JSONBIN_BASE}/{bin_id}"
    headers = {'X-Master-Key': JSONBIN_API_KEY, 'Content-Type': 'application/json'}
    try:
        payload = normalize_data(data)
        resp = requests.put(url, json=payload, headers=headers, timeout=REQUESTS_TIMEOUT)
        if resp.status_code in (200, 201):
            return True, None
        else:
            try:
                return False, resp.json().get("message", f"status_{resp.status_code}")
            except Exception:
                return False, f"status_{resp.status_code}"
    except Exception as e:
        print("JSONBin PUT exception:", e)
        return False, "request_exception"

# ---------- High-level load/save ----------
def load_urls():
    # Try JSONBin if API key present
    if JSONBIN_API_KEY:
        bin_id = get_effective_bin_id()
        if bin_id:
            data, err = load_urls_from_jsonbin(bin_id)
            if data is not None:
                return data
            # If invalid bin id, try create new
            if isinstance(err, str) and ("Invalid Bin Id" in err or "status_400" in err or "Invalid Bin Id provided" in err):
                created = create_bin_on_jsonbin({"public": [], "private": []}, private=True, bin_name="auto_created_urls")
                if created:
                    data2, err2 = load_urls_from_jsonbin(created)
                    if data2 is not None:
                        return data2
            print("JSONBin read error:", err)
        else:
            # try to create one
            created = create_bin_on_jsonbin({"public": [], "private": []}, private=True, bin_name="auto_created_urls")
            if created:
                data2, err2 = load_urls_from_jsonbin(created)
                if data2 is not None:
                    return data2
            print("JSONBin: no bin id and could not create one.")
    # fallback local
    return use_local_fallback_read()

def save_urls(data):
    if JSONBIN_API_KEY:
        bin_id = get_effective_bin_id()
        if not bin_id:
            created = create_bin_on_jsonbin(data, private=True, bin_name="auto_created_urls")
            if created:
                bin_id = created
        if bin_id:
            ok, msg = save_urls_to_jsonbin(bin_id, data)
            if ok:
                return True
            else:
                # try create new bin then save
                if isinstance(msg, str) and ("Invalid Bin Id" in msg or "status_400" in msg):
                    created = create_bin_on_jsonbin(data, private=True, bin_name="auto_created_urls")
                    if created:
                        ok2, _ = save_urls_to_jsonbin(created, data)
                        if ok2:
                            return True
                print("JSONBin save error:", msg)
    # fallback to local
    return use_local_fallback_write(data)

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
    return render_template('index.html', public_docs=all_public, private_docs=all_private, session=session, subjects=SUBJECTS)

@app.route('/subject/<name>')
def subject(name):
    name = name or 'Chung'
    data = load_urls()
    public = [d for d in data.get('public', []) if d.get('category', 'Chung') == name]
    private = [d for d in data.get('private', []) if d.get('category', 'Chung') == name]
    return render_template('index.html', public_docs=public, private_docs=private, session=session, subjects=SUBJECTS, current_subject=name)

@app.route('/login', methods=['POST'])
def login():
    password = request.form.get('password')
    # NOTE: in production replace with secure auth
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

    return render_template('admin.html', public_docs=data.get('public', []), private_docs=data.get('private', []), subjects=SUBJECTS)

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

# ---------- Run ----------
def handler(request, *args, **kwargs):
    return app(request.environ, request.start_response)



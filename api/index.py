from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import secrets
from datetime import datetime
import requests
import json
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
templates_path = os.path.join(current_dir, '..', 'templates')

app = Flask(__name__, template_folder=templates_path)
app.secret_key = 'your_fixed_secret_key_for_vercel_deployment_2024'

# Configuration
SUBJECTS = ['Toán', 'Lý', 'Hóa', 'Sinh', 'Tin', 'Sử', 'Văn', 'Tiếng Anh', 'Chung']

# Memory storage
memory_storage = {"public": [], "private": []}

# Sample data
SAMPLE_DATA = {
    "public": [
        {
            "id": "sample1",
            "title": "Toán 12 - Bài giảng đại số",
            "url": "https://example.com/toan12",
            "category": "Toán",
            "created_at": "01/01/2024 10:00",
            "description": "Bài giảng đại số nâng cao lớp 12"
        },
        {
            "id": "sample2", 
            "title": "Vật lý cơ bản - Chương 1",
            "url": "https://example.com/vatly",
            "category": "Lý",
            "created_at": "01/01/2024 10:00",
            "description": "Kiến thức vật lý cơ bản chương 1"
        },
        {
            "id": "sample3",
            "title": "Hóa học hữu cơ",
            "url": "https://example.com/hoahoc",
            "category": "Hóa", 
            "created_at": "01/01/2024 10:00",
            "description": "Chuyên đề hóa học hữu cơ 11"
        }
    ],
    "private": []
}

def normalize_data(raw):
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
        for doc in public + private:
            if 'category' not in doc:
                doc['category'] = 'Chung'
            if 'description' not in doc:
                doc['description'] = ''
        return {"public": public, "private": []}
        
    return {"public": [], "private": []}

def use_memory_storage_read():
    global memory_storage
    if not memory_storage["public"] and not memory_storage["private"]:
        memory_storage = SAMPLE_DATA.copy()
    return memory_storage

def use_memory_storage_write(data):
    global memory_storage
    memory_storage = normalize_data(data)
    return True

def load_urls():
    return use_memory_storage_read()

def save_urls(data):
    return use_memory_storage_write(data)

def generate_secure_key():
    return "kn1-" + secrets.token_hex(8)

def find_and_remove_doc(data, doc_id):
    for bucket in ('public', 'private'):
        lst = data.get(bucket, [])
        for i, doc in enumerate(lst):
            if doc.get('id') == doc_id:
                lst.pop(i)
                return True
    return False

# Routes
@app.route('/')
def index():
    data = load_urls()
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
        url = (request.form.get('url') or '').strip()
        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip()
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
                'description': description,
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
            data = load_urls()

    return render_template('admin.html', 
                         public_docs=data.get('public', []), 
                         private_docs=data.get('private', []), 
                         subjects=SUBJECTS)

@app.route('/delete/<doc_id>', methods=['POST'])
def delete_doc(doc_id):
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Không có quyền'}), 403
    
    data = load_urls()
    removed = find_and_remove_doc(data, doc_id)
    if removed:
        ok = save_urls(data)
        if ok:
            return jsonify({'success': True, 'message': 'Xóa tài liệu thành công'})
        else:
            return jsonify({'success': False, 'message': 'Lỗi khi lưu dữ liệu'}), 500
    else:
        return jsonify({'success': False, 'message': 'Không tìm thấy tài liệu'}), 404

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
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Không có quyền'}), 403
    
    global memory_storage
    memory_storage = SAMPLE_DATA.copy()
    return jsonify({'success': True, 'message': 'Đã reset dữ liệu về mẫu!'})

@app.route('/health')
def health_check():
    return {'status': 'healthy', 'message': 'Flask app is running on Vercel'}

# Vercel requirement
application = app

if __name__ == '__main__':
    use_memory_storage_write(SAMPLE_DATA)
    app.run(debug=True)

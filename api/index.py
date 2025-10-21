from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import secrets
from datetime import datetime
import os
import copy

current_dir = os.path.dirname(os.path.abspath(__file__))
templates_path = os.path.join(current_dir, '..', 'templates')

app = Flask(__name__, template_folder=templates_path)
app.secret_key = 'your_fixed_secret_key_for_vercel_deployment_2024'

# Configuration
SUBJECTS = ['Toán', 'Lý', 'Hóa', 'Sinh', 'Tin', 'Sử', 'Văn', 'Tiếng Anh', 'Chung']

# Memory storage - khởi tạo rõ ràng
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
        }
    ],
    "private": []
}

def init_storage():
    """Khởi tạo storage nếu chưa có dữ liệu"""
    global memory_storage
    if not memory_storage["public"] and not memory_storage["private"]:
        memory_storage = copy.deepcopy(SAMPLE_DATA)
    return memory_storage

def load_urls():
    """Tải URLs từ memory storage"""
    try:
        return init_storage()
    except Exception as e:
        print(f"Error loading URLs: {e}")
        return {"public": [], "private": []}

def save_urls(data):
    """Lưu URLs vào memory storage"""
    try:
        global memory_storage
        # Validate data structure
        if not isinstance(data, dict):
            return False
            
        memory_storage["public"] = data.get("public", [])
        memory_storage["private"] = data.get("private", [])
        return True
    except Exception as e:
        print(f"Error saving URLs: {e}")
        return False

def generate_secure_key():
    """Tạo key bảo mật"""
    return "kn1-" + secrets.token_hex(8)

def generate_doc_id():
    """Tạo ID duy nhất cho document"""
    return secrets.token_hex(8)

def validate_url(url):
    """Validate URL format"""
    if not url:
        return False
    url = url.strip()
    return url.startswith('http://') or url.startswith('https://')

def add_document(data, title, url, description, category, doc_type):
    """Thêm document mới vào data"""
    try:
        new_doc = {
            'id': generate_doc_id(),
            'title': title.strip(),
            'url': url.strip(),
            'description': description.strip(),
            'category': category,
            'created_at': datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        
        if doc_type == 'private':
            new_doc['key'] = generate_secure_key()
            data["private"].append(new_doc)
            return True, new_doc['key']
        else:
            data["public"].append(new_doc)
            return True, None
            
    except Exception as e:
        print(f"Error adding document: {e}")
        return False, None

def delete_document(data, doc_id):
    """Xóa document khỏi data"""
    try:
        # Tìm trong public documents
        for i, doc in enumerate(data["public"]):
            if doc.get('id') == doc_id:
                data["public"].pop(i)
                return True
                
        # Tìm trong private documents  
        for i, doc in enumerate(data["private"]):
            if doc.get('id') == doc_id:
                data["private"].pop(i)
                return True
                
        return False
    except Exception as e:
        print(f"Error deleting document: {e}")
        return False

# Routes
@app.route('/')
def index():
    """Trang chủ"""
    data = load_urls()
    return render_template('index.html', 
                         public_docs=data["public"], 
                         private_docs=data["private"], 
                         session=session, 
                         subjects=SUBJECTS)

@app.route('/subject/<name>')
def subject(name):
    """Trang theo môn học"""
    name = name or 'Chung'
    data = load_urls()
    public = [d for d in data["public"] if d.get('category', 'Chung') == name]
    private = [d for d in data["private"] if d.get('category', 'Chung') == name]
    return render_template('index.html', 
                         public_docs=public, 
                         private_docs=private, 
                         session=session, 
                         subjects=SUBJECTS, 
                         current_subject=name)

@app.route('/login', methods=['POST'])
def login():
    """Đăng nhập admin"""
    password = request.form.get('password', '').strip()
    if password == 'huankk123@@':
        session['logged_in'] = True
        session['admin'] = True
        flash('Đăng nhập thành công!', 'success')
        return redirect(url_for('admin'))
    else:
        flash('Mật khẩu không đúng!', 'error')
        return redirect(url_for('index'))

@app.route('/admin')
def admin():
    """Trang quản trị"""
    if not session.get('logged_in'):
        flash('Vui lòng đăng nhập để truy cập trang quản trị', 'error')
        return redirect(url_for('index'))

    data = load_urls()
    return render_template('admin.html', 
                         public_docs=data["public"], 
                         private_docs=data["private"], 
                         subjects=SUBJECTS)

@app.route('/add_document', methods=['POST'])
def add_document_route():
    """API thêm document mới"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Không có quyền'}), 403

    try:
        url = request.form.get('url', '').strip()
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        doc_type = request.form.get('type', 'public')
        category = request.form.get('category', 'Chung')

        # Validate input
        if not title or len(title) < 2:
            return jsonify({'success': False, 'message': 'Tiêu đề phải có ít nhất 2 ký tự'})
        
        if not validate_url(url):
            return jsonify({'success': False, 'message': 'URL không hợp lệ'})
        
        if category not in SUBJECTS:
            category = 'Chung'

        # Load current data
        data = load_urls()
        data_copy = copy.deepcopy(data)
        
        # Add document
        success, key = add_document(data_copy, title, url, description, category, doc_type)
        
        if success:
            # Save updated data
            if save_urls(data_copy):
                message = 'Thêm tài liệu thành công!'
                if key:
                    message += f' Key: {key}'
                return jsonify({'success': True, 'message': message, 'key': key})
            else:
                return jsonify({'success': False, 'message': 'Lỗi khi lưu dữ liệu'})
        else:
            return jsonify({'success': False, 'message': 'Lỗi khi thêm tài liệu'})
            
    except Exception as e:
        print(f"Error adding document: {e}")
        return jsonify({'success': False, 'message': 'Lỗi server'}), 500

@app.route('/delete/<doc_id>', methods=['POST'])
def delete_doc(doc_id):
    """Xóa document"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Không có quyền'}), 403
    
    try:
        if not doc_id:
            return jsonify({'success': False, 'message': 'ID không hợp lệ'})
            
        data = load_urls()
        data_copy = copy.deepcopy(data)
        
        if delete_document(data_copy, doc_id):
            if save_urls(data_copy):
                return jsonify({'success': True, 'message': 'Xóa tài liệu thành công'})
            else:
                return jsonify({'success': False, 'message': 'Lỗi khi lưu dữ liệu'})
        else:
            return jsonify({'success': False, 'message': 'Không tìm thấy tài liệu'})
            
    except Exception as e:
        print(f"Error deleting document: {e}")
        return jsonify({'success': False, 'message': 'Lỗi server'}), 500

@app.route('/access_private/<doc_id>', methods=['POST'])
def access_private(doc_id):
    """Truy cập tài liệu private với key"""
    data = load_urls()
    entered_key = request.form.get('key', '').strip()
    
    for doc in data["private"]:
        if doc.get('id') == doc_id:
            if doc.get('key') == entered_key:
                return redirect(doc.get('url'))
            else:
                flash('Key không đúng!', 'error')
                return redirect(url_for('index'))
    
    flash('Tài liệu không tồn tại!', 'error')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """Đăng xuất"""
    session.clear()
    flash('Đã đăng xuất thành công!', 'success')
    return redirect(url_for('index'))

@app.route('/reset', methods=['POST'])
def reset_data():
    """Reset dữ liệu về mẫu"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Không có quyền'}), 403
    
    global memory_storage
    memory_storage = copy.deepcopy(SAMPLE_DATA)
    return jsonify({'success': True, 'message': 'Đã reset dữ liệu về mẫu!'})

@app.route('/health')
def health_check():
    """Health check endpoint"""
    data = load_urls()
    return jsonify({
        'status': 'healthy', 
        'data_stats': {
            'public_docs': len(data["public"]),
            'private_docs': len(data["private"])
        }
    })

# Vercel requirement
application = app

if __name__ == '__main__':
    init_storage()
    app.run(debug=True)

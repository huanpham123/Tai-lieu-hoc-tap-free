from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import secrets
from datetime import datetime
import requests
import json
import os
import copy

current_dir = os.path.dirname(os.path.abspath(__file__))
templates_path = os.path.join(current_dir, '..', 'templates')

app = Flask(__name__, template_folder=templates_path)
app.secret_key = 'your_fixed_secret_key_for_vercel_deployment_2024'

# Configuration
SUBJECTS = ['Toán', 'Lý', 'Hóa', 'Sinh', 'Tin', 'Sử', 'Văn', 'Tiếng Anh', 'Chung']

# Memory storage với deep copy để tránh tham chiếu
memory_storage = {"public": [], "private": []}

# Sample data với ID cố định
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
    """Chuẩn hóa dữ liệu với kiểm tra chặt chẽ"""
    if raw is None:
        return {"public": [], "private": []}
    
    # Tạo bản sao để tránh thay đổi dữ liệu gốc
    data = copy.deepcopy(raw)
    
    if isinstance(data, dict) and 'record' in data:
        data = data['record']
        
    if isinstance(data, list):
        return {"public": data, "private": []}
        
    if isinstance(data, dict):
        public = data.get('public', [])
        private = data.get('private', [])
        
        # Đảm bảo public và private là list
        if not isinstance(public, list):
            public = []
        if not isinstance(private, list):
            private = []
            
        # Validate từng document
        validated_public = []
        for doc in public:
            if isinstance(doc, dict) and doc.get('id') and doc.get('title'):
                # Đảm bảo có đầy đủ fields
                doc.setdefault('category', 'Chung')
                doc.setdefault('description', '')
                doc.setdefault('created_at', datetime.now().strftime("%d/%m/%Y %H:%M"))
                validated_public.append(doc)
                
        validated_private = []
        for doc in private:
            if isinstance(doc, dict) and doc.get('id') and doc.get('title') and doc.get('key'):
                doc.setdefault('category', 'Chung')
                doc.setdefault('description', '')
                doc.setdefault('created_at', datetime.now().strftime("%d/%m/%Y %H:%M"))
                validated_private.append(doc)
                
        return {
            "public": validated_public,
            "private": validated_private
        }
        
    return {"public": [], "private": []}

def use_memory_storage_read():
    """Đọc từ memory storage với validation"""
    global memory_storage
    # Kiểm tra nếu memory storage rỗng thì khởi tạo với sample data
    if not memory_storage.get("public") and not memory_storage.get("private"):
        memory_storage = normalize_data(SAMPLE_DATA)
    return normalize_data(memory_storage)

def use_memory_storage_write(data):
    """Ghi vào memory storage với validation"""
    global memory_storage
    validated_data = normalize_data(data)
    memory_storage = validated_data
    return True

def load_urls():
    """Tải URLs với error handling"""
    try:
        return use_memory_storage_read()
    except Exception as e:
        print(f"Error loading URLs: {e}")
        return {"public": [], "private": []}

def save_urls(data):
    """Lưu URLs với error handling"""
    try:
        return use_memory_storage_write(data)
    except Exception as e:
        print(f"Error saving URLs: {e}")
        return False

def generate_secure_key():
    """Tạo key bảo mật"""
    return "kn1-" + secrets.token_hex(8)

def generate_doc_id():
    """Tạo ID duy nhất cho document"""
    return secrets.token_hex(12)

def find_and_remove_doc(data, doc_id):
    """Tìm và xóa document theo ID - trả về data mới"""
    if not data or not doc_id:
        return False, data
        
    data_copy = copy.deepcopy(data)
    removed = False
    
    # Tìm trong public documents
    public_docs = data_copy.get('public', [])
    for i, doc in enumerate(public_docs):
        if doc.get('id') == doc_id:
            public_docs.pop(i)
            removed = True
            break
            
    # Tìm trong private documents
    if not removed:
        private_docs = data_copy.get('private', [])
        for i, doc in enumerate(private_docs):
            if doc.get('id') == doc_id:
                private_docs.pop(i)
                removed = True
                break
                
    return removed, data_copy

def validate_url(url):
    """Validate URL format"""
    if not url:
        return False
    url = url.strip()
    return url.startswith('http://') or url.startswith('https://')

def validate_doc_data(title, url, category):
    """Validate document data"""
    errors = []
    if not title or len(title.strip()) < 2:
        errors.append("Tiêu đề phải có ít nhất 2 ký tự")
    if not validate_url(url):
        errors.append("URL không hợp lệ (phải bắt đầu với http:// hoặc https://)")
    if category not in SUBJECTS:
        errors.append("Chuyên mục không hợp lệ")
    return errors

# Routes
@app.route('/')
def index():
    """Trang chủ"""
    try:
        data = load_urls()
        all_public = data.get('public', [])
        all_private = data.get('private', [])
        return render_template('index.html', 
                             public_docs=all_public, 
                             private_docs=all_private, 
                             session=session, 
                             subjects=SUBJECTS)
    except Exception as e:
        print(f"Error in index route: {e}")
        return render_template('index.html', 
                             public_docs=[], 
                             private_docs=[], 
                             session=session, 
                             subjects=SUBJECTS)

@app.route('/subject/<name>')
def subject(name):
    """Trang theo môn học"""
    try:
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
    except Exception as e:
        print(f"Error in subject route: {e}")
        return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    """Đăng nhập admin"""
    try:
        password = request.form.get('password', '').strip()
        # Fixed password for demo
        if password == 'huankk123@@':
            session['logged_in'] = True
            session['admin'] = True
            flash('Đăng nhập thành công!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Mật khẩu không đúng!', 'error')
            return redirect(url_for('index'))
    except Exception as e:
        print(f"Error in login: {e}")
        flash('Lỗi đăng nhập!', 'error')
        return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    """Trang quản trị"""
    if not session.get('logged_in'):
        flash('Vui lòng đăng nhập để truy cập trang quản trị', 'error')
        return redirect(url_for('index'))

    try:
        data = load_urls()

        if request.method == 'POST':
            # Xử lý thêm document mới
            url = request.form.get('url', '').strip()
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            doc_type = request.form.get('type', 'public')
            category = request.form.get('category', 'Chung')
            
            # Validate input
            errors = validate_doc_data(title, url, category)
            if errors:
                for error in errors:
                    flash(error, 'error')
            else:
                new_doc = {
                    'id': generate_doc_id(),
                    'title': title,
                    'url': url,
                    'description': description,
                    'category': category,
                    'created_at': datetime.now().strftime("%d/%m/%Y %H:%M")
                }
                
                # Tạo bản sao của data để tránh thay đổi trực tiếp
                data_copy = copy.deepcopy(data)
                
                if doc_type == 'private':
                    new_doc['key'] = generate_secure_key()
                    data_copy.setdefault('private', []).append(new_doc)
                    flash(f'Thêm tài liệu mật thành công! Key: {new_doc["key"]}', 'success')
                else:
                    data_copy.setdefault('public', []).append(new_doc)
                    flash('Thêm tài liệu công khai thành công!', 'success')

                # Lưu dữ liệu
                if save_urls(data_copy):
                    data = load_urls()  # Reload data để hiển thị
                else:
                    flash('Lỗi khi lưu dữ liệu!', 'error')

        return render_template('admin.html', 
                             public_docs=data.get('public', []), 
                             private_docs=data.get('private', []), 
                             subjects=SUBJECTS)
                             
    except Exception as e:
        print(f"Error in admin route: {e}")
        flash('Lỗi tải trang quản trị!', 'error')
        return redirect(url_for('index'))

@app.route('/delete/<doc_id>', methods=['POST'])
def delete_doc(doc_id):
    """Xóa document"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Không có quyền'}), 403
    
    try:
        if not doc_id:
            return jsonify({'success': False, 'message': 'ID không hợp lệ'}), 400
            
        data = load_urls()
        removed, new_data = find_and_remove_doc(data, doc_id)
        
        if removed:
            if save_urls(new_data):
                return jsonify({'success': True, 'message': 'Xóa tài liệu thành công'})
            else:
                return jsonify({'success': False, 'message': 'Lỗi khi lưu dữ liệu'}), 500
        else:
            return jsonify({'success': False, 'message': 'Không tìm thấy tài liệu'}), 404
            
    except Exception as e:
        print(f"Error deleting document: {e}")
        return jsonify({'success': False, 'message': 'Lỗi server khi xóa tài liệu'}), 500

@app.route('/access_private/<doc_id>', methods=['POST'])
def access_private(doc_id):
    """Truy cập tài liệu private với key"""
    try:
        if not doc_id:
            flash('ID tài liệu không hợp lệ!', 'error')
            return redirect(url_for('index'))
            
        data = load_urls()
        entered_key = request.form.get('key', '').strip()
        
        # Tìm document trong private docs
        for doc in data.get('private', []):
            if doc.get('id') == doc_id:
                if doc.get('key') == entered_key:
                    return redirect(doc.get('url', url_for('index')))
                else:
                    flash('Key không đúng!', 'error')
                    return redirect(url_for('index'))
        
        flash('Tài liệu không tồn tại!', 'error')
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"Error accessing private doc: {e}")
        flash('Lỗi truy cập tài liệu!', 'error')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """Đăng xuất"""
    try:
        session.clear()
        flash('Đã đăng xuất thành công!', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Error logging out: {e}")
        return redirect(url_for('index'))

@app.route('/reset', methods=['POST'])
def reset_data():
    """Reset dữ liệu về mẫu"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Không có quyền'}), 403
    
    try:
        global memory_storage
        memory_storage = normalize_data(SAMPLE_DATA)
        return jsonify({'success': True, 'message': 'Đã reset dữ liệu về mẫu!'})
    except Exception as e:
        print(f"Error resetting data: {e}")
        return jsonify({'success': False, 'message': 'Lỗi khi reset dữ liệu'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy', 
        'message': 'Flask app is running on Vercel',
        'data_stats': {
            'public_docs': len(memory_storage.get('public', [])),
            'private_docs': len(memory_storage.get('private', []))
        }
    })

@app.errorhandler(404)
def not_found(error):
    """Xử lý 404 error"""
    return jsonify({'success': False, 'message': 'Endpoint không tồn tại'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Xử lý 500 error"""
    return jsonify({'success': False, 'message': 'Lỗi server nội bộ'}), 500

# Vercel requirement
application = app

if __name__ == '__main__':
    # Khởi tạo với sample data
    use_memory_storage_write(SAMPLE_DATA)
    print("Sample data initialized:")
    print(f"Public docs: {len(memory_storage['public'])}")
    print(f"Private docs: {len(memory_storage['private'])}")
    app.run(debug=True)

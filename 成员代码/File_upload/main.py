from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_mysqldb import MySQL
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)


app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'user_system'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'


app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.secret_key = 'your_secret_key_here'


app.config['ADMIN_USERNAME'] = 'admin'
app.config['ADMIN_PASSWORD'] = 'admin123'


os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

mysql = MySQL(app)


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def is_image(filename):
    return filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))


@app.route('/', methods=['GET', 'POST'])
def index():
    if 'loggedin' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']


        if username == app.config['ADMIN_USERNAME'] and password == app.config['ADMIN_PASSWORD']:
            session['loggedin'] = True
            session['is_admin'] = True
            session['username'] = username
            return redirect(url_for('admin_dashboard'))

        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        account = cursor.fetchone()

        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            session['is_admin'] = False
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码不正确!', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'loggedin' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']

        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        account = cursor.fetchone()

        if account:
            flash('用户名已存在!', 'danger')
        else:
            cursor.execute('INSERT INTO users (username, password) VALUES (%s, %s)', (username, password))
            mysql.connection.commit()
            flash('注册成功，请登录!', 'success')
            return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    if 'loggedin' not in session:
        return redirect(url_for('index'))


    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(session['id']))
    files = os.listdir(user_folder) if os.path.exists(user_folder) else []

    return render_template('dashboard.html', files=files)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'loggedin' not in session:
        return redirect(url_for('index'))

    if 'file' not in request.files:
        flash('没有选择文件', 'danger')
        return redirect(url_for('dashboard'))

    file = request.files['file']
    if file.filename == '':
        flash('没有选择文件', 'danger')
        return redirect(url_for('dashboard'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(session['id']))
        os.makedirs(user_folder, exist_ok=True)
        file.save(os.path.join(user_folder, filename))
        flash('文件上传成功!', 'success')
    else:
        flash('不允许的文件类型!', 'danger')

    return redirect(url_for('dashboard'))


@app.route('/view/<filename>')
def view_file(filename):
    if 'loggedin' not in session:
        return redirect(url_for('index'))

    user_id = session['id'] if not session.get('is_admin') else request.args.get('user_id', session['id'])
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
    filepath = os.path.join(user_folder, filename)

    if not os.path.exists(filepath):
        flash('文件不存在!', 'danger')
        return redirect(url_for('admin_dashboard' if session.get('is_admin') else 'dashboard'))

    if is_image(filename):
        return send_from_directory(user_folder, filename)
    else:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return render_template('view_file.html', filename=filename, content=content)


@app.route('/admin')
def admin_dashboard():
    if 'loggedin' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))


    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()


    users_with_images = []
    for user in users:
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user['id']))
        if os.path.exists(user_folder):
            images = [f for f in os.listdir(user_folder) if is_image(f)]
        else:
            images = []
        users_with_images.append({
            'id': user['id'],
            'username': user['username'],
            'image_count': len(images),
            'images': images[:5]
        })

    return render_template('admin_dashboard.html', users=users_with_images)


@app.route('/admin/user/<int:user_id>')
def admin_view_user(user_id):
    if 'loggedin' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))


    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()

    if not user:
        flash('用户不存在!', 'danger')
        return redirect(url_for('admin_dashboard'))


    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
    if os.path.exists(user_folder):
        images = [f for f in os.listdir(user_folder) if is_image(f)]
    else:
        images = []

    return render_template('admin_user_images.html', user=user, images=images)


@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    session.pop('is_admin', None)
    return redirect(url_for('index'))


if __name__ == '__main__':
    with app.app_context():
        cursor = mysql.connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password VARCHAR(100) NOT NULL
            )
        ''')
        mysql.connection.commit()


    cert_file = "cert\\_ wzy-kxsfbsy114514.top_chain.pem"
    key_file = "cert\\_ wzy-kxsfbsy114514.top_key.key"

    app.run(
        debug=True,
        ssl_context=(cert_file, key_file)
    )
import os
import sqlite3
import hashlib
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import datetime
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = os.urandom(24)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'zip', 'rar'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_ADDRESS = 'tu_correo@gmail.com'
EMAIL_PASSWORD = 'tu_contraseña_de_aplicación' # ¡NUNCA tu contraseña real!

def get_db_connection():
    conn = sqlite3.connect('usuarios.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT,
            company_name TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS dinerito_data (
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            ingresos REAL,
            egresos REAL,
            PRIMARY KEY (user_id, month),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS inventario_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            quantity REAL,
            price REAL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS facturas_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            invoice_number TEXT,
            invoice_date TEXT,
            client_name TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS factura_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            description TEXT,
            quantity REAL,
            price REAL,
            FOREIGN KEY (invoice_id) REFERENCES facturas_data (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS recibos_ingresos_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            receipt_number TEXT,
            receipt_date TEXT,
            payer_name TEXT,
            amount_received REAL,
            concept TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notas_credito_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            credit_note_number TEXT,
            credit_note_date TEXT,
            related_invoice TEXT,
            reason TEXT,
            credited_amount REAL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ordenes_compra_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_number TEXT,
            order_date TEXT,
            supplier_name TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orden_compra_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            description TEXT,
            quantity REAL,
            price REAL,
            FOREIGN KEY (order_id) REFERENCES ordenes_compra_data (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS guias_de_remision_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            guide_number TEXT,
            guide_date TEXT,
            start_point TEXT,
            end_point TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS guia_de_remision_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guide_id INTEGER NOT NULL,
            product TEXT,
            quantity REAL,
            FOREIGN KEY (guide_id) REFERENCES guias_de_remision_data (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS boletas_venta_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            boleta_number TEXT,
            boleta_date TEXT,
            client_name TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS boleta_venta_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boleta_id INTEGER NOT NULL,
            description TEXT,
            quantity REAL,
            price REAL,
            FOREIGN KEY (boleta_id) REFERENCES boletas_venta_data (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS text_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            subject TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS uploaded_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS html_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            title TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, hashed_password)).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error='Usuario o contraseña incorrectos.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form.get('email')
        company_name = request.form.get('company_name')

        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (username, password, email, company_name) VALUES (?, ?, ?, ?)",
                         (username, hashed_password, email, company_name))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error='El nombre de usuario ya existe.')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/home')
@login_required
def home():
    return render_template('home.html')

@app.route('/documentos')
@login_required
def documentos():
    return render_template('documentos.html')

@app.route('/dinerito')
@login_required
def dinerito():
    return render_template('dinerito.html')

@app.route('/inventario')
@login_required
def inventario():
    return render_template('inventario.html')

@app.route('/facturas')
@login_required
def facturas():
    return render_template('facturas.html')

@app.route('/guias_de_remision')
@login_required
def guias_de_remision():
    return render_template('guias_de_remision.html')

@app.route('/orden_de_compra')
@login_required
def orden_de_compra():
    return render_template('orden_de_compra.html')

@app.route('/boleta_de_venta')
@login_required
def boleta_de_venta():
    return render_template('boleta_de_venta.html')

@app.route('/recibos_de_ingresos')
@login_required
def recibos_de_ingresos():
    return render_template('recibos_de_ingresos.html')

@app.route('/nota_de_credito')
@login_required
def nota_de_credito():
    return render_template('nota_de_credito.html')

@app.route('/mi_progreso')
@login_required
def mi_progreso():
    return render_template('mi_progreso.html')

@app.route('/motivacion')
@login_required
def motivacion():
    return render_template('motivacion.html')

@app.route('/memorando')
@login_required
def memorando():
    return render_template('memorando.html')

@app.route('/oficio')
@login_required
def oficio():
    return render_template('oficio.html')

@app.route('/informe')
@login_required
def informe():
    return render_template('informe.html')

@app.route('/acta')
@login_required
def acta():
    return render_template('acta.html')

@app.route('/solicitud')
@login_required
def solicitud():
    return render_template('solicitud.html')

@app.route('/plantillas')
@login_required
def plantillas():
    return render_template('plantillas.html')

@app.route('/save_html_document', methods=['POST'])
@login_required
def save_html_document():
    user_id = session['user_id']
    data = request.json
    document_type = data.get('document_type')
    title = data.get('title')
    content = data.get('content')
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO html_documents (user_id, document_type, title, content) VALUES (?, ?, ?, ?)', 
                     (user_id, document_type, title, content))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Documento guardado con éxito.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': f'Error al guardar: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/get_html_documents', methods=['GET'])
@login_required
def get_html_documents():
    user_id = session['user_id']
    conn = get_db_connection()
    try:
        documents = conn.execute('SELECT document_type, title, content, created_at FROM html_documents WHERE user_id = ? ORDER BY created_at DESC', (user_id,)).fetchall()
        
        document_list = []
        for doc in documents:
            document_list.append({
                'document_type': doc['document_type'],
                'title': doc['title'],
                'content': doc['content'],
                'created_at': doc['created_at']
            })
        
        return jsonify({'documentos': document_list})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()


@app.route('/save_text_document', methods=['POST'])
@login_required
def save_text_document():
    user_id = session['user_id']
    data = request.json
    document_type = data.get('document_type')
    subject = data.get('subject')
    content = data.get('content')
    
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM text_documents WHERE user_id = ? AND document_type = ?', (user_id, document_type))
        conn.execute('INSERT INTO text_documents (user_id, document_type, subject, content) VALUES (?, ?, ?, ?)', (user_id, document_type, subject, content))
        conn.commit()
        return jsonify({'success': True, 'message': 'Documento guardado con éxito.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/get_text_document', methods=['GET'])
@login_required
def get_text_document():
    user_id = session['user_id']
    document_type = request.args.get('type')
    
    conn = get_db_connection()
    document = conn.execute('SELECT subject, content FROM text_documents WHERE user_id = ? AND document_type = ? ORDER BY created_at DESC LIMIT 1', (user_id, document_type)).fetchone()
    conn.close()
    
    if document:
        return jsonify({'subject': document['subject'], 'content': document['content']})
    else:
        return jsonify({})

@app.route('/save_dinerito_data', methods=['POST'])
@login_required
def save_dinerito_data():
    user_id = session['user_id']
    data = request.json
    conn = get_db_connection()
    try:
        for month, values in data.items():
            conn.execute('INSERT OR REPLACE INTO dinerito_data (user_id, month, ingresos, egresos) VALUES (?, ?, ?, ?)', (user_id, month, values['ingresos'], values['egresos']))
        conn.commit()
        return jsonify({'success': True, 'message': 'Datos guardados con éxito.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/get_dinerito_data', methods=['GET'])
@login_required
def get_dinerito_data():
    user_id = session['user_id']
    conn = get_db_connection()
    rows = conn.execute('SELECT month, ingresos, egresos FROM dinerito_data WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    data = {row['month']: {'ingresos': row['ingresos'], 'egresos': row['egresos']} for row in rows}
    return jsonify(data)

@app.route('/save_inventario_data', methods=['POST'])
@login_required
def save_inventario_data():
    user_id = session['user_id']
    data = request.json
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM inventario_data WHERE user_id = ?', (user_id,))
        for item in data:
            if item['item'] and item['quantity'] > 0:
                conn.execute('INSERT INTO inventario_data (user_id, item_name, quantity, price) VALUES (?, ?, ?, ?)', (user_id, item['item'], item['quantity'], item['price']))
        conn.commit()
        return jsonify({'success': True, 'message': 'Inventario guardado con éxito.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/get_inventario_data', methods=['GET'])
@login_required
def get_inventario_data():
    user_id = session['user_id']
    conn = get_db_connection()
    rows = conn.execute('SELECT item_name, quantity, price FROM inventario_data WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    data = [{'item': row['item_name'], 'quantity': row['quantity'], 'price': row['price']} for row in rows]
    return jsonify(data)

@app.route('/save_facturas_data', methods=['POST'])
@login_required
def save_facturas_data():
    user_id = session['user_id']
    data = request.json
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM factura_items WHERE invoice_id IN (SELECT id FROM facturas_data WHERE user_id = ?)', (user_id,))
        conn.execute('DELETE FROM facturas_data WHERE user_id = ?', (user_id,))
        cursor = conn.execute('INSERT INTO facturas_data (user_id, invoice_number, invoice_date, client_name) VALUES (?, ?, ?, ?)', (user_id, data['invoice_number'], data['invoice_date'], data['client_name']))
        invoice_id = cursor.lastrowid
        for item in data['items']:
            if item['description']:
                conn.execute('INSERT INTO factura_items (invoice_id, description, quantity, price) VALUES (?, ?, ?, ?)', (invoice_id, item['description'], item['quantity'], item['price']))
        conn.commit()
        return jsonify({'success': True, 'message': 'Factura guardada con éxito.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'}), 500
    finally:
        conn.close()
    
@app.route('/get_facturas_data', methods=['GET'])
@login_required
def get_facturas_data():
    user_id = session['user_id']
    conn = get_db_connection()
    try:
        invoice = conn.execute('SELECT id, invoice_number, invoice_date, client_name FROM facturas_data WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,)).fetchone()
        if not invoice:
            return jsonify({})
        items = conn.execute('SELECT description, quantity, price FROM factura_items WHERE invoice_id = ?', (invoice['id'],)).fetchall()
        data = {'invoice_number': invoice['invoice_number'],'invoice_date': invoice['invoice_date'],'client_name': invoice['client_name'],'items': [{'description': item['description'], 'quantity': item['quantity'], 'price': item['price']} for item in items]}
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/save_recibos_de_ingresos_data', methods=['POST'])
@login_required
def save_recibos_de_ingresos_data():
    user_id = session['user_id']
    data = request.json
    conn = get_db_connection()
    try:
        conn.execute('INSERT OR REPLACE INTO recibos_ingresos_data (user_id, receipt_number, receipt_date, payer_name, amount_received, concept) VALUES (?, ?, ?, ?, ?, ?)',(user_id, data['receipt_number'], data['receipt_date'], data['payer_name'], data['amount_received'], data['concept']))
        conn.commit()
        return jsonify({'success': True, 'message': 'Recibo guardado con éxito.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'}), 500
    finally:
        conn.close()
    
@app.route('/get_recibos_de_ingresos_data', methods=['GET'])
@login_required
def get_recibos_de_ingresos_data():
    user_id = session['user_id']
    conn = get_db_connection()
    try:
        row = conn.execute('SELECT receipt_number, receipt_date, payer_name, amount_received, concept FROM recibos_ingresos_data WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,)).fetchone()
        if row:
            return jsonify({'receipt_number': row['receipt_number'],'receipt_date': row['receipt_date'],'payer_name': row['payer_name'],'amount_received': row['amount_received'],'concept': row['concept']})
        else:
            return jsonify({})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/save_nota_de_credito_data', methods=['POST'])
@login_required
def save_nota_de_credito_data():
    user_id = session['user_id']
    data = request.json
    conn = get_db_connection()
    try:
        conn.execute('INSERT OR REPLACE INTO notas_credito_data (user_id, credit_note_number, credit_note_date, related_invoice, reason, credited_amount) VALUES (?, ?, ?, ?, ?, ?)',(user_id, data['credit_note_number'], data['credit_note_date'], data['related_invoice'], data['reason'], data['credited_amount']))
        conn.commit()
        return jsonify({'success': True, 'message': 'Nota de crédito guardada con éxito.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/get_nota_de_credito_data', methods=['GET'])
@login_required
def get_nota_de_credito_data():
    user_id = session['user_id']
    conn = get_db_connection()
    try:
        row = conn.execute('SELECT credit_note_number, credit_note_date, related_invoice, reason, credited_amount FROM notas_credito_data WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,)).fetchone()
        if row:
            return jsonify({'credit_note_number': row['credit_note_number'],'credit_note_date': row['credit_note_date'],'related_invoice': row['related_invoice'],'reason': row['reason'],'credited_amount': row['credited_amount']})
        else:
            return jsonify({})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/save_orden_de_compra_data', methods=['POST'])
@login_required
def save_orden_de_compra_data():
    user_id = session['user_id']
    data = request.json
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM orden_compra_items WHERE order_id IN (SELECT id FROM ordenes_compra_data WHERE user_id = ?)', (user_id,))
        conn.execute('DELETE FROM ordenes_compra_data WHERE user_id = ?', (user_id,))
        cursor = conn.execute('INSERT INTO ordenes_compra_data (user_id, order_number, order_date, supplier_name) VALUES (?, ?, ?, ?)', (user_id, data['order_number'], data['order_date'], data['supplier_name']))
        order_id = cursor.lastrowid
        for item in data['items']:
            if item['description']:
                conn.execute('INSERT INTO orden_compra_items (order_id, description, quantity, price) VALUES (?, ?, ?, ?)', (order_id, item['description'], item['quantity'], item['price']))
        conn.commit()
        return jsonify({'success': True, 'message': 'Orden de compra guardada con éxito.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'}), 500
    finally:
        conn.close()
    
@app.route('/get_orden_de_compra_data', methods=['GET'])
@login_required
def get_orden_de_compra_data():
    user_id = session['user_id']
    conn = get_db_connection()
    try:
        order = conn.execute('SELECT id, order_number, order_date, supplier_name FROM ordenes_compra_data WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,)).fetchone()
        if not order:
            return jsonify({})
        items = conn.execute('SELECT description, quantity, price FROM orden_compra_items WHERE order_id = ?', (order['id'],)).fetchall()
        data = {'order_number': order['order_number'],'order_date': order['order_date'],'supplier_name': order['supplier_name'],'items': [{'description': item['description'], 'quantity': item['quantity'], 'price': item['price']} for item in items]}
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/save_guias_de_remision_data', methods=['POST'])
@login_required
def save_guias_de_remision_data():
    user_id = session['user_id']
    data = request.json
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM guia_de_remision_items WHERE guide_id IN (SELECT id FROM guias_de_remision_data WHERE user_id = ?)', (user_id,))
        conn.execute('DELETE FROM guias_de_remision_data WHERE user_id = ?', (user_id,))
        cursor = conn.execute('INSERT INTO guias_de_remision_data (user_id, guide_number, guide_date, start_point, end_point) VALUES (?, ?, ?, ?, ?)', (user_id, data['guide_number'], data['guide_date'], data['start_point'], data['end_point']))
        guide_id = cursor.lastrowid
        for item in data['items']:
            if item['product']:
                conn.execute('INSERT INTO guia_de_remision_items (guide_id, product, quantity) VALUES (?, ?, ?)', (guide_id, item['product'], item['quantity']))
        conn.commit()
        return jsonify({'success': True, 'message': 'Guía de remisión guardada con éxito.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'}), 500
    finally:
        conn.close()

@app.route('/get_guias_de_remision_data', methods=['GET'])
@login_required
def get_guias_de_remision_data():
    user_id = session['user_id']
    conn = get_db_connection()
    try:
        guide = conn.execute('SELECT id, guide_number, guide_date, start_point, end_point FROM guias_de_remision_data WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,)).fetchone()
        if not guide:
            return jsonify({})
        items = conn.execute('SELECT product, quantity FROM guia_de_remision_items WHERE guide_id = ?', (guide['id'],)).fetchall()
        data = {'guide_number': guide['guide_number'],'guide_date': guide['guide_date'],'start_point': guide['start_point'],'end_point': guide['end_point'],'items': [{'product': item['product'], 'quantity': item['quantity']} for item in items]}
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/save_boleta_de_venta_data', methods=['POST'])
@login_required
def save_boleta_de_venta_data():
    user_id = session['user_id']
    data = request.json
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM boleta_venta_items WHERE boleta_id IN (SELECT id FROM boletas_venta_data WHERE user_id = ?)', (user_id,))
        conn.execute('DELETE FROM boletas_venta_data WHERE user_id = ?', (user_id,))
        cursor = conn.execute('INSERT INTO boletas_venta_data (user_id, boleta_number, boleta_date, client_name) VALUES (?, ?, ?, ?)', (user_id, data['boleta_number'], data['boleta_date'], data['client_name']))
        boleta_id = cursor.lastrowid
        for item in data['items']:
            if item['description']:
                conn.execute('INSERT INTO boleta_venta_items (boleta_id, description, quantity, price) VALUES (?, ?, ?, ?)', (boleta_id, item['description'], item['quantity'], item['price']))
        conn.commit()
        return jsonify({'success': True, 'message': 'Boleta de venta guardada con éxito.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'}), 500
    finally:
        conn.close()
    
@app.route('/get_boleta_de_venta_data', methods=['GET'])
@login_required
def get_boleta_de_venta_data():
    user_id = session['user_id']
    conn = get_db_connection()
    try:
        boleta = conn.execute('SELECT id, boleta_number, boleta_date, client_name FROM boletas_venta_data WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,)).fetchone()
        if not boleta:
            return jsonify({})
        items = conn.execute('SELECT description, quantity, price FROM boleta_venta_items WHERE boleta_id = ?', (boleta['id'],)).fetchall()
        data = {'boleta_number': boleta['boleta_number'],'boleta_date': boleta['boleta_date'],'client_name': boleta['client_name'],'items': [{'description': item['description'], 'quantity': item['quantity'], 'price': item['price']} for item in items]}
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/get_progress_data', methods=['GET'])
@login_required
def get_progress_data():
    user_id = session['user_id']
    conn = get_db_connection()

    try:
        monthly_sales = conn.execute('SELECT month, ingresos FROM dinerito_data WHERE user_id = ? ORDER BY month', (user_id,)).fetchall()
        
        top_products = conn.execute('''
            SELECT item_name, SUM(quantity) as total_sold
            FROM inventario_data 
            WHERE user_id = ?
            GROUP BY item_name
            ORDER BY total_sold DESC
            LIMIT 5
        ''', (user_id,)).fetchall()

        sales_data = {row['month']: row['ingresos'] for row in monthly_sales}
        products_data = [{'label': row['item_name'], 'value': row['total_sold']} for row in top_products]

        return jsonify({
            'monthly_sales': sales_data,
            'top_products': products_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/upload_file', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No se encontró el archivo'}), 400
    
    file = request.files['file']
    file_type = request.form.get('file_type')
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No se seleccionó ningún archivo'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        user_id = session['user_id']
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO uploaded_files (user_id, filename, file_type) VALUES (?, ?, ?)', (user_id, filename, file_type))
            conn.commit()
            return jsonify({'success': True, 'message': 'Archivo subido con éxito.'})
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'message': f'Error al guardar en la base de datos: {str(e)}'}), 500
        finally:
            conn.close()
    else:
        return jsonify({'success': False, 'message': 'Tipo de archivo o de documento no permitido'}), 400

@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/get_files_by_type/<file_type>', methods=['GET'])
@login_required
def get_files_by_type(file_type):
    user_id = session['user_id']
    conn = get_db_connection()
    files = conn.execute('SELECT filename FROM uploaded_files WHERE user_id = ? AND file_type = ? ORDER BY upload_date DESC', (user_id, file_type)).fetchall()
    conn.close()
    
    file_list = [{'filename': file['filename']} for file in files]
    return jsonify(file_list)

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    user_id = session['user_id']
    conn = get_db_connection()
    file_record = conn.execute('SELECT * FROM uploaded_files WHERE user_id = ? AND filename = ?', (user_id, filename)).fetchone()
    conn.close()

    if file_record:
        try:
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
        except FileNotFoundError:
            return "Archivo no encontrado.", 404
    else:
        return "No autorizado para descargar este archivo.", 403

@app.route('/delete_file/<filename>', methods=['DELETE'])
@login_required
def delete_file(filename):
    user_id = session['user_id']
    conn = get_db_connection()
    try:
        file_record = conn.execute('SELECT * FROM uploaded_files WHERE user_id = ? AND filename = ?', (user_id, filename)).fetchone()
        
        if file_record:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            
            conn.execute('DELETE FROM uploaded_files WHERE user_id = ? AND filename = ?', (user_id, filename))
            conn.commit()
            return jsonify({'success': True, 'message': f'Archivo "{filename}" borrado con éxito.'})
        else:
            return jsonify({'success': False, 'message': 'Archivo no encontrado o no autorizado para borrar.'}), 404
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error al borrar el archivo: {str(e)}'}), 500
    finally:
        conn.close()


@app.route('/cuenta')
@login_required
def cuenta():
    user_id = session['user_id']
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()

    if user:
        return render_template('cuenta.html', user=user)
    
    return redirect(url_for('index'))

@app.route('/save_profile', methods=['POST'])
@login_required
def save_profile():
    user_id = session['user_id']
    email = request.form.get('email', '')
    company_name = request.form.get('company_name', '')

    conn = get_db_connection()
    try:
        conn.execute('UPDATE users SET email = ?, company_name = ? WHERE id = ?', (email, company_name, user_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Perfil actualizado con éxito.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error al guardar: {str(e)}'}), 500
    finally:
        conn.close()


@app.route('/send_document_by_email', methods=['POST'])
@login_required
def send_document_by_email():
    user_id = session['user_id']
    data = request.json
    filename = data.get('filename')
    
    conn = get_db_connection()
    user = conn.execute('SELECT email FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    
    if not user or not user['email']:
        return jsonify({'success': False, 'message': 'Debes vincular un correo a tu cuenta primero.'}), 400

    if not filename:
        return jsonify({'success': False, 'message': 'No se especificó un archivo para enviar.'}), 400

    try:
        # Construye el objeto de mensaje
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = user['email']
        msg['Subject'] = f"Documento Adjunto: {filename}"

        # Cuerpo del mensaje
        body = "Hola,\n\nTe adjuntamos el archivo que solicitaste.\n\nSaludos cordiales,\nEl equipo de Cuentas Claras"
        msg.attach(MIMEText(body, 'plain'))

        # Adjunta el archivo
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(file_path, 'rb') as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename= {filename}')
        msg.attach(part)

        # Inicia la conexión con el servidor SMTP
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls() # Habilita la seguridad TLS
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)

        return jsonify({'success': True, 'message': f'Documento "{filename}" enviado con éxito a {user["email"]}.'})
    
    except FileNotFoundError:
        return jsonify({'success': False, 'message': f'Error: El archivo "{filename}" no se encontró en el servidor.'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al enviar el correo: {str(e)}'}), 500

# --- BLOQUE PRINCIPAL DE EJECUCIÓN ---
if __name__ == '__main__':
    init_db()
    app.run(debug=True)

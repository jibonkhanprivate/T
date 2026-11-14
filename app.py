import os, sqlite3, secrets
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY', secrets.token_hex(32)), DATABASE=os.environ.get('DATABASE_PATH', os.path.join(BASE,'topupers.db')), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS games(id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, image TEXT NOT NULL, description TEXT);
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES games(id), name TEXT NOT NULL, price REAL NOT NULL CHECK(price>=0), active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), product_id INTEGER NOT NULL REFERENCES products(id), player_id TEXT NOT NULL, zone_id TEXT, customer_email TEXT NOT NULL, amount REAL NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
'''

def db():
    if 'db' not in g:
        g.db=sqlite3.connect(app.config['DATABASE']);g.db.row_factory=sqlite3.Row;g.db.execute('PRAGMA foreign_keys=ON')
    return g.db

@app.teardown_appcontext
def close_db(_):
    conn=g.pop('db',None)
    if conn:conn.close()

def init_db():
    with app.app_context():
        d=db();d.executescript(SCHEMA)
        if not d.execute('SELECT 1 FROM games').fetchone():
            games=[('Mobile Legends: Bang Bang','mobile-legends','mlbb.jpg','Diamonds and weekly passes'),('Free Fire','free-fire','placeholder.svg','Diamonds for Free Fire'),('PUBG Mobile','pubg-mobile','placeholder.svg','UC top-ups'),('Clash of Clans','clash-of-clans','clash.jpg','Gems and bundles')]
            d.executemany('INSERT INTO games(name,slug,image,description) VALUES(?,?,?,?)',games)
            for game_id,items in enumerate([ [('86 Diamonds',130),('172 Diamonds',255),('257 Diamonds',380),('Weekly Diamond Pass',220)], [('100 Diamonds',95),('310 Diamonds',285),('520 Diamonds',470)], [('60 UC',130),('325 UC',640),('660 UC',1250)], [('80 Gems',120),('500 Gems',580)] ],1):
                d.executemany('INSERT INTO products(game_id,name,price) VALUES(?,?,?)',[(game_id,n,p) for n,p in items])
        d.commit()

def current_user():
    return db().execute('SELECT id,name,email FROM users WHERE id=?',(session['user_id'],)).fetchone() if session.get('user_id') else None

def json_error(message,status=400):return jsonify(error=message),status

def csrf_check():
    if request.headers.get('X-CSRF-Token') != session.get('csrf_token'):return json_error('Invalid security token',403)

def login_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if not current_user():return json_error('Please sign in first',401)
        return fn(*a,**kw)
    return wrapper

@app.before_request
def ensure_token():
    if 'csrf_token' not in session:session['csrf_token']=secrets.token_urlsafe(32)

@app.get('/')
def index():return render_template('index.html',csrf_token=session['csrf_token'])

@app.get('/api/games')
def games():
    return jsonify([dict(r) for r in db().execute('SELECT * FROM games ORDER BY id')])

@app.get('/api/games/<slug>/products')
def products(slug):
    game=db().execute('SELECT id FROM games WHERE slug=?',(slug,)).fetchone()
    if not game:return json_error('Game not found',404)
    return jsonify([dict(r) for r in db().execute('SELECT id,name,price FROM products WHERE game_id=? AND active=1 ORDER BY price',(game['id'],))])

@app.get('/api/me')
def me():
    u=current_user();return jsonify(user=dict(u) if u else None)

@app.post('/api/register')
def register():
    err=csrf_check()
    if err:return err
    data=request.get_json(silent=True) or {};name=str(data.get('name','')).strip();email=str(data.get('email','')).strip().lower();password=str(data.get('password',''))
    if not name or len(name)>100 or '@' not in email or len(email)>254 or len(password)<8:return json_error('Enter a name, valid email and password of at least 8 characters')
    try:
        cur=db().execute('INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)',(name,email,generate_password_hash(password),datetime.now(timezone.utc).isoformat()));db().commit()
    except sqlite3.IntegrityError:return json_error('Email already registered',409)
    session.clear();session['user_id']=cur.lastrowid;session['csrf_token']=secrets.token_urlsafe(32)
    return jsonify(user=dict(current_user()),csrf_token=session['csrf_token']),201

@app.post('/api/login')
def login():
    err=csrf_check()
    if err:return err
    data=request.get_json(silent=True) or {};email=str(data.get('email','')).strip().lower()
    u=db().execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
    if not u or not check_password_hash(u['password_hash'],str(data.get('password',''))):return json_error('Invalid credentials',401)
    session.clear();session['user_id']=u['id'];session['csrf_token']=secrets.token_urlsafe(32)
    return jsonify(user=dict(current_user()),csrf_token=session['csrf_token'])

@app.post('/api/logout')
def logout():
    err=csrf_check()
    if err:return err
    session.clear();session['csrf_token']=secrets.token_urlsafe(32)
    return jsonify(ok=True,csrf_token=session['csrf_token'])

@app.post('/api/orders')
def create_order():
    err=csrf_check()
    if err:return err
    data=request.get_json(silent=True) or {}
    try:product_id=int(data.get('product_id'))
    except (ValueError,TypeError):return json_error('Select a package')
    player=str(data.get('player_id','')).strip();zone=str(data.get('zone_id','')).strip();email=str(data.get('email','')).strip().lower()
    if not (2<=len(player)<=80) or len(zone)>40 or not (3<=len(email)<=254) or '@' not in email:return json_error('Enter a valid player ID and email')
    p=db().execute('SELECT id,price FROM products WHERE id=? AND active=1',(product_id,)).fetchone()
    if not p:return json_error('Package unavailable',404)
    u=current_user()
    cur=db().execute('INSERT INTO orders(user_id,product_id,player_id,zone_id,customer_email,amount,status,created_at) VALUES(?,?,?,?,?,?,?,?)',(u['id'] if u else None,p['id'],player,zone,email,p['price'],'pending',datetime.now(timezone.utc).isoformat()))
    db().commit()
    return jsonify(order_id=cur.lastrowid,status='pending',amount=p['price'],message='Order request saved. No payment has been collected or top-up delivered.'),201

@app.get('/api/orders')
@login_required
def my_orders():
    return jsonify([dict(r) for r in db().execute('''SELECT o.id,o.player_id,o.zone_id,o.amount,o.status,o.created_at,p.name AS package,g.name AS game FROM orders o JOIN products p ON p.id=o.product_id JOIN games g ON g.id=p.game_id WHERE o.user_id=? ORDER BY o.id DESC''',(session['user_id'],))])

if __name__=='__main__':
    init_db();app.run(debug=os.environ.get('FLASK_DEBUG')=='1',host='127.0.0.1',port=int(os.environ.get('PORT','5000')))

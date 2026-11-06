import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'bgc-maintenance-secret-key-2026')
# Supabase/Postgres connection string via DATABASE_URL; falls back to local SQLite for dev
database_url = os.environ.get('DATABASE_URL', 'sqlite:///maintenance.db')
# Supabase provides postgres://; use psycopg (v3) driver for SQLAlchemy
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ---------- نماذج قاعدة البيانات (Database Models) ----------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_code = db.Column(db.String(50), unique=True, nullable=False)
    asset_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), default='الات ومعدات')
    location = db.Column(db.String(50), default='نوربيتكو')
    status = db.Column(db.String(20), default='يعمل بحالة جيدة')

class MaintenanceLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_code = db.Column(db.String(50), nullable=False)
    asset_name = db.Column(db.String(100), nullable=False)
    maint_type = db.Column(db.String(50), nullable=False) # وقائية، طارئة، عمرة...
    start_date = db.Column(db.String(20), nullable=False)
    next_date = db.Column(db.String(20))
    action_taken = db.Column(db.Text)
    spare_parts = db.Column(db.String(200))
    technician = db.Column(db.String(100))
    cost = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(50), default='تمت الصيانة') # تمت، جاري العمل، مؤجل

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------- المسارات والصفحات (Routes) ----------

@app.route('/')
@login_required
def dashboard():
    total_assets = Asset.query.count()
    total_logs = MaintenanceLog.query.count()
    total_cost = db.session.query(db.func.sum(MaintenanceLog.cost)).scalar() or 0.0
    pending_maint = MaintenanceLog.query.filter(MaintenanceLog.status != 'تمت الصيانة').count()
    recent_logs = MaintenanceLog.query.order_by(MaintenanceLog.id.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                           total_assets=total_assets, 
                           total_logs=total_logs, 
                           total_cost=total_cost, 
                           pending_maint=pending_maint,
                           recent_logs=recent_logs)

# --- إدارة الأصول (Assets) ---
@app.route('/assets', methods=['GET', 'POST'])
@login_required
def assets():
    if request.method == 'POST':
        code = request.form.get('asset_code')
        name = request.form.get('asset_name')
        category = request.form.get('category')
        location = request.form.get('location')
        status = request.form.get('status')

        if Asset.query.filter_by(asset_code=code).first():
            flash('كود الأصل مسجل مسبقاً!', 'danger')
        else:
            new_asset = Asset(asset_code=code, asset_name=name, category=category, location=location, status=status)
            db.session.add(new_asset)
            db.session.commit()
            flash('تم إضافة الأصل بنجاح!', 'success')
        return redirect(url_for('assets'))

    all_assets = Asset.query.order_by(Asset.id.desc()).all()
    return render_template('assets.html', assets=all_assets)

@app.route('/assets/delete/<int:id>')
@login_required
def delete_asset(id):
    asset = Asset.query.get_or_404(id)
    db.session.delete(asset)
    db.session.commit()
    flash('تم حذف الأصل بنجاح!', 'warning')
    return redirect(url_for('assets'))

# --- إدارة الصيانة (Maintenance) ---
@app.route('/maintenance', methods=['GET', 'POST'])
@login_required
def maintenance():
    if request.method == 'POST':
        new_log = MaintenanceLog(
            asset_code=request.form.get('asset_code'),
            asset_name=request.form.get('asset_name'),
            maint_type=request.form.get('maint_type'),
            start_date=request.form.get('start_date'),
            next_date=request.form.get('next_date'),
            action_taken=request.form.get('action_taken'),
            spare_parts=request.form.get('spare_parts'),
            technician=request.form.get('technician'),
            cost=float(request.form.get('cost') or 0),
            status=request.form.get('status')
        )
        db.session.add(new_log)
        db.session.commit()
        flash('تم تسجيل أمر الصيانة بنجاح!', 'success')
        return redirect(url_for('maintenance'))

    logs = MaintenanceLog.query.order_by(MaintenanceLog.id.desc()).all()
    assets_list = Asset.query.all()
    return render_template('maintenance.html', logs=logs, assets=assets_list)

@app.route('/maintenance/delete/<int:id>')
@login_required
def delete_maintenance(id):
    log = MaintenanceLog.query.get_or_404(id)
    db.session.delete(log)
    db.session.commit()
    flash('تم حذف سجل الصيانة!', 'warning')
    return redirect(url_for('maintenance'))

# --- تسجيل الدخول والخروج ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# تهيئة قاعدة البيانات ومستخدم افتراضي عند البدء
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin123'))
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)

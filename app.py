import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, flash, abort
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
    role = db.Column(db.String(20), default='technician')  # manager, technician, management

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_code = db.Column(db.String(50), unique=True, nullable=False)
    asset_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), default='الات ومعدات')
    location = db.Column(db.String(50), default='Norpetco')
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
    assigned_to = db.Column(db.Integer)  # user id of technician
    cost = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(50), default='مفتوح') # مفتوح، جاري العمل، تمت الصيانة، مؤجل
    fault_report_id = db.Column(db.Integer)

class FaultReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_code = db.Column(db.String(50), nullable=False)
    asset_name = db.Column(db.String(100))
    description = db.Column(db.Text, nullable=False)
    reporter_name = db.Column(db.String(100))
    created_at = db.Column(db.String(20))
    status = db.Column(db.String(30), default='جديد')  # جديد، تم تحويله لتيكيت
    ticket_id = db.Column(db.Integer)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def role_required(*roles):
    from functools import wraps
    from flask import abort
    def decorator(f):
        @wraps(f)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator

# ---------- المسارات والصفحات (Routes) ----------

@app.route('/')
@login_required
def dashboard():
    if current_user.role == 'technician':
        return redirect(url_for('tickets'))
    total_assets = Asset.query.count()
    faulty_assets = Asset.query.filter(Asset.status != 'يعمل بحالة جيدة').count()
    new_reports = FaultReport.query.filter_by(status='جديد').count()
    total_logs = MaintenanceLog.query.count()
    total_cost = db.session.query(db.func.sum(MaintenanceLog.cost)).scalar() or 0.0
    pending_maint = MaintenanceLog.query.filter(MaintenanceLog.status != 'تمت الصيانة').count()
    recent_logs = MaintenanceLog.query.order_by(MaintenanceLog.id.desc()).limit(5).all()
    # periodic maintenance within next 7 days
    from datetime import date, timedelta
    today = date.today()
    week_end = today + timedelta(days=7)
    weekly_periodic = []
    for log in MaintenanceLog.query.filter_by(maint_type='دوريات').all():
        try:
            d = datetime.strptime(log.next_date or log.start_date, '%Y-%m-%d').date()
            if today <= d <= week_end:
                weekly_periodic.append(log)
        except Exception:
            pass
    recent_reports = FaultReport.query.order_by(FaultReport.id.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                           total_assets=total_assets, 
                           faulty_assets=faulty_assets,
                           new_reports=new_reports,
                           total_logs=total_logs, 
                           total_cost=total_cost, 
                           pending_maint=pending_maint,
                           recent_logs=recent_logs,
                           weekly_periodic=weekly_periodic,
                           recent_reports=recent_reports)

# --- إدارة الأصول (Assets) ---
@app.route('/assets', methods=['GET', 'POST'])
@role_required('manager')
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
@role_required('manager')
def delete_asset(id):
    asset = Asset.query.get_or_404(id)
    db.session.delete(asset)
    db.session.commit()
    flash('تم حذف الأصل بنجاح!', 'warning')
    return redirect(url_for('assets'))

# --- إدارة الصيانة (Maintenance) ---
@app.route('/maintenance', methods=['GET', 'POST'])
@role_required('manager')
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

@app.route('/maintenance/edit/<int:id>', methods=['GET', 'POST'])
@role_required('manager')
def edit_maintenance(id):
    log = MaintenanceLog.query.get_or_404(id)
    if request.method == 'POST':
        log.asset_code = request.form.get('asset_code')
        log.asset_name = request.form.get('asset_name')
        log.maint_type = request.form.get('maint_type')
        log.start_date = request.form.get('start_date')
        log.next_date = request.form.get('next_date')
        log.action_taken = request.form.get('action_taken')
        log.spare_parts = request.form.get('spare_parts')
        log.technician = request.form.get('technician')
        log.cost = float(request.form.get('cost') or 0)
        log.status = request.form.get('status')
        db.session.commit()
        flash('تم تحديث سجل الصيانة بنجاح!', 'success')
        return redirect(url_for('maintenance'))
    assets_list = Asset.query.all()
    return render_template('edit_maintenance.html', log=log, assets=assets_list)

@app.route('/maintenance/delete/<int:id>')
@role_required('manager')
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
            if user.role == 'technician':
                return redirect(url_for('tickets'))
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
        admin = User(username='admin', password=generate_password_hash('admin123'), role='manager')
        db.session.add(admin)
    if not User.query.filter_by(username='tech').first():
        tech = User(username='tech', password=generate_password_hash('tech123'), role='technician')
        db.session.add(tech)
    if not User.query.filter_by(username='mgmt').first():
        mgmt = User(username='mgmt', password=generate_password_hash('mgmt123'), role='management')
        db.session.add(mgmt)
    db.session.commit()
    # Auto-seed equipment/tools list into assets table if empty
    try:
        from seed_assets import seed as seed_assets
        if Asset.query.count() == 0:
            seed_assets(db, Asset)
    except Exception as e:
        print('Asset seeding skipped:', e)

# --- تبليغ عن عطل (عام - بدون تسجيل دخول) ---
@app.route('/report', methods=['GET', 'POST'])
def report_fault():
    if request.method == 'POST':
        code = request.form.get('asset_code')
        asset = Asset.query.filter_by(asset_code=code).first()
        name = asset.asset_name if asset else request.form.get('asset_name')
        rep = FaultReport(
            asset_code=code,
            asset_name=name,
            description=request.form.get('description'),
            reporter_name=request.form.get('reporter_name'),
            created_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
            status='جديد'
        )
        db.session.add(rep)
        db.session.commit()
        flash('تم إرسال البلاغ بنجاح! سيقوم فريق الصيانة بمراجعته.', 'success')
        return redirect(url_for('report_fault'))
    assets_list = Asset.query.all()
    return render_template('report_fault.html', assets=assets_list)

# --- قائمة البلاغات (إدارة + مدير صيانة) ---
@app.route('/reports')
@role_required('manager', 'management')
def reports():
    all_reports = FaultReport.query.order_by(FaultReport.id.desc()).all()
    return render_template('reports.html', reports=all_reports)

# --- تحويل بلاغ إلى تيكيت (مدير صيانة) ---
@app.route('/reports/convert/<int:id>')
@role_required('manager')
def convert_report(id):
    rep = FaultReport.query.get_or_404(id)
    if rep.status == 'تم تحويله لتيكيت':
        flash('هذا البلاغ تم تحويله مسبقاً', 'warning')
        return redirect(url_for('reports'))
    log = MaintenanceLog(
        asset_code=rep.asset_code,
        asset_name=rep.asset_name or '',
        maint_type='طارئة',
        start_date=datetime.now().strftime('%Y-%m-%d'),
        action_taken=rep.description,
        status='مفتوح',
        fault_report_id=rep.id
    )
    db.session.add(log)
    db.session.commit()
    rep.status = 'تم تحويله لتيكيت'
    rep.ticket_id = log.id
    db.session.commit()
    flash('تم تحويل البلاغ إلى تيكيت صيانة', 'success')
    return redirect(url_for('reports'))

# --- تيكيتات فني الصيانة ---
@app.route('/tickets')
@login_required
def tickets():
    if current_user.role == 'management':
        return redirect(url_for('dashboard'))
    open_tickets = MaintenanceLog.query.filter(MaintenanceLog.status != 'تمت الصيانة').order_by(MaintenanceLog.id.desc()).all()
    return render_template('tickets.html', tickets=open_tickets)

@app.route('/tickets/close/<int:id>', methods=['GET', 'POST'])
@login_required
def close_ticket(id):
    if current_user.role == 'management':
        abort(403)
    log = MaintenanceLog.query.get_or_404(id)
    if request.method == 'POST':
        log.action_taken = request.form.get('action_taken')
        log.spare_parts = request.form.get('spare_parts')
        log.technician = request.form.get('technician') or current_user.username
        log.cost = float(request.form.get('cost') or 0)
        log.status = 'تمت الصيانة'
        db.session.commit()
        flash('تم إغلاق التذكرة وتسجيل الصيانة', 'success')
        return redirect(url_for('tickets'))
    return render_template('close_ticket.html', log=log)

if __name__ == '__main__':
    app.run(debug=True)

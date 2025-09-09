from flask import Flask, render_template_string, request, redirect, url_for, flash, session
from datetime import datetime
import json, os, functools

app = Flask(__name__)
app.secret_key = 'secret-key-change-this'

LEAVE_TYPES = ["Vacation", "Sick", "Maternity", "specific"]
DEFAULT_BALANCES = {"Vacation": 15, "Sick": 10, "Maternity": 90, "specific": 45}
DATA_FILE = 'data.json'

class Employee:
    def __init__(self, emp_id, name, password='password', contact='', department='', leave_balances=None, leave_requests=None):
        self.emp_id = emp_id
        self.name = name
        self.password = password
        self.contact = contact
        self.department = department
        self.leave_balances = leave_balances or {lt: DEFAULT_BALANCES[lt] for lt in LEAVE_TYPES}
        self.leave_requests = leave_requests or []

    def apply_leave(self, leave_type, start_date, end_date):
        days = (end_date - start_date).days + 1
        if start_date.date() < datetime.now().date():
            return False, "Start date cannot be in the past."
        if leave_type not in LEAVE_TYPES:
            return False, f"Invalid leave type: {leave_type}."
        if days > self.leave_balances.get(leave_type, 0):
            return False, f"Insufficient {leave_type} leave balance."
        for req in self.leave_requests:
            if req['status'] in ('Pending', 'Approved'):
                es = datetime.strptime(req['start_date'], '%Y-%m-%d')
                ee = datetime.strptime(req['end_date'], '%Y-%m-%d')
                if start_date <= ee and end_date >= es:
                    return False, "Dates overlap with an existing request."
        self.leave_requests.append({
            "leave_type": leave_type,
            "start_date": start_date.strftime('%Y-%m-%d'),
            "end_date": end_date.strftime('%Y-%m-%d'),
            "days": days,
            "status": "Pending",
            "deducted": False
        })
        return True, f"{leave_type} leave for {days} day(s) submitted."

    def to_dict(self):
        return {
            'emp_id': self.emp_id,
            'name': self.name,
            'password': self.password,
            'contact': self.contact,
            'department': self.department,
            'leave_balances': self.leave_balances,
            'leave_requests': self.leave_requests
        }

employees = {}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            for eid, ed in data.items():
                employees[eid] = Employee(
                    ed['emp_id'], ed['name'], ed.get('password', 'password'),
                    ed.get('contact', ''), ed.get('department', ''),
                    ed.get('leave_balances', {lt: DEFAULT_BALANCES[lt] for lt in LEAVE_TYPES}),
                    ed.get('leave_requests', [])
                )

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({eid: emp.to_dict() for eid, emp in employees.items()}, f, indent=4)

load_data()

def employee_login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'employee_id' not in session:
            flash("Please log in as employee first.")
            return redirect(url_for('employee_login'))
        return view(**kwargs)
    return wrapped_view

base_template = """
<!DOCTYPE html>
<html>
<head>
  <title>Leave Management System</title>
  <style>
    body {
      font-family: Arial;
      margin:0; padding:0;
      min-height:100vh;
      background: #f4f4f4;
      {% if request.endpoint == 'index' %}
       background: url('{{ url_for('static', filename='img/successful-employees.png') }}') no-repeat center center fixed;
            background-size: cover;
      {% endif %}
    }
    .container {
      max-width:900px;
      margin:30px auto;
      background:rgba(255,255,255,0.95);
      padding:20px;
      border-radius:8px;
    }
    ul.nav { list-style:none; padding:0; text-align:center; margin-bottom:20px; }
    ul.nav li { display:inline; margin:0 10px; }
    ul.nav a { color:#007BFF; text-decoration:none; font-weight:bold; }
    .flash {
      background-color: #f8d7da;
      padding: 15px;
      border-radius: 5px;
      color: #721c24;
      border: 1px solid #f5c6cb;
      margin: 10px 0;
      text-align:center;
    }
    table { width:100%; border-collapse:collapse; margin-top:20px; }
    th,td { padding:8px; border:1px solid #ddd; text-align:left; }
    th { background:#efefef; }
    input, select, button { width:100%; padding:8px; margin:5px 0; }
    button { background:#007BFF; color:#fff; border:none; cursor:pointer; }
    button:hover { background:#0056b3; }
    .action-form { display:inline; }
  </style>
</head>
<body>
  <div class="container">
    <h2>Leave Management System</h2>
    <ul class="nav">
      <li><a href="{{ url_for('index') }}">Home</a></li>
      {% if session.get('employee_id') %}
        <li><a href="{{ url_for('apply_leave') }}">Apply Leave</a></li>
        <li><a href="{{ url_for('view_requests') }}">My Requests</a></li>
        <li><a href="{{ url_for('change_password') }}">Change Password</a></li>
        <li><a href="{{ url_for('employee_logout') }}">Logout ({{ employees[session.get('employee_id')].name }})</a></li>
      {% else %}
        <li><a href="{{ url_for('employee_login') }}">Employee Login</a></li>
      {% endif %}
      {% if session.get('admin') %}
        <li><a href="{{ url_for('dashboard') }}">Dashboard</a></li>
        <li><a href="{{ url_for('admin_requests') }}">Admin Requests</a></li>
        <li><a href="{{ url_for('admin_employees') }}">Employees</a></li>
        <li><a href="{{ url_for('admin_logout') }}">Logout (Admin)</a></li>
      {% else %}
        <li><a href="{{ url_for('admin_login') }}">Admin Login</a></li>
      {% endif %}
    </ul>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <div class="flash"><strong>{{ messages[0] }}</strong></div>
      {% endif %}
    {% endwith %}
    {{ content|safe }}
  </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(base_template, content="<h3>Welcome to the Leave Management System</h3>", employees=employees)

@app.route('/employee/login', methods=['GET', 'POST'])
def employee_login():
    if request.method == 'POST':
        emp_id = request.form['emp_id']
        password = request.form['password']
        emp = employees.get(emp_id)
        if emp and emp.password == password:
            session.clear()
            session['employee_id'] = emp_id
            flash(f"Welcome {emp.name}!")
            return redirect(url_for('apply_leave'))
        else:
            flash("Invalid employee ID or password.")
            return redirect(url_for('employee_login'))
    return render_template_string(base_template, content="""
      <h3>Employee Login</h3>
      <form method="post">
        Employee ID:<input name="emp_id" required>
        Password:<input type="password" name="password" required>
        <button type="submit">Login</button>
      </form>
    """, employees=employees)

@app.route('/employee/logout')
def employee_logout():
    session.pop('employee_id', None)
    flash("Logged out successfully.")
    return redirect(url_for('index'))

@app.route('/employee/change_password', methods=['GET', 'POST'])
@employee_login_required
def change_password():
    emp = employees.get(session['employee_id'])
    if request.method == 'POST':
        old = request.form['old_password']
        new = request.form['new_password']
        confirm = request.form['confirm_password']
        if old != emp.password:
            flash("Old password is incorrect.")
        elif not new or new != confirm:
            flash("New passwords do not match or are empty.")
        else:
            emp.password = new
            save_data()
            flash("Password changed successfully.")
            return redirect(url_for('index'))
    return render_template_string(base_template, content="""
      <h3>Change Password</h3>
      <form method="post">
        Old Password: <input type="password" name="old_password" required>
        New Password: <input type="password" name="new_password" required>
        Confirm New Password: <input type="password" name="confirm_password" required>
        <button type="submit">Update Password</button>
      </form>
    """, employees=employees)


@app.route('/apply', methods=['GET', 'POST'])
@employee_login_required
def apply_leave():
    emp = employees.get(session['employee_id'])
    if request.method == 'POST':
        lt = request.form['leave_type']
        try:
            start = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
            end = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
        except Exception:
            flash("Invalid dates.")
            return redirect(url_for('apply_leave'))
        if start > end:
            flash("Start date must be before end date.")
            return redirect(url_for('apply_leave'))
        ok, msg = emp.apply_leave(lt, start, end)
        if ok:
            save_data()
        flash(msg)
        return redirect(url_for('apply_leave'))
    opts = ''.join(f'<option>{lt}</option>' for lt in LEAVE_TYPES)
    return render_template_string(base_template, content=f"""
      <h3>Apply Leave</h3>
      <p>Logged in as: <strong>{emp.name}</strong> (ID: {emp.emp_id})</p>
      <form method="post">
        Leave Type: <select name="leave_type">{opts}</select>
        Start Date: <input type="date" name="start_date" required>
        End Date: <input type="date" name="end_date" required>
        <button type="submit">Apply</button>
      </form>
    """, employees=employees)


@app.route('/balance')
@employee_login_required
def view_balance():
    emp = employees.get(session['employee_id'])
    bal = ''.join(f'<li>{lt}: {emp.leave_balances[lt]}</li>' for lt in LEAVE_TYPES)
    return render_template_string(base_template, content=f"<h3>{emp.name}'s Leave Balances</h3><ul>{bal}</ul>", employees=employees)


@app.route('/requests')
@employee_login_required
def view_requests():
    emp = employees.get(session['employee_id'])
    if not emp.leave_requests:
        content = f"<p>{emp.name} has no leave requests.</p>"
    else:
        items = "".join(f"<li>{r['leave_type']} {r['start_date']} → {r['end_date']} – Status: {r['status']}</li>" for r in emp.leave_requests)
        content = f"<h3>{emp.name}'s Leave Requests</h3><ul>{items}</ul>"
    return render_template_string(base_template, content=content, employees=employees)


# Admin routes unchanged except they pass employees dict for navbar rendering

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['password'] == 'adminpass':
            session.clear()
            session['admin'] = True
            flash("Logged in as Admin.")
            return redirect(url_for('dashboard'))
        flash("Incorrect password.")
        return redirect(url_for('admin_login'))
    return render_template_string(base_template, content="""
      <h3>Admin Login</h3>
      <form method="post">
        Password:<input type="password" name="password" required>
        <button type="submit">Login</button>
      </form>
    """, employees=employees)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash("Admin logged out.")
    return redirect(url_for('index'))


@app.route('/admin/requests', methods=['GET', 'POST'])
def admin_requests():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        eid = request.form['emp_id']
        idx = int(request.form['index'])
        act = request.form['action']
        emp = employees.get(eid)
        if emp:
            req = emp.leave_requests[idx]
            prev = req['status']
            req['status'] = act
            if act == 'Approved' and not req['deducted']:
                emp.leave_balances[req['leave_type']] -= req['days']
                req['deducted'] = True
            elif prev == 'Approved' and req['deducted'] and act != 'Approved':
                emp.leave_balances[req['leave_type']] += req['days']
                req['deducted'] = False
            save_data()
            flash("Request updated.")
        return redirect(url_for('admin_requests'))
    rows = ""
    for emp in employees.values():
        for i, r in enumerate(emp.leave_requests):
            rows += f"<tr><td>{emp.emp_id}</td><td>{emp.name}</td><td>{r['leave_type']}</td><td>{r['start_date']}</td><td>{r['end_date']}</td><td>{r['days']}</td><td>{r['status']}</td><td><form method='post' class='action-form'><input type='hidden' name='emp_id' value='{emp.emp_id}'><input type='hidden' name='index' value='{i}'><button name='action' value='Approved'>Approve</button><button name='action' value='Rejected'>Reject</button></form></td></tr>"
    table_html = f"<h3>Admin: Manage Requests</h3><a href='{url_for('add_employee')}'><button>Add Employee</button></a><table><tr><th>ID</th><th>Name</th><th>Type</th><th>Start</th><th>End</th><th>Days</th><th>Status</th><th>Actions</th></tr>{rows}</table>"
    return render_template_string(base_template, content=table_html, employees=employees)


@app.route('/admin/employees', methods=['GET', 'POST'])
def admin_employees():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    q = request.form.get('query', '').lower() if request.method == 'POST' else ''
    fl = [e for e in employees.values() if q in e.emp_id.lower() or q in e.name.lower() or q in e.department.lower()] if q else employees.values()
    rows = ""
    for e in fl:
        rows += f"<tr><td>{e.emp_id}</td><td>{e.name}</td><td>{e.contact}</td><td>{e.department}</td><td><a href='{url_for('edit_employee', emp_id=e.emp_id)}'><button>Edit</button></a><form method='post' action='{url_for('delete_employee', emp_id=e.emp_id)}' class='action-form' onsubmit='return confirm(\"Delete {e.name}?\");'><button type='submit'>Delete</button></form></td></tr>"
    tbl_html = f"<h3>Admin: Employees</h3><form method='post'><input name='query' placeholder='Search by ID, name, dept' value='{q}'><button type='submit'>Search</button></form><table><tr><th>ID</th><th>Name</th><th>Contact</th><th>Department</th><th>Actions</th></tr>{rows}</table>"
    return render_template_string(base_template, content=tbl_html, employees=employees)


@app.route('/admin/edit/<emp_id>', methods=['GET', 'POST'])
def edit_employee(emp_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    emp = employees.get(emp_id)
    if not emp:
        flash("Employee not found.")
        return redirect(url_for('admin_employees'))
    if request.method == 'POST':
        nm = request.form['name'].strip()
        ct = request.form['contact'].strip()
        dept = request.form['department'].strip()
        pwd = request.form.get('password', '').strip()
        if not all([nm, ct, dept]):
            flash("All fields except password are required.")
        else:
            emp.name, emp.contact, emp.department = nm, ct, dept
            if pwd:
                emp.password = pwd
            save_data()
            flash("Employee updated.")
            return redirect(url_for('admin_employees'))
    return render_template_string(base_template, content=f"""
      <h3>Edit Employee {emp.emp_id}</h3>
      <form method="post">
        Name: <input name="name" value="{emp.name}" required>
        Contact: <input name="contact" value="{emp.contact}" required>
        Department: <input name="department" value="{emp.department}" required>
        Password (leave blank to keep current): <input type="password" name="password">
        <button type="submit">Update</button>
      </form><br>
      <a href="{url_for('admin_employees')}"><button>Back</button></a>
    """, employees=employees)


@app.route('/admin/delete/<emp_id>', methods=['POST'])
def delete_employee(emp_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    if emp_id in employees:
        del employees[emp_id]
        save_data()
        flash("Employee deleted.")
    else:
        flash("Employee not found.")
    return redirect(url_for('admin_employees'))


@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    totals = {lt: 0 for lt in LEAVE_TYPES}
    approved = {lt: 0 for lt in LEAVE_TYPES}
    for emp in employees.values():
        for r in emp.leave_requests:
            totals[r['leave_type']] += 1
            if r['status'] == 'Approved':
                approved[r['leave_type']] += 1
    chart_html = render_template_string("""
      <h3>Leave Dashboard</h3>
      <canvas id="chart" style="max-width:600px"></canvas>
      <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
      <script>
        const labels = {{ labels|tojson }};
        const totalData = {{ totals|tojson }};
        const approvedData = {{ approved|tojson }};
        new Chart(document.getElementById('chart'), {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [
              { label: 'All Requests', data: totalData, backgroundColor: 'rgba(54,162,235,0.6)' },
              { label: 'Approved', data: approvedData, backgroundColor: 'rgba(75,192,192,0.6)' }
            ]
          },
          options: { scales: { y: { beginAtZero: true } } }
        });
      </script>
    """, labels=LEAVE_TYPES, totals=list(totals.values()), approved=list(approved.values()))
    return render_template_string(base_template, content=chart_html, employees=employees)


@app.route('/add', methods=['GET', 'POST'])
def add_employee():
    # Only admin can add employees
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        eid = request.form['emp_id'].strip()
        name = request.form['name'].strip()
        contact = request.form['contact'].strip()
        dept = request.form['department'].strip()
        password = request.form['password'].strip() or 'password'  # default password if none entered
        if not all([eid, name, contact, dept, password]):
            flash("All fields required.")
        elif eid in employees:
            flash("Employee ID exists.")
        else:
            employees[eid] = Employee(eid, name, password, contact, dept)
            save_data()
            flash(f"Added {name} with default password.")
        return redirect(url_for('add_employee'))
    return render_template_string(base_template, content="""
      <h3>Add Employee</h3>
      <form method="post">
        Employee ID: <input name="emp_id" required>
        Name: <input name="name" required>
        Contact: <input name="contact" required>
        Department: <input name="department" required>
        Password (default 'password'): <input type="text" name="password">
        <button type="submit">Add</button>
      </form>
    """, employees=employees)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
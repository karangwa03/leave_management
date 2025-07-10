from flask import Flask, render_template_string, request, redirect, url_for, flash, session
from datetime import datetime
import json
import os

app = Flask(__name__)
app.secret_key = 'secret-key'

LEAVE_TYPES = ["Vacation", "Sick", "Maternity"]
DEFAULT_BALANCES = {"Vacation": 15, "Sick": 10, "Maternity": 90}
DATA_FILE = 'data.json'

class Employee:
    def __init__(self, emp_id, name, contact='', department='', leave_balances=None, leave_requests=None):
        self.emp_id = emp_id
        self.name = name
        self.contact = contact
        self.department = department
        self.leave_balances = leave_balances or {lt: DEFAULT_BALANCES[lt] for lt in LEAVE_TYPES}
        self.leave_requests = leave_requests or []

    def apply_leave(self, leave_type, start_date, end_date):
        days = (end_date - start_date).days + 1
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
                    emp_id=ed['emp_id'],
                    name=ed['name'],
                    contact=ed.get('contact', ''),
                    department=ed.get('department', ''),
                    leave_balances=ed['leave_balances'],
                    leave_requests=ed['leave_requests']
                )

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({eid: emp.to_dict() for eid, emp in employees.items()}, f, indent=4)

load_data()

base_template = """
<!DOCTYPE html>
<html><head><title>Leave Management System</title><style>
body{font-family:Arial;margin:0;padding:0;
{% if request.endpoint=='index' %}
background:url('{{ url_for('static', filename='img/successful-employees.png') }}')center/cover fixed;
{% else %}
background:#f4f4f4;
{% endif %}
min-height:100vh}
.container{padding:20px;max-width:800px;margin:50px auto;background:rgba(255,255,255,.95);border-radius:10px}
h2,h3{color:#333}ul.nav{list-style:none;padding:0;margin-bottom:20px;text-align:center}
ul.nav li{display:inline;margin:0 10px}ul.nav a{color:#007BFF;text-decoration:none;font-weight:bold}
ul.nav a:hover{text-decoration:underline}.flash{background:#ffdddd;padding:10px;border:1px solid #d00;color:#900;margin-bottom:20px}
table{width:100%;border-collapse:collapse;margin-top:20px;background:white}
th,td{border:1px solid #ddd;padding:10px;text-align:left}th{background:#f0f0f0}
input,select,button{width:100%;padding:8px;margin:5px 0;box-sizing:border-box}
button{background:#007BFF;color:#fff;border:none;cursor:pointer}
button:hover{background:#0056b3}.action-form{display:inline}
</style></head><body><div class="container">
<h2>Leave Management System</h2><ul class="nav">
<li><a href="{{ url_for('index') }}">Home</a></li>
<li><a href="{{ url_for('apply_leave') }}">Apply Leave</a></li>
<li><a href="{{ url_for('view_balance') }}">Check Balance</a></li>
<li><a href="{{ url_for('view_requests') }}">My Requests</a></li>
{% if session.get('admin') %}
<li><a href="{{ url_for('admin_requests') }}">Admin Panel</a></li>
<li><a href="{{ url_for('admin_employees') }}">Employees List</a></li>
<li><a href="{{ url_for('admin_logout') }}">Logout</a></li>
{% else %}
<li><a href="{{ url_for('admin_login') }}">Admin Login</a></li>
{% endif %}
</ul>{% with messages = get_flashed_messages() %}
{% if messages %}<div class="flash">{{ messages[0] }}</div>{% endif %}{% endwith %}
{{ content|safe }}
</div></body></html>
"""

@app.route('/')
def index():
    return render_template_string(base_template, content="<p>Welcome to the Leave Management System.</p>")

@app.route('/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        emp_id = request.form['emp_id'].strip()
        name = request.form['name'].strip()
        contact = request.form['contact'].strip()
        department = request.form['department'].strip()
        if not emp_id or not name or not contact or not department:
            flash("All fields required.")
        elif emp_id in employees:
            flash("Employee already exists.")
        else:
            employees[emp_id] = Employee(emp_id, name, contact, department)
            save_data()
            flash(f"Employee {name} added.")
        return redirect(url_for('add_employee'))
    return render_template_string(base_template, content="""
      <h3>Add Employee</h3>
      <form method="post">
        Employee ID: <input name="emp_id" required>
        Name: <input name="name" required>
        Contact: <input name="contact" required>
        Department: <input name="department" required>
        <button type="submit">Add</button>
      </form>
    """)

@app.route('/apply', methods=['GET', 'POST'])
def apply_leave():
    if request.method == 'POST':
        emp_id = request.form['emp_id']
        lt = request.form['leave_type']
        try:
            start = datetime.strptime(request.form['start_date'],'%Y-%m-%d')
            end = datetime.strptime(request.form['end_date'],'%Y-%m-%d')
        except ValueError:
            flash("Invalid date format.")
            return redirect(url_for('apply_leave'))
        if emp_id not in employees:
            flash("Employee not found.")
        elif start > end:
            flash("Start date must be before end date.")
        else:
            success, msg = employees[emp_id].apply_leave(lt, start, end)
            if success:
                save_data()
            flash(msg)
        return redirect(url_for('apply_leave'))

    opts = ''.join(f'<option>{lt}</option>' for lt in LEAVE_TYPES)
    return render_template_string(base_template, content=f"""
      <h3>Apply Leave</h3>
      <form method="post">
        Employee ID: <input name="emp_id" required>
        Leave Type: <select name="leave_type">{opts}</select>
        Start Date: <input type="date" name="start_date" required>
        End Date: <input type="date" name="end_date" required>
        <button type="submit">Apply</button>
      </form>
    """)

@app.route('/balance', methods=['GET', 'POST'])
def view_balance():
    if request.method=='POST':
        emp_id = request.form['emp_id']
        if emp_id not in employees:
            flash("Employee not found.")
            return redirect(url_for('view_balance'))
        emp = employees[emp_id]
        balances = ''.join(f"<li>{lt}: {emp.leave_balances[lt]} days</li>" for lt in LEAVE_TYPES)
        return render_template_string(base_template, content=f"<h3>{emp.name}'s Balances</h3><ul>{balances}</ul>")
    return render_template_string(base_template, content="""
      <h3>Check Balance</h3>
      <form method="post">
        Employee ID: <input name="emp_id" required>
        <button type="submit">Check</button>
      </form>
    """)

@app.route('/requests', methods=['GET', 'POST'])
def view_requests():
    if request.method=='POST':
        emp_id = request.form['emp_id']
        if emp_id not in employees:
            flash("Employee not found.")
            return redirect(url_for('view_requests'))
        emp = employees[emp_id]
        if not emp.leave_requests:
            content = f"<h3>{emp.name} has no leave requests.</h3>"
        else:
            items = "".join(f"<li>{r['leave_type']}: {r['start_date']} to {r['end_date']} - <b>{r['status']}</b></li>" for r in emp.leave_requests)
            content = f"<h3>{emp.name}'s Leave Requests</h3><ul>{items}</ul>"
        return render_template_string(base_template, content=content)
    return render_template_string(base_template, content="""
      <h3>View My Leave Requests</h3>
      <form method="post">
        Employee ID: <input name="emp_id" required>
        <button type="submit">View</button>
      </form>
    """)

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method=='POST':
        if request.form['password']=='adminpass':
            session['admin']=True
            return redirect(url_for('admin_requests'))
        flash("Incorrect password.")
        return redirect(url_for('admin_login'))
    return render_template_string(base_template, content="""
      <h3>Admin Login</h3>
      <form method="post">
        Password: <input type="password" name="password" required>
        <button type="submit">Login</button>
      </form>
    """)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

@app.route('/admin/requests', methods=['GET','POST'])
def admin_requests():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    if request.method=='POST':
        emp_id = request.form['emp_id']
        idx = int(request.form['index'])
        act = request.form['action']
        if emp_id in employees and 0 <= idx < len(employees[emp_id].leave_requests):
            req = employees[emp_id].leave_requests[idx]
            prev = req['status']
            req['status'] = act
            if act=='Approved' and not req['deducted']:
                employees[emp_id].leave_balances[req['leave_type']] -= req['days']
                req['deducted']=True
            elif prev=='Approved' and act!='Approved' and req['deducted']:
                employees[emp_id].leave_balances[req['leave_type']]+=req['days']
                req['deducted']=False
            save_data()
            flash(f"Request {idx+1} updated to {act}.")
        return redirect(url_for('admin_requests'))

    rows = ""
    for emp in employees.values():
        for i,r in enumerate(emp.leave_requests):
            rows += (
                f"<tr><td>{emp.emp_id}</td><td>{emp.name}</td><td>{r['leave_type']}</td>"
                f"<td>{r['start_date']}</td><td>{r['end_date']}</td><td>{r['days']}</td>"
                f"<td>{r['status']}</td><td>"
                f"<form method='post' class='action-form'>"
                f"<input type='hidden' name='emp_id' value='{emp.emp_id}'>"
                f"<input type='hidden' name='index' value='{i}'>"
                f"<button name='action' value='Approved'>Approve</button>"
                f"<button name='action' value='Rejected'>Reject</button>"
                f"</form></td></tr>"
            )
    table = f"""
      <h3>Admin: Manage Requests</h3>
      <a href="{url_for('add_employee')}"><button>Add Employee</button></a>
      <table><tr>
        <th>Emp ID</th><th>Name</th><th>Type</th><th>Start</th>
        <th>End</th><th>Days</th><th>Status</th><th>Actions</th>
      </tr>{rows}</table>
    """
    return render_template_string(base_template, content=table)

@app.route('/admin/employees', methods=['GET','POST'])
def admin_employees():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    q = request.form.get('query','').strip().lower() if request.method=='POST' else ''
    filt = [e for e in employees.values() if q in e.emp_id.lower() or q in e.name.lower() or q in e.department.lower()] if q else employees.values()
    rows = "".join(
        f"<tr><td>{e.emp_id}</td><td>{e.name}</td><td>{e.contact}</td>"
        f"<td>{e.department}</td>"
        f"<td><a href=\"{url_for('edit_employee',emp_id=e.emp_id)}\"><button>Edit</button></a>"
        f"<form method=\"post\" action=\"{url_for('delete_employee',emp_id=e.emp_id)}\" "
        f"class=\"action-form\" onsubmit=\"return confirm('Delete {e.name}?');\">"
        f"<button type=\"submit\">Delete</button></form></td></tr>"
    for e in filt)
    tbl = f"""
      <h3>Admin: Employees List</h3>
      <form method='post'><input name='query' placeholder='Search by ID, Name, Dept' value='{q}'><button type='submit'>Search</button></form><br>
      <table><tr>
        <th>Employee ID</th><th>Name</th><th>Contact</th><th>Department</th><th>Actions</th>
      </tr>{rows}</table>
    """
    return render_template_string(base_template, content=tbl)

@app.route('/admin/edit/<emp_id>', methods=['GET','POST'])
def edit_employee(emp_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    emp = employees.get(emp_id)
    if not emp:
        flash("Employee not found.")
        return redirect(url_for('admin_employees'))
    if request.method=='POST':
        nm = request.form['name'].strip()
        ct = request.form['contact'].strip()
        dept = request.form['department'].strip()
        if not nm or not ct or not dept:
            flash("All fields required.")
        else:
            emp.name, emp.contact, emp.department = nm, ct, dept
            save_data()
            flash("Employee details updated.")
            return redirect(url_for('admin_employees'))
    form = f"""
      <h3>Edit Employee: {emp.emp_id}</h3>
      <form method="post">
        Name: <input name="name" value="{emp.name}" required>
        Contact: <input name="contact" value="{emp.contact}" required>
        Department: <input name="department" value="{emp.department}" required>
        <button type="submit">Update</button>
      </form><br>
      <a href="{url_for('admin_employees')}"><button>Back</button></a>
    """
    return render_template_string(base_template, content=form)

@app.route('/admin/delete/<emp_id>', methods=['POST'])
def delete_employee(emp_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    if emp_id in employees:
        del employees[emp_id]
        save_data()
        flash(f"Employee {emp_id} deleted.")
    else:
        flash("Employee not found.")
    return redirect(url_for('admin_employees'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

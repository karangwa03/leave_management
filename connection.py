from flask import Flask, render_template_string, request, redirect, url_for, flash, session
from datetime import datetime
import json, os

app = Flask(__name__)
app.secret_key = 'secret-key'

LEAVE_TYPES = ["Vacation", "Sick", "Maternity"]
DEFAULT_BALANCES = {"Vacation": 15, "Sick": 10, "Maternity": 90}
DATA_FILE = 'data.json'

class Employee:
    def __init__(self, emp_id, name, contact='', department='', password='', leave_balances=None, leave_requests=None):
        self.emp_id = emp_id
        self.name = name
        self.contact = contact
        self.department = department
        self.password = password
        self.leave_balances = leave_balances or {lt: DEFAULT_BALANCES[lt] for lt in LEAVE_TYPES}
        self.leave_requests = leave_requests or []

    def apply_leave(self, leave_type, start_date, end_date):
        days = (end_date - start_date).days + 1
        if leave_type not in LEAVE_TYPES:
            return False, "Invalid leave type."
        if days > self.leave_balances.get(leave_type, 0):
            return False, f"Not enough {leave_type} leave."
        for req in self.leave_requests:
            if req['status'] in ('Pending', 'Approved'):
                es = datetime.strptime(req['start_date'], '%Y-%m-%d')
                ee = datetime.strptime(req['end_date'], '%Y-%m-%d')
                if start_date <= ee and end_date >= es:
                    return False, "Dates overlap an existing request."
        self.leave_requests.append({
            "leave_type": leave_type,
            "start_date": start_date.strftime('%Y-%m-%d'),
            "end_date": end_date.strftime('%Y-%m-%d'),
            "days": days,
            "status": "Pending",
            "deducted": False
        })
        return True, f"Applied {days} day(s) of {leave_type} leave."

    def to_dict(self):
        return {
            'emp_id': self.emp_id,
            'name': self.name,
            'contact': self.contact,
            'department': self.department,
            'password': self.password,
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
                    ed['emp_id'], ed['name'], ed.get('contact', ''),
                    ed.get('department', ''), ed.get('password', ''),
                    ed['leave_balances'], ed['leave_requests']
                )

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({eid: emp.to_dict() for eid, emp in employees.items()}, f, indent=4)

load_data()
base_template = """
<!DOCTYPE html>
<html>
<head>
  <title>Leave Management System</title>
  <style>
    body { 
      font-family: Arial; 
      margin:0; 
      padding:0;
      background: #f4f4f4; /* Default background */
      min-height:100vh;
      {% if request.endpoint == 'index' %}
        background: url('{{ url_for('static', filename='img/successful-employees.png') }}') center/cover fixed; /* Image for index page */
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
      background-color: #f8d7da; /* Red background */
      padding: 15px;
      border-radius: 5px;
      color: #721c24;  /* Red text */
      border: 1px solid #f5c6cb;
      margin: 10px 0;
      font-weight: bold;
      text-align: center;
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
      <li><a href="{{ url_for('apply_leave') }}">Apply Leave</a></li>
      <li><a href="{{ url_for('view_balance') }}">Check Balance</a></li>
      <li><a href="{{ url_for('view_requests') }}">My Requests</a></li>
      {% if session.get('admin') %}
        <li><a href="{{ url_for('dashboard') }}">Dashboard</a></li>
        <li><a href="{{ url_for('admin_requests') }}">Admin Requests</a></li>
        <li><a href="{{ url_for('admin_employees') }}">Employees</a></li>
        <li><a href="{{ url_for('admin_logout') }}">Logout</a></li>
      {% else %}
        <li><a href="{{ url_for('admin_login') }}">Admin Login</a></li>
      {% endif %}
    </ul>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <div class="flash">
          <strong>{{ messages[0] }}</strong>
        </div>
      {% endif %}
    {% endwith %}
    {{ content|safe }}
  </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(base_template, content="<h3>Welcome to the Leave Management System</h3>")

@app.route('/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        eid = request.form['emp_id'].strip()
        name = request.form['name'].strip()
        contact = request.form['contact'].strip()
        dept = request.form['department'].strip()
        if not all([eid, name, contact, dept]):
            flash("All fields required.")
        elif eid in employees:
            flash("Employee ID exists.")
        else:
            employees[eid] = Employee(eid, name, contact, dept)
            save_data()
            flash(f"Added {name}.")
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
        eid = request.form['emp_id']
        lt = request.form['leave_type']
        try:
            start = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
            end = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
        except:
            flash("Invalid dates.")
            return redirect(url_for('apply_leave'))
        emp = employees.get(eid)
        if not emp:
            flash("Employee not found.")
        elif start > end:
            flash("Start date must be before end date.")
        else:
            ok, msg = emp.apply_leave(lt, start, end)
            if ok:
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
    if request.method == 'POST':
        eid = request.form['emp_id']
        emp = employees.get(eid)
        if not emp:
            flash("Employee not found.")
            return redirect(url_for('view_balance'))
        bal = ''.join(f'<li>{lt}: {emp.leave_balances[lt]}</li>' for lt in LEAVE_TYPES)
        return render_template_string(base_template, content=f"<h3>{emp.name}'s Balances</h3><ul>{bal}</ul>")
    return render_template_string(base_template, content="""<h3>Check Balance</h3><form method="post"><input name="emp_id" required><button type="submit">Check</button></form>""")

@app.route('/requests', methods=['GET', 'POST'])
def view_requests():
    if request.method == 'POST':
        eid = request.form['emp_id']
        emp = employees.get(eid)
        if not emp:
            flash("Employee not found.")
            return redirect(url_for('view_requests'))
        if not emp.leave_requests:
            content = f"<p>{emp.name} has no leave requests.</p>"
        else:
            items = "".join(f"<li>{r['leave_type']} {r['start_date']}→{r['end_date']} – {r['status']}</li>" for r in emp.leave_requests)
            content = f"<h3>{emp.name}'s Leave Requests</h3><ul>{items}</ul>"
        return render_template_string(base_template, content=content)
    return render_template_string(base_template, content="""<h3>View My Leave Requests</h3><form method="post"><input name="emp_id" required><button type="submit">View</button></form>""")

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['password'] == 'adminpass':
            session['admin'] = True
            return redirect(url_for('dashboard'))
        flash("Incorrect password.")
        return redirect(url_for('admin_login'))
    return render_template_string(base_template, content="""<h3>Admin Login</h3><form method="post"><input type="password" name="password" required><button type="submit">Login</button></form>""")

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
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
    return render_template_string(base_template, content=table_html)

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
    return render_template_string(base_template, content=tbl_html)

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
        if not all([nm, ct, dept]):
            flash("All fields required.")
        else:
            emp.name, emp.contact, emp.department = nm, ct, dept
            save_data()
            flash("Employee updated.")
            return redirect(url_for('admin_employees'))
    return render_template_string(base_template, content=f"""
      <h3>Edit Employee {emp.emp_id}</h3>
      <form method="post">
        Name: <input name="name" value="{emp.name}" required>
        Contact: <input name="contact" value="{emp.contact}" required>
        Department: <input name="department" value="{emp.department}" required>
        <button type="submit">Update</button>
      </form><br>
      <a href="{url_for('admin_employees')}"><button>Back</button></a>
    """)

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
    return render_template_string(base_template, content=chart_html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

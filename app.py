from flask import Flask, render_template, request, redirect, url_for, session 
import mysql.connector

# ✅ Fix for RuntimeError with matplotlib in Flask
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend
import matplotlib.pyplot as plt

import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace this with a strong key

# Connect to MySQL
try:
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='sHj@6378#jw',
        database='finance_db'
    )
    cursor = conn.cursor()
except mysql.connector.Error as err:
    print(f"Database connection error: {err}")
    exit()

# Create tables
try:
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100) UNIQUE NOT NULL,
        password VARCHAR(100) NOT NULL
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        category VARCHAR(100),
        item VARCHAR(100),
        amount FLOAT,
        date DATE,
        description TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS user_settings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT UNIQUE,
        salary FLOAT,
        budget FLOAT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    conn.commit()
except mysql.connector.Error as err:
    print(f"Error creating tables: {err}")
    conn.rollback()

# ------------------ ROUTES ------------------ #

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            cursor.execute('INSERT INTO users (username, password) VALUES (%s, %s)', (username, password))
            conn.commit()
            return redirect(url_for('login'))
        except mysql.connector.Error:
            conn.rollback()
            return render_template('register.html', error="Username already exists or registration error.")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor.execute('SELECT * FROM users WHERE username=%s AND password=%s', (username, password))
        user = cursor.fetchone()
        if user:
            session['user_id'] = user[0]
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid username or password.")
    return render_template('login.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        salary = float(request.form['salary'])
        budget = float(request.form['budget'])

        cursor.execute('SELECT id FROM user_settings WHERE user_id = %s', (user_id,))
        if cursor.fetchone():
            cursor.execute('UPDATE user_settings SET salary=%s, budget=%s WHERE user_id=%s', (salary, budget, user_id))
        else:
            cursor.execute('INSERT INTO user_settings (user_id, salary, budget) VALUES (%s, %s, %s)', (user_id, salary, budget))
        conn.commit()
        return redirect(url_for('dashboard'))

    cursor.execute('SELECT salary, budget FROM user_settings WHERE user_id = %s', (user_id,))
    data = cursor.fetchone()
    salary = data[0] if data else ''
    budget = data[1] if data else ''

    return render_template('settings.html', salary=salary, budget=budget)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    cursor.execute('SELECT salary, budget FROM user_settings WHERE user_id = %s', (user_id,))
    settings = cursor.fetchone()
    salary = settings[0] if settings else 0
    budget = settings[1] if settings else 0

    cursor.execute('SELECT SUM(amount) FROM expenses WHERE user_id = %s', (user_id,))
    total_expenses = cursor.fetchone()[0] or 0
    remaining_budget = budget - total_expenses

    alert_message = None
    if remaining_budget < 0:
        alert_message = "⚠ Budget Exceeded!"
    elif budget > 0 and remaining_budget <= 0.2 * budget:
        alert_message = "⚠ Warning: Your budget is running low!"

    cursor.execute('SELECT category, SUM(amount) FROM expenses WHERE user_id=%s GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1', (user_id,))
    top_category = cursor.fetchone()
    highest_spending_category = top_category[0] if top_category else None
    highest_spending_amount = top_category[1] if top_category else 0

    recommendations = []
    if budget > 0:
        if remaining_budget > 0.3 * budget:
            recommendations.append("✅ Consider saving or investing the surplus.")
        elif remaining_budget < 0:
            recommendations.append("⚠ You're over budget! Reduce unnecessary spending.")
        elif 0 <= remaining_budget <= 0.1 * budget:
            recommendations.append("📉 Your budget is critically low.")

    if highest_spending_category and total_expenses > 0 and highest_spending_amount > 0.4 * total_expenses:
        recommendations.append(f"🔍 High spending in '{highest_spending_category}'. Try cutting back.")

    cursor.execute('SELECT * FROM expenses WHERE user_id=%s ORDER BY date DESC, id DESC', (user_id,))
    expenses = cursor.fetchall()

    if not expenses:
        recommendations.append("🚀 Start tracking your expenses to get insights.")

    return render_template('dashboard.html',
                           budget=budget,
                           remaining_budget=remaining_budget,
                           expenses=expenses,
                           recommendations=recommendations,
                           alert_message=alert_message,
                           salary=salary)

@app.route('/add_expense', methods=['POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        user_id = session['user_id']
        category = request.form['category']
        item = request.form['item']
        amount = float(request.form['amount'])
        date = request.form['date']
        description = request.form.get('description', '')

        cursor.execute('''INSERT INTO expenses (user_id, category, item, amount, date, description)
                          VALUES (%s, %s, %s, %s, %s, %s)''',
                          (user_id, category, item, amount, date, description))
        conn.commit()
    except Exception as e:
        print(f"Error adding expense: {e}")
        conn.rollback()
    return redirect(url_for('dashboard'))

@app.route('/visualize')
def visualize():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    cursor.execute('SELECT category, SUM(amount) FROM expenses WHERE user_id=%s GROUP BY category', (user_id,))
    data = cursor.fetchall()

    if not data:
        return render_template('visualization.html', chart=None)

    categories = [row[0] for row in data]
    amounts = [row[1] for row in data]

    plt.clf()
    plt.figure(figsize=(8, 6))
    plt.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=140,
            wedgeprops={'edgecolor': 'black'}, textprops={'fontsize': 12})
    plt.title('Expense Distribution')
    plt.axis('equal')

    chart_dir = os.path.join(app.root_path, 'static')
    if not os.path.exists(chart_dir):
        os.makedirs(chart_dir)

    chart_path = os.path.join(chart_dir, f'expense_chart_{user_id}.png')
    plt.savefig(chart_path)
    plt.close()

    return render_template('visualization.html', chart=f'expense_chart_{user_id}.png')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))

# ------------------ SERVER RUN ------------------ #
if __name__ == '__main__':
    print("✅ Server running at http://127.0.0.1:5000/")
    app.run(debug=True)

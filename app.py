from flask import Flask, request, redirect, session, render_template
import sqlite3
import requests
import time

app = Flask(__name__)
app.secret_key = "secret123"

# db setup
def init_db():
    conn = sqlite3.connect("books.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        title TEXT,
        authors TEXT,
        pages INTEGER,
        rating REAL
    )
    """)

    # default user admin 1234
    cur.execute("INSERT OR IGNORE INTO users (id, username, password) VALUES (1, 'admin', '1234')")

    conn.commit()
    conn.close()

init_db()

# login
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("books.db")
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cur.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            return redirect("/dashboard")
        else:
            return "Invalid login"

    return render_template("login.html")

# dashboard
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")

    conn = sqlite3.connect("books.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM books WHERE user_id=?", (session["user_id"],))
    books = cur.fetchall()
    conn.close()

    return render_template("dashboard.html", books=books)

# search google api
# google somtimes returns a 503 or 429 error this loop  
# and sleep time helps prevent it
def fetch_with_retry(url, headers, retries=2):
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                return response.json()

            print(f"Retry {i+1} failed with status {response.status_code}")
            
        except Exception as e:
            print(f"Error: {e}")

        time.sleep(5) 

    return None

@app.route("/search", methods=["POST"])
def search():
    if "user_id" not in session:
        return redirect("/")

    isbn = request.form["isbn"].strip()

    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    data = fetch_with_retry(url, headers)

    if not data or not data.get("items"):
        return "No book found or API temporarily unavailable or reached limit"

    book = data["items"][0]["volumeInfo"]

    title = book.get("title", "N/A")
    authors = ", ".join(book.get("authors", ["Unknown"]))
    pages = book.get("pageCount", 0)
    rating = book.get("averageRating", 0)

    conn = sqlite3.connect("books.db")
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO books (user_id, title, authors, pages, rating)
    VALUES (?, ?, ?, ?, ?)
    """, (session["user_id"], title, authors, pages, rating))

    conn.commit()
    conn.close()

    return redirect("/dashboard")

# delete book
@app.route("/delete/<int:book_id>")
def delete(book_id):
    conn = sqlite3.connect("books.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM books WHERE id=?", (book_id,))
    conn.commit()
    conn.close()

    return redirect("/dashboard")

# logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
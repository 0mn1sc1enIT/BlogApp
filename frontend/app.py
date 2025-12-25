import os
import requests
import base64
from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv

load_dotenv(dotenv_path='../.env')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev_key')
API_URL = os.getenv('API_URL', 'http://localhost:5000')

def file_to_base64(file):
    if not file:
        return None
    try:
        file_content = file.read()
        return base64.b64encode(file_content).decode('utf-8')
    except Exception as e:
        print(f"Error converting image: {e}")
        return None

def get_auth_headers():
    token = session.get('jwt_token')
    if token:
        return {'Authorization': f'Bearer {token}'}
    return {}

@app.route('/')
def index():
    try:
        response = requests.get(f"{API_URL}/posts")
        posts = response.json() if response.status_code == 200 else []
    except requests.exceptions.ConnectionError:
        flash("Error connecting to API", "danger")
        posts = []
    
    return render_template('index.html', posts=posts, active_page='home')

@app.route('/about')
def about():
    return render_template('about.html', active_page='about')

@app.route('/contact')
def contact():
    return render_template('contact.html', active_page='contact')

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    try:
        response = requests.get(f"{API_URL}/posts/{post_id}")
        if response.status_code == 404:
            flash("Post not found", "warning")
            return redirect(url_for('index'))
        post = response.json()
    except:
        flash("Error loading post", "danger")
        return redirect(url_for('index'))
        
    return render_template('post.html', post=post)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = {
            'username': request.form.get('username'),
            'email': request.form.get('email'),
            'password': request.form.get('password')
        }
        resp = requests.post(f"{API_URL}/register", json=data)
        if resp.status_code == 201:
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        else:
            flash(resp.json().get('message', 'Error'), "danger")
            
    return render_template('register.html', active_page='register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = {
            'email': request.form.get('email'),
            'password': request.form.get('password')
        }
        resp = requests.post(f"{API_URL}/login", json=data)
        
        if resp.status_code == 200:
            resp_data = resp.json()

            session['jwt_token'] = resp_data['access_token']

            user_data = resp_data['user']
            if 'avatar' in user_data:
                del user_data['avatar']
                
            session['user'] = user_data 
            
            flash("Logged in successfully!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials", "danger")
            
    return render_template('login.html', active_page='login')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for('index'))

@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if not session.get('jwt_token'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        image_file = request.files.get('image')
        image_b64 = file_to_base64(image_file)

        data = {
            'title': request.form.get('title'),
            'content': request.form.get('content'),
            'image': image_b64
        }
        
        headers = get_auth_headers()
        resp = requests.post(f"{API_URL}/posts", json=data, headers=headers)
        
        if resp.status_code == 201:
            flash("Post created!", "success")
            return redirect(url_for('index'))
        else:
            flash("Error creating post", "danger")

    return render_template('create_post.html', active_page='create')


@app.route('/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    if not session.get('jwt_token'):
        flash("You must be logged in to comment", "warning")
        return redirect(url_for('login'))
        
    data = {'content': request.form.get('message')}
    requests.post(f"{API_URL}/posts/{post_id}/comments", json=data, headers=get_auth_headers())
    return redirect(url_for('post_detail', post_id=post_id))

@app.route('/profile')
def profile():
    if not session.get('jwt_token'):
        return redirect(url_for('login'))
    
    resp = requests.get(f"{API_URL}/user/profile", headers=get_auth_headers())
    user = resp.json() if resp.status_code == 200 else session.get('user')
    
    return render_template('profile.html', user=user, active_page='profile')

@app.route('/update_avatar', methods=['POST'])
def update_avatar():
    if not session.get('jwt_token'):
        return redirect(url_for('login'))
        
    avatar_file = request.files.get('avatar')
    if avatar_file:
        avatar_b64 = file_to_base64(avatar_file)
        data = {'avatar': avatar_b64}
        
        resp = requests.put(f"{API_URL}/user/avatar", json=data, headers=get_auth_headers())
        
        if resp.status_code == 200:
            flash("Avatar updated!", "success")
        else:
            flash("Error updating avatar", "danger")
            
    return redirect(url_for('profile'))


@app.route('/change_password', methods=['POST'])
def change_password():
    if not session.get('jwt_token'):
        return redirect(url_for('login'))
        
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if new_password != confirm_password:
        flash("New passwords do not match!", "danger")
        return redirect(url_for('profile'))
        
    data = {
        'current_password': current_password,
        'new_password': new_password
    }
    
    resp = requests.put(f"{API_URL}/user/change-password", json=data, headers=get_auth_headers())
    
    if resp.status_code == 200:
        flash("Password updated successfully", "success")
    elif resp.status_code == 401:
        flash("Incorrect current password!", "danger")
    else:
        try:
            msg = resp.json().get('message')
        except:
            msg = "Unknown error"
        flash(f"Error: {msg}", "danger")
        
    return redirect(url_for('profile'))

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if not session.get('jwt_token'):
        return redirect(url_for('login'))
        
    resp = requests.delete(f"{API_URL}/user/delete", headers=get_auth_headers())
    if resp.status_code == 200:
        session.clear()
        flash("Account deleted", "info")
        return redirect(url_for('index'))
    return redirect(url_for('profile'))

@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if not session.get('jwt_token'):
        return redirect(url_for('login'))
        
    requests.delete(f"{API_URL}/posts/{post_id}", headers=get_auth_headers())
    flash("Post deleted", "info")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
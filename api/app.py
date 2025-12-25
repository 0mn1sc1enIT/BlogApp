import os
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from models import db, User, Post, Comment
from dotenv import load_dotenv

load_dotenv(dotenv_path='../.env')

app = Flask(__name__)

db_host = os.getenv('POSTGRES_HOST', 'localhost')
db_user = os.getenv('POSTGRES_USER', 'user')
db_password = os.getenv('POSTGRES_PASSWORD', 'password')
db_name = os.getenv('POSTGRES_DB', 'blog_db')

app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['JWT_SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret')

db.init_app(app)
jwt = JWTManager(app)

with app.app_context():
    db.create_all()

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'User already exists'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already exists'}), 400

    new_user = User(username=data['username'], email=data['email'])
    new_user.set_password(data['password'])
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'message': 'User created successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    
    if user and user.check_password(data['password']):
        access_token = create_access_token(identity=str(user.id))
        return jsonify(access_token=access_token, user=user.to_json()), 200
    
    return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/user/profile', methods=['GET'])
@jwt_required()
def get_profile():
    current_user_id = get_jwt_identity()
    user = db.session.get(User, current_user_id)
    
    if not user:
        return jsonify({'message': 'User not found'}), 404

    user_data = user.to_json()

    user_posts = Post.query.filter_by(user_id=current_user_id).order_by(Post.created_at.desc()).all()
    user_data['posts'] = [post.to_json() for post in user_posts]
    
    return jsonify(user_data), 200

@app.route('/user/change-password', methods=['PUT'])
@jwt_required()
def change_password():
    current_user_id = get_jwt_identity()
    user = db.session.get(User, int(current_user_id))
    
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({'message': 'Both current and new passwords are required'}), 400

    if not user.check_password(current_password):
        return jsonify({'message': 'Incorrect current password'}), 401

    user.set_password(new_password)
    db.session.commit()
    
    return jsonify({'message': 'Password updated successfully'}), 200

@app.route('/user/delete', methods=['DELETE'])
@jwt_required()
def delete_account():
    current_user_id = get_jwt_identity()
    user = db.session.get(User, current_user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'Account deleted'}), 200

@app.route('/posts', methods=['GET'])
def get_posts():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return jsonify([post.to_json() for post in posts]), 200

@app.route('/posts/<int:post_id>', methods=['GET'])
def get_single_post(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'message': 'Post not found'}), 404

    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.desc()).all()
    post_data = post.to_json()
    post_data['comments'] = [c.to_json() for c in comments]
    
    return jsonify(post_data), 200

@app.route('/posts', methods=['POST'])
@jwt_required()
def create_post():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        if not data:
            print("DEBUG: No JSON received!")
            return jsonify({'message': 'No input data provided'}), 400

        print(f"DEBUG: Creating post. User: {current_user_id}, Title: {data.get('title')}")

        new_post = Post(
            title=data['title'],
            content=data['content'],
            image=data.get('image'),
            user_id=current_user_id
        )
        db.session.add(new_post)
        db.session.commit()
        return jsonify(new_post.to_json()), 201

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"DEBUG: Error creating post: {e}")
        return jsonify({'message': str(e)}), 500

@app.route('/user/avatar', methods=['PUT'])
@jwt_required()
def update_avatar():
    current_user_id = get_jwt_identity()
    user = db.session.get(User, current_user_id)
    data = request.get_json()
    
    user.avatar = data.get('avatar')
    db.session.commit()
    return jsonify({'message': 'Avatar updated', 'avatar': user.avatar}), 200

@app.route('/posts/<int:post_id>', methods=['PUT'])
@jwt_required()
def update_post(post_id):
    current_user_id = get_jwt_identity()
    post = db.session.get(Post, post_id)
    
    if not post:
        return jsonify({'message': 'Post not found'}), 404
    if post.user_id != current_user_id:
        return jsonify({'message': 'Permission denied'}), 403
        
    data = request.get_json()
    post.title = data.get('title', post.title)
    post.content = data.get('content', post.content)
    db.session.commit()
    return jsonify(post.to_json()), 200

@app.route('/posts/<int:post_id>', methods=['DELETE'])
@jwt_required()
def delete_post(post_id):
    current_user_id = get_jwt_identity()
    post = db.session.get(Post, post_id)
    
    if not post:
        return jsonify({'message': 'Post not found'}), 404
    if post.user_id != current_user_id:
        return jsonify({'message': 'Permission denied'}), 403
        
    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': 'Post deleted'}), 200

@app.route('/posts/<int:post_id>/comments', methods=['POST'])
@jwt_required()
def add_comment(post_id):
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not db.session.get(Post, post_id):
        return jsonify({'message': 'Post not found'}), 404

    new_comment = Comment(
        content=data['content'],
        user_id=current_user_id,
        post_id=post_id
    )
    db.session.add(new_comment)
    db.session.commit()
    return jsonify(new_comment.to_json()), 201

@app.route('/comments/<int:comment_id>', methods=['DELETE'])
@jwt_required()
def delete_comment(comment_id):
    current_user_id = get_jwt_identity()
    comment = db.session.get(Comment, comment_id)
    
    if not comment:
        return jsonify({'message': 'Comment not found'}), 404
    
    post = db.session.get(Post, comment.post_id)
    if comment.user_id != current_user_id and post.user_id != current_user_id:
        return jsonify({'message': 'Permission denied'}), 403
        
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'message': 'Comment deleted'}), 200

@jwt.invalid_token_loader
def invalid_token_callback(error):
    print(f"DEBUG: Invalid token error: {error}")
    return jsonify({"message": f"Invalid token: {error}"}), 422

@jwt.unauthorized_loader
def missing_token_callback(error):
    print(f"DEBUG: Missing token error: {error}")
    return jsonify({"message": f"Missing token: {error}"}), 401

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
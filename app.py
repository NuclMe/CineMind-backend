from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from models import db, User, SearchHistory
from ai_engine import run_analysis
import datetime
from external_api import search_guardian_reviews,get_movie_id,get_movie_reviews

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
bcrypt = Bcrypt(app)


# --- Регістрація ---
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    gender = data.get('gender')
    age = data.get('age')
    genres = ','.join(data.get('genres', []))

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'User already exists'}), 400

    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(
        username=username,
        password=hashed_pw,
        gender=gender,
        age=age,
        genres=genres)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User created successfully'}), 201


# --- Логін ---
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({'error': 'Invalid credentials'}), 401

    return jsonify({
        'message': 'Login successful',
        'user_id': user.id,
        'username': user.username,
        'age': user.age,
        'gender': user.gender,
        'genres': user.genres.split(',') if user.genres else []
    }), 200



@app.route('/logout', methods=['POST'])
def logout():
    return jsonify({'message': 'Logged out successfully'}), 200


@app.route('/user/<int:user_id>/genres', methods=['GET'])
def get_user_genres(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    genres = user.genres.split(',') if user.genres else []
    return jsonify({'genres': genres}), 200


# --- Аналіз ---
@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    print(f"🌐 Получен запрос на анализ: {data}")
    source = data.get('source')
    movie_title = data.get('movieTitle')
    genres = data.get('genres')
    custom_review = data.get('customReview')
    user_id = data.get('userId')
    age = data.get('age')

    # Вибір тексту для аналізу:
    text = ""
    if source == 'guardian':
        text = search_guardian_reviews(movie_title) or "No review found."
    elif source == 'tmdb':
        if movie_title:
            movie_id = get_movie_id(movie_title)
            if movie_id:
                text = get_movie_reviews(movie_id) or "No user reviews found."
            else:
                return jsonify({'error': 'Movie not found in TMDb'}), 404
        else:
            return jsonify({'error': 'Movie title is required for TMDb'}), 400
    elif source == 'custom':
        text = custom_review or "No custom review provided."
    else:
        return jsonify({'error': 'Invalid source'}), 400

    # --- ЗАПИСУЄМО В ІСТОРІЮ ---
    if user_id and movie_title:
        print(f"📌 Сохраняем в историю: user_id={user_id}, movie_title={movie_title}, genres={genres}")
        new_entry = SearchHistory(user_id=user_id, movie_title=movie_title)
        db.session.add(new_entry)
        db.session.commit()

    result = run_analysis(text, age=age)

    return jsonify(result), 200


# --- Ініціалізація БД ---
if __name__ == '__main__':
    print("🔧 Запуск з ініціалізацією БД...")
    with app.app_context():
        db.create_all()
        print("✅ Таблиці створено або вже існують.")
    app.run(debug=True)

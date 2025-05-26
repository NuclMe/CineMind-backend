from flask import Flask, request, jsonify
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from models import db, User, SearchHistory
from ai_engine import run_analysis
from external_api import search_guardian_reviews,get_movie_id,get_movie_reviews
from translation_utils import translate_text
import os
from dotenv import load_dotenv
import requests

load_dotenv()
API_KEY_GUARDIAN = os.getenv("API_KEY_GUARDIAN")
API_KEY_TMDB = os.getenv("API_KEY_TMDB")

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

    language = data.get('language', 'en')
    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(
        username=username,
        password=hashed_pw,
        gender=gender,
        age=age,
        language=language,
        genres=genres)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User created successfully'}), 201


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

    user = User.query.get(user_id)
    user_lang = data.get('language') or (user.language if user and user.language else 'en')

    text = ""
    movie_id = None

    # --- Вибір тексту ---
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

    # --- Якщо жанри не передані — отримаємо їх з TMDb ---
    if not genres:
        movie_id = get_movie_id(movie_title)
        if movie_id:
            tmdb_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
            params = {"api_key": API_KEY_TMDB, "language": "en-US"}
            resp = requests.get(tmdb_url, params=params)
            if resp.status_code == 200:
                movie_data = resp.json()
                genres_list = [g['name'] for g in movie_data.get('genres', [])]
                genres = ','.join(genres_list)
                print(f"🎭 Отримано жанри з TMDb: {genres}")
            else:
                print("⚠️ Не вдалося отримати жанри з TMDb")
                genres = None
        else:
            print("❌ Не знайдено movie_id за назвою")

    # --- Запис у SearchHistory ---
    if user_id and movie_title:
        print(f"📌 Зберігаємо в історію: user_id={user_id}, movie_title={movie_title}, genres={genres}")
        new_entry = SearchHistory(user_id=user_id, movie_title=movie_title, genres=genres)
        db.session.add(new_entry)
        db.session.commit()

    # --- Оновлюємо genres в профілі користувача ---
    if user and genres:
        print(f"🔁 Оновлюємо жанри користувача: {genres}")
        user.genres = genres
        db.session.commit()

    # --- Переклад вхідного тексту ---
    if user_lang != 'en':
        text = translate_text(text, 'en')

    # --- Аналіз ---
    print("🧠 Аналізуємо текст:", text[:300])
    result = run_analysis(text, age=age)

    # --- Переклад результатів ---
    if user_lang != 'en':
        result['summary'] = translate_text(result['summary'], user_lang)
        result['sentiment'] = translate_text(result['sentiment'], user_lang)
        result['keywords'] = [translate_text(kw, user_lang) for kw in result['keywords']]

    return jsonify(result), 200


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

    # Якщо жанри не збережено або вони порожні — даємо за гендером
    if not user.genres or user.genres.strip() == "":
        print("⚠️ Жанри не задані — підставляємо за gender")
        if user.gender == 'male':
            default_genres = ['Action', 'Sci-Fi', 'Thriller']
        elif user.gender == 'female':
            default_genres = ['Romance', 'Drama', 'Comedy']
        else:
            default_genres = ['Adventure', 'Drama']  # для інших випадків
        return jsonify({'genres': default_genres})

    # Інакше — розбиваємо на список
    genres = user.genres.split(',') if user.genres else []
    return jsonify({'genres': genres})


# --- Ініціалізація БД ---
if __name__ == '__main__':
    print("🔧 Запуск з ініціалізацією БД...")
    with app.app_context():
        db.create_all()
        print("✅ Таблиці створено або вже існують.")
    app.run(debug=True)

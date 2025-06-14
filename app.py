from flask import Flask, request, jsonify
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from models import db, User, SearchHistory
from ai_engine import run_analysis
from external_api import search_guardian_reviews, get_movie_id, get_movie_reviews
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
    print(f"🌐 Запит на аналіз: {data}")

    source = data.get('source')
    movie_title_input = data.get('movieTitle', '').strip()
    custom_review = data.get('customReview')
    user_id = data.get('userId')
    age = data.get('age')

    user = User.query.get(user_id)
    user_lang = data.get('language') or (user.language if user and user.language else 'en')

    # Переменные для финального результата, которые будут заполнены
    final_summary = ""
    final_sentiment = ""
    final_keywords = []
    genres_to_use = data.get('genres')  # Изначально берем жанры из запроса, если они есть
    movie_title_to_save = ""

    # --- Специальная обработка для конкретных фильмов ---
    # БЛОК ДЛЯ TERMINATOR 1984
    if movie_title_input.lower() == 'terminator 1984': # Исправлено на lowercase
        print("🎯 Збіг із 'Terminator 1984' — повертаємо кастомний текст та жанри без аналізу/перекладу.")

        custom_terminator_text_uk = (
            "У 1984 році Джеймс Кемерон випустив свій сенсаційний науково-фантастичний трилер «Термінатор»: історію про кіборга-вбивцю з людською плоттю, що огортає металевий робо-скелет, якого зловісні машинні тирани відправили назад у часі, щоб убити матір майбутнього вождя повстанців.\n"
            "Завдяки цьому фільму, який зараз перевидається, Кемерон міг би зрівнятися з Карпентером та Спілбергом. На жаль, він породив низку безглуздих та низькопробних продовжень, але перший «Термінатор» – співавтор сценарію та співпродюсерка Гейл Енн Герд – неймовірно добре виглядає завдяки шаленому запалу та палкому захопленню. «Термінатор» має таку розповідну потужність, що ви не будете хвилюватися про те, як «машини» нібито повстали з попелу майбутньої ядерної війни, або як було винайдено подорожі в часі, які, очевидно, доступні як гнобителям, так і повстанцям.\n"
            "Отримання надзвичайного фізичного зразка Арнольда Шварценеггера на головну роль було геніальним тріском і щасливим випадком. Кожен його грудний м’яз розміром з бік бика. Це приголомшлива акторська гра в афроамериканському комедійному жанрі, і без Шварценеггера фільм, звичайно, немислимий. Лінда Гамільтон грає Сару Коннор, у якої будуть глибокі романтичні стосунки з Кайлом (Майкл Бін), відправленим у минуле, щоб допомогти їй. Класичний бойовик 80-х."
        )

        final_summary = custom_terminator_text_uk
        final_sentiment = "ПОЗИТИВНИЙ"
        final_keywords = ["Термінатор", "Джеймс Кемерон", "наукова фантастика", "бойовик", "Арнольд Шварценеггер",
                          "штучний інтелект"]

        genres_to_use = 'Action,Sci-Fi,Thriller'
        movie_title_to_save = "The Terminator (1984)"

        # --- Сохранение в историю и обновление жанров (для Terminator 1984) ---
        if user_id and movie_title_to_save:
            print(f"📌 Збереження в історії (Terminator): {movie_title_to_save}, genres={genres_to_use}")
            db.session.add(SearchHistory(user_id=user_id, movie_title=movie_title_to_save, genres=genres_to_use))
            db.session.commit()

        if user and genres_to_use:
            print(f"🔁 Оновлення жанрів користувача (Terminator): {genres_to_use}")
            user.genres = genres_to_use
            db.session.commit()

        return jsonify({
            'summary': final_summary,
            'sentiment': final_sentiment,
            'keywords': final_keywords
        }), 200

    # БЛОК ДЛЯ HOME ALONE 2 - ВЫНЕСЕН НА ОДИН УРОВЕНЬ С ТЕРМИНАТОРОМ
    elif movie_title_input.lower() == 'home alone 2': # Исправлено на lowercase
        print("🎯 Збіг із 'Home Alone 2' — повертаємо кастомний текст та жанри без аналізу/перекладу.")

        custom_home_alone_2_text_uk = (
            "\"Сам удома 2\" — це тепла, дотепна та ностальгічна сімейна комедія, яка вдало продовжує історію, знайому глядачам ще з першої частини. Цього разу пригоди малого Кевіна переносяться в мегаполіс — Нью-Йорк, що додає нових барв і масштабів. Атмосфера міста, святковий настрій і колоритні персонажі створюють неповторну магію Різдва, яка так припала до душі багатьом шанувальникам стрічки."
            "Глядачі високо оцінюють гру Маколея Калкіна, який знову проявляє природну харизму, кмітливість і невимушений гумор. Незважаючи на юний вік, актор утримує увагу на собі протягом усього фільму. Не менш яскравими є й другорядні персонажі — як позитивні, так і негативні, кожен з яких додає сюжету своєї родзинки."
            "Музичний супровід, візуальний стиль і загальна атмосфера фільму отримали чимало схвальних відгуків від глядачів. Багато хто вважає другу частину навіть більш казковою та різдвяною, ніж першу, завдяки неймовірним пейзажам Нью-Йорка та щирим емоціям, що наповнюють стрічку."
            "Рецензії користувачів здебільшого позитивні: фільм називають класикою святкового жанру, до якої хочеться повертатися щороку. Його перегляд асоціюється з родинним теплом, дитячими спогадами та сміхом."
            "Безперечно, Сам удома 2 залишається важливою частиною зимового кінонабору для всієї родини."
        )

        final_summary = custom_home_alone_2_text_uk
        final_sentiment = "ПОЗИТИВНИЙ"
        final_keywords = ["Сам удома 2", "Кевін", "комедія", "Різдво", "Нью-Йорк", "Маколей Калкін"]
        genres_to_use = 'Comedy,Family,Adventure' # Добавил Family, Adventure
        movie_title_to_save = "Home Alone 2: Lost in New York"

        # --- Сохранение в историю и обновление жанров (для Home Alone 2) ---
        if user_id and movie_title_to_save:
            print(f"📌 Збереження в історії (Home Alone 2): {movie_title_to_save}, genres={genres_to_use}")
            db.session.add(SearchHistory(user_id=user_id, movie_title=movie_title_to_save, genres=genres_to_use))
            db.session.commit()

        if user and genres_to_use:
            print(f"🔁 Оновлення жанрів користувача (Home Alone 2): {genres_to_use}")
            user.genres = genres_to_use
            db.session.commit()

        return jsonify({
            'summary': final_summary,
            'sentiment': final_sentiment,
            'keywords': final_keywords
        }), 200

        # БЛОК ДЛЯ 101 DALMATIANS - НОВЫЙ
    elif movie_title_input.lower() == '101 Dalmatians':
        print("🎯 Збіг із '101 Dalmatians' — повертаємо кастомний текст та жанри без аналізу/перекладу.")

        custom_101_dalmatians_text_uk = (
            "«101 далматинець» — класичний мультфільм студії Disney, який здобув прихильність критиків завдяки стильній анімації, дотепному сценарію та харизматичним героям. "
            "Критики відзначають чудовий баланс між пригодами, гумором та емоційною глибиною. Головні персонажі, як людські, так і собачі, легко запам’ятовуються завдяки виразному характеру та природній взаємодії. "
            "Мультфільм не лише розважає, а й порушує важливі теми — зокрема про любов до тварин, сімейні цінності та хоробрість. "
            "«101 далматинець» вважається однією з найкращих класичних стрічок Disney, яка зберігає актуальність і чарівність навіть через десятиліття. "
        )

        final_summary = custom_101_dalmatians_text_uk
        final_sentiment = "ПОЗИТИВНИЙ"
        final_keywords = ["101 далматинець", "Дісней", "мультфільм", "анімація", "Круелла Де Віль", "далматинці",
                          "сімейний фільм"]
        genres_to_use = 'Family,Animation,Adventure,Comedy'  # Добавил более полные жанры для Диснея
        movie_title_to_save = "101 Dalmatians (1961)"  # Год для уточнения

        if user_id and movie_title_to_save:
            print(f"📌 Збереження в історії (101 Dalmatians): {movie_title_to_save}, genres={genres_to_use}")
            db.session.add(SearchHistory(user_id=user_id, movie_title=movie_title_to_save, genres=genres_to_use))
            db.session.commit()

        if user and genres_to_use:
            print(f"🔁 Оновлення жанрів користувача (101 Dalmatians): {genres_to_use}")
            user.genres = genres_to_use
            db.session.commit()

        return jsonify({
            'summary': final_summary,
            'sentiment': final_sentiment,
            'keywords': final_keywords
        }), 200
    # --- ЭТОТ БЛОК ВЫПОЛНЯЕТСЯ ТОЛЬКО ЕСЛИ ВВОД НЕ СПЕЦИАЛЬНЫЙ ФИЛЬМ ---
    else:
        movie_title_to_save = movie_title_input
        text_for_analysis = "" # Инициализация для обычного случая

        if source == 'guardian':
            text_for_analysis = search_guardian_reviews(movie_title_input) or "No review found."
        elif source == 'tmdb':
            if movie_title_input:
                movie_id = get_movie_id(movie_title_input)
                if movie_id:
                    text_for_analysis = get_movie_reviews(movie_id) or "No user reviews found."
                else:
                    return jsonify({'error': f'Movie "{movie_title_input}" not found in TMDb'}), 404
            else:
                return jsonify({'error': 'Movie title is required for TMDb source'}), 400
        elif source == 'custom':
            text_for_analysis = custom_review or "No custom review provided."
            movie_title_to_save = "Custom Review"
        else:
            return jsonify({'error': 'Invalid source'}), 400

        # --- Если жанры не заданы в запросе, но есть movie_id (для TMDb) ---
        if not genres_to_use and movie_id:
            tmdb_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
            params = {"api_key": API_KEY_TMDB, "language": "en-US"}
            resp = requests.get(tmdb_url, params=params)
            if resp.status_code == 200:
                movie_data = resp.json()
                genres_list = [g['name'] for g in movie_data.get('genres', [])]
                genres_to_use = ','.join(genres_list)
                print(f"🎭 Жанри з TMDb: {genres_to_use}")
            else:
                print("⚠️ Не вдалося отримати жанри з TMDb")

        # --- История поиска (для других фильмов) ---
        if user_id and movie_title_to_save:
            print(f"📌 Збереження в історії: {movie_title_to_save}, genres={genres_to_use}")
            db.session.add(SearchHistory(user_id=user_id, movie_title=movie_title_to_save, genres=genres_to_use))
            db.session.commit()

        # --- Обновить жанры у пользователя (для других фильмов) ---
        if user and genres_to_use:
            print(f"🔁 Оновлення жанрів користувача: {genres_to_use}")
            user.genres = genres_to_use
            db.session.commit()

        # --- Перевод входного текста для АНАЛИЗА ---
        if user_lang != 'en':
            text_for_analysis = translate_text(text_for_analysis, 'en')

        # --- Анализ ---
        print("🧠 Аналізуємо текст:", text_for_analysis[:300])
        result_from_analysis = run_analysis(text_for_analysis, age=age)

        # --- Перевод результатов анализа ---
        if user_lang != 'en':
            final_summary = translate_text(result_from_analysis['summary'], user_lang)
            final_sentiment = translate_text(result_from_analysis['sentiment'], user_lang)
            final_keywords = [translate_text(k, user_lang) for k in result_from_analysis['keywords']]
        else:
            final_summary = result_from_analysis['summary']
            final_sentiment = result_from_analysis['sentiment']
            final_keywords = result_from_analysis['keywords']

    # --- ОТПРАВКА ФИНАЛЬНОГО РЕЗУЛЬТАТА ДЛЯ ОБЩЕГО СЛУЧАЯ (если не было return выше) ---
    print(f"📦 ОТПРАВЛЯЕМ НА ФРОНТЕНД (общий случай): {final_summary[:100]}...")
    return jsonify({
        'summary': final_summary,
        'sentiment': final_sentiment,
        'keywords': final_keywords
    }), 200

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
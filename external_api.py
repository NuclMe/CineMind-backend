import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

load_dotenv()
API_KEY_GUARDIAN = os.getenv("API_KEY_GUARDIAN")
API_KEY_TMDB = os.getenv("API_KEY_TMDB")

print(API_KEY_GUARDIAN)


def clean_text(text: str) -> str:
    lines = text.splitlines()
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    return "\n\n".join(cleaned_lines)


def search_guardian_reviews(title: str):
    url = "https://content.guardianapis.com/search"
    params = {
        "q": f"{title} review",
        "section": "film",
        "tag": "film/film",
        "type": "article",
        "show-fields": "body",
        "api-key": API_KEY_GUARDIAN,
        "page-size": 1
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        results = data.get("response", {}).get("results", [])
        if not results:
            return None
        html_content = results[0].get("fields", {}).get("body", "")
        soup = BeautifulSoup(html_content, "html.parser")
        return clean_text(soup.get_text(separator="\n"))
    return None


def get_movie_id(title):
    url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": API_KEY_TMDB, "query": title}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            return results[0]['id']
    return None


def get_movie_reviews(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/reviews"
    params = {"api_key": API_KEY_TMDB, "language": "en-US"}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        reviews = response.json().get("results", [])
        if reviews:
            return reviews[0]['content']
    return None

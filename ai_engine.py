from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from keybert import KeyBERT
from transformers import (
    T5Tokenizer, T5ForConditionalGeneration,
    BartTokenizer, BartForConditionalGeneration
)
import torch

# BART для повного summary
bart_tokenizer = BartTokenizer.from_pretrained('facebook/bart-large-cnn')
bart_model = BartForConditionalGeneration.from_pretrained('facebook/bart-large-cnn')

# Sentiment pipeline
sentiment_pipeline = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

# T5 для коротших summary
t5_tokenizer = T5Tokenizer.from_pretrained("t5-small")
t5_model = T5ForConditionalGeneration.from_pretrained("t5-small")

# Ключові слова
kw_model = KeyBERT(model='all-MiniLM-L6-v2')

# Модель спрощення тексту
simple_tokenizer = AutoTokenizer.from_pretrained("philippelaban/keep_it_simple")
simple_model = AutoModelForCausalLM.from_pretrained("philippelaban/keep_it_simple")

# ✅ Робоча модель для виявлення спойлерів
spoiler_detector = pipeline("text-classification", model="eesuan/imdb-spoiler-distilbert")

# ————————————————————————————————————————————
def remove_spoilers(text, threshold=0.8):
    sentences = text.split('. ')
    non_spoilers = []
    for s in sentences:
        try:
            result = spoiler_detector(s[:512])[0]
            label = result['label']
            score = result['score']
            print(f"{label} ({score:.2f}) → {s}")

            if label == 'LABEL_0' or score < threshold:
                non_spoilers.append(s)
        except Exception as e:
            print("Error:", e)
            continue
    return '. '.join(non_spoilers)


def simplify_with_t5(text, max_len=120):
    input_text = "summarize: " + text
    inputs = t5_tokenizer.encode(input_text, return_tensors="pt", max_length=512, truncation=True)
    summary_ids = t5_model.generate(inputs, max_length=max_len, min_length=30, length_penalty=2.0, num_beams=4, early_stopping=True)
    return t5_tokenizer.decode(summary_ids[0], skip_special_tokens=True)

def summarize_with_bart(text, max_len=200, min_len=100):
    inputs = bart_tokenizer([text], max_length=1024, return_tensors='pt', truncation=True)
    summary_ids = bart_model.generate(inputs['input_ids'], num_beams=4, max_length=max_len, min_length=min_len, length_penalty=2.0, early_stopping=True)
    return bart_tokenizer.decode(summary_ids[0], skip_special_tokens=True)

def simplify_text_with_keepit(text, max_tokens=100):
    inputs = simple_tokenizer.encode(text, return_tensors='pt', truncation=True, max_length=512)
    outputs = simple_model.generate(inputs, max_new_tokens=max_tokens, do_sample=False)
    return simple_tokenizer.decode(outputs[0], skip_special_tokens=True)

# ————————————————————————————————————————————
def adapt_summary_by_age(summary, age):
    if age is None:
        return summary
    if age <= 12:
        return simplify_text_with_keepit(summary, max_tokens=80)
    elif age <= 17:
        return simplify_text_with_keepit(summary, max_tokens=120)
    else:
        return summary

def run_summary_adapted(text, age=None):
    if age is None:
        return summarize_with_bart(text)
    elif age <= 12:
        return simplify_with_t5(text, max_len=80)
    elif age <= 17:
        return simplify_with_t5(text, max_len=120)
    else:
        return summarize_with_bart(text)

# ————————————————————————————————————————————
def run_analysis(review_text, age=None):
    # 1️⃣ Видалення спойлерів
    clean_text = remove_spoilers(review_text)

    # 2️⃣ Адаптивне узагальнення
    adapted_summary = run_summary_adapted(clean_text, age)

    # 3️⃣ Аналіз тональності
    sentiment_result = sentiment_pipeline(adapted_summary)[0]
    sentiment = sentiment_result['label']

    # 4️⃣ Витяг ключових слів
    keywords = kw_model.extract_keywords(
        adapted_summary,
        keyphrase_ngram_range=(1, 2),
        stop_words='english',
        top_n=5
    )
    extracted_keywords = [kw for kw, _ in keywords]

    return {
        'summary': adapted_summary,
        'sentiment': sentiment,
        'keywords': extracted_keywords
    }

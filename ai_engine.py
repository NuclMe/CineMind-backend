from transformers import BartTokenizer, BartForConditionalGeneration, pipeline
from keybert import KeyBERT
import torch

tokenizer = BartTokenizer.from_pretrained('facebook/bart-large-cnn')
model = BartForConditionalGeneration.from_pretrained('facebook/bart-large-cnn')
sentiment_pipeline = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
kw_model = KeyBERT(model='all-MiniLM-L6-v2')

def run_analysis(review_text):
    # 1️⃣ Видалення спойлерів (dummy зараз)
    clean_text_en = review_text

    # 2️⃣ Узагальнення
    inputs = tokenizer([clean_text_en], max_length=1024, return_tensors='pt', truncation=True)
    summary_ids = model.generate(
        inputs['input_ids'],
        num_beams=4,
        max_length=200,
        min_length=150,
        length_penalty=2.0,
        early_stopping=True
    )
    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)

    # 3️⃣ Аналіз настрою
    sentiment_result = sentiment_pipeline(summary[:512])[0]
    sentiment = sentiment_result['label']

    # 4️⃣ Ключові теми
    keywords = kw_model.extract_keywords(summary, keyphrase_ngram_range=(1, 2), stop_words='english', top_n=5)
    extracted_keywords = [kw for kw, score in keywords]

    return {
        'summary': summary,
        'sentiment': sentiment,
        'keywords': extracted_keywords
    }

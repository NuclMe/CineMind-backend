# translation_utils.py
from googletrans import Translator

translator = Translator()

def translate_text(text, target_lang):
    """
    Перекладає текст на вказану мову.
    :param text: рядок тексту
    :param target_lang: цільова мова ('uk', 'en', 'es' тощо)
    :return: перекладений текст
    """
    try:
        translated = translator.translate(text, dest=target_lang)
        return translated.text
    except Exception as e:
        print(f"❌ Translation error: {e}")
        return text

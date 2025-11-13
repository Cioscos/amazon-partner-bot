import re
import logging
import requests
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, InlineQueryHandler, ContextTypes

from env import keyring_get, keyring_initialize
from translations import TranslationService
from languages import TRANSLATIONS

i18n = TranslationService(translations=TRANSLATIONS, default_lang="en")

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    datefmt='%y-%m-%d %H:%M:%S',
    filename='amazon_partner_bot.log'
)

# Headers per simulare un browser reale (evita blocchi)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def txt(key: str, user_lang: str | None = None, **kwargs) -> str:
    return i18n.t(key, lang=user_lang, **kwargs)

def expand_short_url(short_url):
    """
    Espande un URL breve Amazon seguendo i redirect.
    """
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        response = session.get(short_url, allow_redirects=True, timeout=10)
        if response.status_code == 200:
            return response.url
    except requests.RequestException as e:
        logging.error(f"Errore nel seguire il redirect: {e}")
    return None


def extract_asin(url):
    """
    Estrae l'ASIN da un URL Amazon, espandendo link brevi se necessario.
    """
    # Controlla se è un link breve Amazon
    short_patterns = [
        r'amzn\.(?:eu|to|com|mx)/[a-zA-Z0-9]+',
        r'a\.co/[a-zA-Z0-9]+'
    ]

    is_short = any(re.search(pattern, url, re.IGNORECASE) for pattern in short_patterns)

    if is_short:
        expanded_url = expand_short_url(url)
        if expanded_url:
            url = expanded_url
            logging.info(f"URL espanso: {expanded_url}")

    # Pattern per estrarre l'ASIN da URL completi
    patterns = [
        r'/dp/([A-Z0-9]{10})',  # Formato standard: /dp/ASIN
        r'/gp/product/([A-Z0-9]{10})',  # Formato alternativo: /gp/product/ASIN
        r'/product/([A-Z0-9]{10})',  # Formato: /product/ASIN
        r'(?:amazon\.[a-z.]+/|amzn\.com/)([A-Z0-9]{10})',  # ASIN diretto dopo dominio
    ]

    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def create_affiliate_link(asin, domain="amazon.it"):
    """
    Crea un link di affiliazione Amazon.
    """
    return f"https://www.{domain}/dp/{asin}?tag={keyring_get('Partner')}"


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestisce le query inline.
    """
    query = update.inline_query.query

    # Get user lang
    user_lang = update.effective_user.language_code

    if not query:
        return

    # Verifica se l'input contiene "amazon" o domini brevi
    if not any(domain in query.lower() for domain in ["amazon", "amzn.", "a.co"]):
        results = [
            InlineQueryResultArticle(
                id="error",
                title=txt('bot.error.url_error.title', user_lang),
                description=txt('bot.error.url_error.description', user_lang),
                input_message_content=InputTextMessageContent(txt('bot.error.url_error.input_message_content', user_lang))
            )
        ]
        await update.inline_query.answer(results)
        return

    # Estrai l'ASIN dall'URL
    asin = extract_asin(query)

    if not asin:
        results = [
            InlineQueryResultArticle(
                id="error",
                title=txt('bot.error.asin_error.title', user_lang),
                description=txt('bot.error.asin_error.description', user_lang),
                input_message_content=InputTextMessageContent(
                    txt('bot.error.asin_error.input_message_content', user_lang))
            )
        ]
        await update.inline_query.answer(results)
        return

    # Determina il dominio Amazon dall'URL originale o espanso
    domain = "amazon.it"
    if ".com" in query:
        domain = "amazon.com"
    elif ".de" in query:
        domain = "amazon.de"
    elif ".fr" in query:
        domain = "amazon.fr"
    elif ".es" in query:
        domain = "amazon.es"
    elif ".co.uk" in query:
        domain = "amazon.co.uk"
    elif "amzn.eu" in query:
        domain = "amazon.it"  # Default per EU, ma può variare [web:19]

    # Crea il link di affiliazione
    affiliate_link = create_affiliate_link(asin, domain)

    # Prepara i risultati
    results = [
        InlineQueryResultArticle(
            id=asin,
            title=txt('bot.info.partner_link_generated.title', user_lang),
            description=txt('bot.info.partner_link_generated.description', user_lang, asin=asin, domain=domain),
            input_message_content=InputTextMessageContent(txt('bot.info.partner_link_generated.input_message_content', user_lang, affiliate_link=affiliate_link)),
            thumbnail_url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Amazon_logo.svg/200px-Amazon_logo.svg.png"
        ),
        InlineQueryResultArticle(
            id=f"{asin}_solo_link",
            title=txt('bot.info.only_asin_link.title', user_lang),
            description=txt('bot.info.only_asin_link.description', user_lang),
            input_message_content=InputTextMessageContent(
                affiliate_link
            )
        )
    ]

    await update.inline_query.answer(results, cache_time=10)


def main():
    """
    Funzione principale per avviare il bot.
    """
    # Initialize the keyring
    if not keyring_initialize():
        exit(0xFF)

    # Crea l'applicazione
    application = (Application.builder()
                   .token(keyring_get('Telegram'))
                   .build()
    )

    # Aggiungi l'handler per le query inline
    application.add_handler(InlineQueryHandler(inline_query_handler))

    # Avvia il bot
    logging.info("Bot avviato!")
    application.run_polling(allowed_updates=["inline_query"])


if __name__ == "__main__":
    main()

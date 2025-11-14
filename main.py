import re
import logging
import requests
from requests.adapters import HTTPAdapter
import urllib.parse
from functools import lru_cache
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, InlineQueryHandler, ContextTypes
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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

# Headers per simulare un browser reale
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


# Configurazione sessione HTTP globale
class TimeoutHTTPAdapter(HTTPAdapter):
    """Adapter HTTP con timeout predefinito."""

    def __init__(self, timeout=10, *args, **kwargs):
        self.timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        kwargs.setdefault('timeout', self.timeout)
        return super().send(request, **kwargs)


# Crea sessione globale
HTTP_SESSION = requests.Session()
HTTP_SESSION.headers.update(HEADERS)
HTTP_SESSION.mount("http://", TimeoutHTTPAdapter(timeout=10))
HTTP_SESSION.mount("https://", TimeoutHTTPAdapter(timeout=10))

# Rate limiting: max 10 query per utente al minuto
user_queries = defaultdict(list)
MAX_QUERIES_PER_MINUTE = 10

# Metriche del bot
bot_metrics = {
    'total_queries': 0,
    'successful_conversions': 0,
    'failed_extractions': 0,
    'rate_limited': 0,
    'domains': Counter()
}


def txt(key: str, user_lang: str | None = None, **kwargs) -> str:
    """Wrapper per il servizio di traduzione."""
    return i18n.t(key, lang=user_lang, **kwargs)


def track_metric(metric_name: str, value=1):
    """Traccia metriche del bot."""
    if metric_name in bot_metrics:
        if isinstance(bot_metrics[metric_name], Counter):
            bot_metrics[metric_name][value] += 1
        else:
            bot_metrics[metric_name] += value

    # Log metriche ogni 100 query
    if bot_metrics['total_queries'] % 100 == 0:
        logging.info(f"Metriche bot: {dict(bot_metrics)}")


async def check_rate_limit(user_id: int) -> bool:
    """Verifica il rate limiting per utente."""
    now = datetime.now()
    cutoff = now - timedelta(minutes=1)

    # Rimuovi query vecchie
    user_queries[user_id] = [ts for ts in user_queries[user_id] if ts > cutoff]

    if len(user_queries[user_id]) >= MAX_QUERIES_PER_MINUTE:
        track_metric('rate_limited')
        return False

    user_queries[user_id].append(now)
    return True


def is_valid_amazon_url(url: str) -> bool:
    """Valida se l'URL è un URL Amazon legittimo."""
    try:
        parsed = urllib.parse.urlparse(url)
        valid_domains = [
            'amazon.com', 'amazon.it', 'amazon.de',
            'amazon.fr', 'amazon.es', 'amazon.co.uk',
            'amzn.to', 'amzn.eu', 'a.co', 'amzn.com'
        ]
        return any(domain in parsed.netloc.lower() for domain in valid_domains)
    except Exception as e:
        logging.error(f"Errore validazione URL: {e}")
        return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, requests.Timeout))
)
def expand_short_url_with_retry(short_url: str) -> str | None:
    """
    Espande un URL breve Amazon seguendo i redirect con retry automatico.
    """
    try:
        response = HTTP_SESSION.get(short_url, allow_redirects=True)
        response.raise_for_status()
        if response.status_code == 200:
            logging.info(f"URL espanso con successo: {short_url} -> {response.url}")
            return response.url
    except requests.RequestException as e:
        logging.error(f"Errore nell'espandere l'URL {short_url}: {e}")
        raise
    return None


@lru_cache(maxsize=1000)
def expand_short_url_cached(short_url: str) -> str | None:
    """
    Versione con cache dell'espansione URL.
    """
    try:
        return expand_short_url_with_retry(short_url)
    except Exception as e:
        logging.error(f"Fallito l'espansione dell'URL dopo retry: {e}")
        return None


def extract_domain(url: str) -> str:
    """
    Estrae il dominio Amazon corretto dall'URL.
    """
    domain_patterns = {
        r'amazon\.com': 'amazon.com',
        r'amazon\.it': 'amazon.it',
        r'amazon\.de': 'amazon.de',
        r'amazon\.fr': 'amazon.fr',
        r'amazon\.es': 'amazon.es',
        r'amazon\.co\.uk': 'amazon.co.uk',
    }

    for pattern, domain in domain_patterns.items():
        if re.search(pattern, url, re.IGNORECASE):
            return domain

    return "amazon.it"  # Default


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
        expanded_url = expand_short_url_cached(url)
        if expanded_url:
            url = expanded_url
            logging.info(f"URL espanso da cache: {expanded_url}")

    # Pattern per estrarre l'ASIN da URL completi
    patterns = [
        r'/dp/([A-Z0-9]{10})',
        r'/gp/product/([A-Z0-9]{10})',
        r'/product/([A-Z0-9]{10})',
        r'(?:amazon\.[a-z.]+/|amzn\.com/)([A-Z0-9]{10})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            asin = match.group(1)
            logging.info(f"ASIN estratto: {asin}")
            return asin

    logging.warning(f"Impossibile estrarre ASIN da: {url}")
    return None


def create_affiliate_link(asin: str, domain: str = "amazon.it") -> str:
    """
    Crea un link di affiliazione Amazon.
    """
    partner_tag = keyring_get('Partner')
    affiliate_link = f"https://www.{domain}/dp/{asin}?tag={partner_tag}"
    logging.info(f"Link di affiliazione creato: {affiliate_link}")
    return affiliate_link


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestisce le query inline con validazione, rate limiting e metriche.
    """
    query = update.inline_query.query
    user_id = update.effective_user.id
    user_lang = update.effective_user.language_code

    # Traccia query totali
    track_metric('total_queries')

    if not query:
        return

    # Rate limiting
    if not await check_rate_limit(user_id):
        results = [
            InlineQueryResultArticle(
                id="rate_limit",
                title=txt('bot.error.rate_limit.title', user_lang),
                description=txt('bot.error.rate_limit.description', user_lang, max_queries=MAX_QUERIES_PER_MINUTE),
                input_message_content=InputTextMessageContent(
                    txt('bot.error.rate_limit.input_message_content', user_lang, max_queries=MAX_QUERIES_PER_MINUTE)
                )
            )
        ]
        await update.inline_query.answer(results, cache_time=5)
        return

    # Validazione URL
    if not is_valid_amazon_url(query):
        results = [
            InlineQueryResultArticle(
                id="error",
                title=txt('bot.error.url_error.title', user_lang),
                description=txt('bot.error.url_error.description', user_lang),
                input_message_content=InputTextMessageContent(
                    txt('bot.error.url_error.input_message_content', user_lang)
                )
            )
        ]
        await update.inline_query.answer(results, cache_time=10)
        return

    # Estrai l'ASIN dall'URL
    asin = extract_asin(query)

    if not asin:
        track_metric('failed_extractions')
        results = [
            InlineQueryResultArticle(
                id="error",
                title=txt('bot.error.asin_error.title', user_lang),
                description=txt('bot.error.asin_error.description', user_lang),
                input_message_content=InputTextMessageContent(
                    txt('bot.error.asin_error.input_message_content', user_lang)
                )
            )
        ]
        await update.inline_query.answer(results, cache_time=10)
        return

    # Determina il dominio Amazon dall'URL
    domain = extract_domain(query)
    track_metric('domains', domain)
    track_metric('successful_conversions')

    # Crea il link di affiliazione
    affiliate_link = create_affiliate_link(asin, domain)

    # Prepara i risultati
    results = [
        InlineQueryResultArticle(
            id=asin,
            title=txt('bot.info.partner_link_generated.title', user_lang),
            description=txt('bot.info.partner_link_generated.description', user_lang, asin=asin, domain=domain),
            input_message_content=InputTextMessageContent(
                txt('bot.info.partner_link_generated.input_message_content', user_lang, affiliate_link=affiliate_link)
            ),
            thumbnail_url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Amazon_logo.svg/200px-Amazon_logo.svg.png"
        ),
        InlineQueryResultArticle(
            id=f"{asin}_solo_link",
            title=txt('bot.info.only_asin_link.title', user_lang),
            description=txt('bot.info.only_asin_link.description', user_lang),
            input_message_content=InputTextMessageContent(affiliate_link)
        )
    ]

    await update.inline_query.answer(results, cache_time=10)


def main():
    """
    Funzione principale per avviare il bot.
    """
    # Initialize the keyring
    if not keyring_initialize():
        logging.error("Inizializzazione keyring fallita")
        exit(0xFF)

    # Crea l'applicazione
    application = (Application.builder()
                   .token(keyring_get('Telegram'))
                   .build()
                   )

    # Aggiungi l'handler per le query inline
    application.add_handler(InlineQueryHandler(inline_query_handler))

    # Avvia il bot
    logging.info("Bot avviato con successo!")
    logging.info(f"Rate limit: {MAX_QUERIES_PER_MINUTE} query/minuto per utente")
    logging.info(f"Cache LRU: 1000 URL")

    try:
        application.run_polling(allowed_updates=["inline_query"])
    except KeyboardInterrupt:
        logging.info("Bot arrestato dall'utente")
    except Exception as e:
        logging.error(f"Errore critico nel bot: {e}")
        raise
    finally:
        # Log metriche finali
        logging.info(f"Metriche finali: {dict(bot_metrics)}")


if __name__ == "__main__":
    main()

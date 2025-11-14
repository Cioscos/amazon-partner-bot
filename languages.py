from typing import Dict

MessagesType = Dict[
    str,  # language: "en" | "it"
    Dict[
        str,  # "bot"
        Dict[
            str,  # "error" | "info"
            Dict[
                str,  # "url_error" | "asin_error" | "partner_link_generated" | "only_asin_link"
                Dict[
                    str,  # "title" | "description" | "input_message_content"
                    str,  # valore della stringa
                ],
            ],
        ],
    ],
]

TRANSLATIONS: MessagesType = {
    "en": {
        "bot": {
            "error": {
                "url_error": {
                    "title": "⚠️ Invalid URL",
                    "description": "Please enter a valid Amazon URL",
                    "input_message_content": "❌ The URL provided does not appear to be an Amazon link."
                },
                "asin_error": {
                    "title" : "⚠️ ASIN not found",
                    "description": "Unable to extract ASIN from URL",
                    "input_message_content": "❌ I was unable to extract the ASIN from the URL provided.\n"
                        "Make sure it's a valid Amazon link (even a short one)."
                },
                "rate_limit": {
                    "title": "⚠️ Too fast!",
                    "description": "Maximum {max_queries} requests per minute. Try again soon.",
                    "input_message_content": "⚠️ You have exceeded the limit of {max_queries} requests per minute. Please wait a moment."
                }
            },
            "info": {
                "partner_link_generated": {
                    "title": "🔗 Affiliate link generated",
                    "description": "ASIN: {asin} | Domain: {domain}",
                    "input_message_content": "🔗 Amazon Affiliate Link:\n\n{affiliate_link}\n\n"
                },
                "only_asin_link": {
                    "title": "📋 Send only the link",
                    "description": "Without additional text"
                }
            }
        }
    },
    "it": {
        "bot": {
            "error": {
                "url_error": {
                    "title": "⚠️ URL non valido",
                    "description": "Inserisci un URL Amazon valido",
                    "input_message_content": "❌ L'URL fornito non sembra essere un link Amazon."
                },
                "asin_error": {
                    "title" : "⚠️ ASIN non trovato",
                    "description": "Non riesco a trovare l'ASIN nell'URL",
                    "input_message_content": "❌ Non sono riuscito a estrarre l'ASIN dall'URL fornito.\n"
                        "Assicurati che sia un link Amazon valido (anche breve)."
                },
                "rate_limit": {
                    "title": "⚠️ Troppo veloce!",
                    "description": "Massimo {max_queries} richieste al minuto. Riprova tra poco.",
                    "input_message_content": "⚠️ Hai superato il limite di {max_queries} richieste al minuto. Attendi un momento."
                }
            },
            "info": {
                "partner_link_generated": {
                    "title": "🔗 Link di affiliazione generato",
                    "description": "ASIN: {asin} | Dominio: {domain}",
                    "input_message_content": "🔗 Link di affiliazione Amazon:\n\n{affiliate_link}\n\n"
                },
                "only_asin_link": {
                    "title": "📋 Invia solo il link",
                    "description": "Senza testo aggiuntivo"
                }
            }
        }
    }
}

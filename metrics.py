import json
import threading
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class MetricsManager:
    """Gestisce le metriche del bot con persistenza in tempo reale."""

    def __init__(self, filepath: str = "bot_metrics.json"):
        self.filepath = Path(filepath)
        self.lock = threading.Lock()
        self.metrics = {
            'total_queries': 0,
            'successful_conversions': 0,
            'failed_extractions': 0,
            'rate_limited': 0,
            'domains': {},
            'last_updated': None,
            'start_time': datetime.now().isoformat()
        }
        self._load_metrics()

    def _load_metrics(self):
        """Carica le metriche esistenti dal file."""
        if self.filepath.exists():
            try:
                with self.lock:
                    with open(self.filepath, 'r', encoding='utf-8') as f:
                        loaded = json.load(f)
                        self.metrics.update(loaded)
                        logger.info(f"Metriche caricate da {self.filepath}")
            except Exception as e:
                logger.warning(f"Impossibile caricare metriche: {e}")

    def _save_metrics(self):
        """Salva le metriche su file in modo atomico."""
        try:
            self.metrics['last_updated'] = datetime.now().isoformat()

            # Scrittura atomica: scrivi su file temporaneo poi rinomina
            temp_file = self.filepath.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.metrics, f, indent=2, ensure_ascii=False)

            # Rinomina atomicamente
            temp_file.replace(self.filepath)

        except Exception as e:
            logger.error(f"Errore nel salvare metriche: {e}")

    def track(self, metric_name: str, value=1):
        """Traccia una metrica e salva immediatamente."""
        with self.lock:
            if metric_name == 'domains':
                # Per i domini usiamo un dizionario invece di Counter
                if value not in self.metrics['domains']:
                    self.metrics['domains'][value] = 0
                self.metrics['domains'][value] += 1
            elif metric_name in self.metrics:
                self.metrics[metric_name] += value

            self._save_metrics()

            # Log ogni 100 query
            if self.metrics['total_queries'] % 100 == 0:
                logger.info(f"Metriche bot: {self.metrics}")

    def get_metrics(self) -> dict:
        """Restituisce una copia delle metriche correnti."""
        with self.lock:
            return self.metrics.copy()

    def reset_metrics(self):
        """Reset delle metriche (mantiene start_time)."""
        with self.lock:
            start_time = self.metrics.get('start_time')
            self.metrics = {
                'total_queries': 0,
                'successful_conversions': 0,
                'failed_extractions': 0,
                'rate_limited': 0,
                'domains': {},
                'last_updated': None,
                'start_time': start_time or datetime.now().isoformat()
            }
            self._save_metrics()
            logger.info("Metriche resettate")

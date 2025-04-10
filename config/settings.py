"""
Arquivo de configurações centralizadas para o OLX Research Scraper.
Contém constantes e parâmetros configuráveis para a aplicação.
"""

import os

# Configurações do banco de dados
DATABASE_NAME = os.environ.get("DATABASE_NAME", "data/olx_precos.db")
DATABASE_URL = os.environ.get("DATABASE_URL", None)  # Para PostgreSQL/MySQL (opcional)

# Configurações de preços (em Reais)
MIN_PRICE = float(os.environ.get("MIN_PRICE", "50"))
MAX_PRICE = float(os.environ.get("MAX_PRICE", "100000"))

# Configurações de scraping
DEFAULT_PAGES = int(os.environ.get("DEFAULT_PAGES", "3"))
BASE_URL = "https://www.olx.com.br"
DEFAULT_STATE = os.environ.get("DEFAULT_STATE", "estado-go")  # Estado padrão para pesquisa
TIMEOUT = int(os.environ.get("TIMEOUT", "20"))  # Timeout para requisições em segundos

# Configurações de delays (em segundos)
MIN_DELAY = float(os.environ.get("MIN_DELAY", "0.2"))
MAX_DELAY = float(os.environ.get("MAX_DELAY", "0.5"))

# Configurações de User Agent
USER_AGENT_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://www.olx.com.br/',
    'DNT': '1',
    'Upgrade-Insecure-Requests': '1'
}

# Configurações de logging
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Seletores CSS para scraping
CSS_SELECTORS = {
    'listings': 'section[data-ds-component="DS-AdCard"]',
    'price': 'h3[data-ds-component="DS-Text"].olx-ad-card__price',
    'title': 'h2[data-ds-component="DS-Text"].olx-ad-card__title',
    'link': 'a'
}

# Formato para matches de regex
PRICE_REGEX = r'R\$\s*([\d.,]+)'

# Configurações de análise
HISTOGRAM_BINS = int(os.environ.get("HISTOGRAM_BINS", "20"))
FIGURE_WIDTH = int(os.environ.get("FIGURE_WIDTH", "10"))
FIGURE_HEIGHT = int(os.environ.get("FIGURE_HEIGHT", "5"))

# Configurações do Redis
REDIS_ENABLED = os.environ.get("REDIS_ENABLED", "True").lower() in ("true", "1", "yes")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
REDIS_SSL = os.environ.get("REDIS_SSL", "False").lower() in ("true", "1", "yes")
REDIS_TTL = int(os.environ.get("REDIS_TTL", "86400"))  # 24 horas em segundos

# Configurações de Proxies
PROXY_ENABLED = os.environ.get("PROXY_ENABLED", "False").lower() in ("true", "1", "yes")
PROXIES = os.environ.get("PROXIES", "").split(",") if os.environ.get("PROXIES") else []
PROXY_TEST_URL = os.environ.get("PROXY_TEST_URL", "https://www.olx.com.br")
PROXY_MIN_SUCCESS_RATE = float(os.environ.get("PROXY_MIN_SUCCESS_RATE", "0.5"))
PROXY_COOLDOWN_TIME = int(os.environ.get("PROXY_COOLDOWN_TIME", "300"))  # 5 minutos

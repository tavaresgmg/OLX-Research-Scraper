"""
Componente principal de scraping para o OLX Research Scraper.

Implementa funcionalidades para extrair dados de anúncios da OLX
de forma robusta e resiliente.
"""

import asyncio
import os
import re
import sys
import time
import urllib.parse
from typing import Dict, List, Optional, Set, Any, Tuple

import aiohttp
from aiohttp.client_exceptions import ClientError, ClientConnectorError, ServerDisconnectedError
from fake_useragent import UserAgent

# Importando os componentes do projeto
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Importar configurações usando caminho correto
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
sys.path.append(CONFIG_PATH)
from settings import (
    BASE_URL, DEFAULT_STATE, TIMEOUT, MIN_PRICE, MAX_PRICE,
    USER_AGENT_HEADERS, PRICE_REGEX,
    # Novas configurações
    REDIS_ENABLED, REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, REDIS_SSL, REDIS_TTL,
    PROXY_ENABLED, PROXIES, PROXY_TEST_URL, PROXY_MIN_SUCCESS_RATE, PROXY_COOLDOWN_TIME
)

from src.utils.helpers import setup_logging, retry, random_delay, safe_float_conversion
from src.utils.selectors import OLXListingSelector, PageStructureChangedError
from src.services.database import ProductRepository
# Novos imports
from src.utils.cache import RedisCache
from src.services.proxy import ProxyManager, ProxyError

# Configuração do logger
logger = setup_logging(__name__)

class ScraperError(Exception):
    """Exceção base para erros do scraper."""
    pass

class OLXScraper:
    """
    Scraper para extração de dados de anúncios da OLX.

    Implementa funcionalidades para extrair preços, títulos e URLs de anúncios
    com tratamento robusto de erros e anti-bloqueio.
    """

    def __init__(self,
                 state: str = DEFAULT_STATE,
                 min_price: float = MIN_PRICE,
                 max_price: float = MAX_PRICE,
                 timeout: int = TIMEOUT,
                 repository: Optional[ProductRepository] = None,
                 use_cache: bool = True,
                 # Novos parâmetros
                 redis_cache: Optional[RedisCache] = None,
                 proxy_manager: Optional[ProxyManager] = None):
        """
        Inicializa o scraper com as configurações desejadas.

        Args:
            state: Sigla do estado para pesquisa (ex: 'estado-go', 'estado-sp').
            min_price: Preço mínimo para considerar válido (em Reais).
            max_price: Preço máximo para considerar válido (em Reais).
            timeout: Timeout para requisições HTTP (em segundos).
            repository: Instância do repositório de produtos para persistência.
            use_cache: Se True, utiliza cache para evitar requisições duplicadas.
            redis_cache: Instância do RedisCache para caching distribuído.
            proxy_manager: Instância do ProxyManager para rotação de proxies.
        """
        self.state = state
        self.min_price = min_price
        self.max_price = max_price
        self.timeout = timeout
        self.repository = repository
        self.use_cache = use_cache
        self.session = None
        self.selector = OLXListingSelector()
        self.logger = logger

        # Inicializa o cache
        self.redis_cache = redis_cache
        if self.redis_cache is None and use_cache and REDIS_ENABLED:
            # Criar instância padrão do Redis
            self.logger.info("Inicializando cache Redis")
            self.redis_cache = RedisCache(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                ssl=REDIS_SSL,
                ttl=REDIS_TTL
            )

        # Cache de memória de backup (para caso de falha no Redis)
        self._url_cache: Dict[str, str] = {}
        self._processed_urls: Set[str] = set()

        # Inicializa o gerenciador de proxies
        self.proxy_manager = proxy_manager
        if self.proxy_manager is None and PROXY_ENABLED and PROXIES:
            self.logger.info("Inicializando gerenciador de proxies")
            self.proxy_manager = ProxyManager(
                proxies=PROXIES,
                test_url=PROXY_TEST_URL,
                min_success_rate=PROXY_MIN_SUCCESS_RATE,
                cooldown_time=PROXY_COOLDOWN_TIME
            )

    async def __aenter__(self):
        """Método para uso com context manager (async with)."""
        if self.session is None:
            # Configura a sessão com ou sem proxy
            self.session = await self._create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Garante que a sessão seja fechada ao sair do context manager."""
        if self.session:
            await self.session.close()
            self.session = None

    async def _create_session(self):
        """
        Cria uma sessão HTTP com configurações apropriadas.

        Returns:
            aiohttp.ClientSession: Sessão configurada.
        """
        # Obtém proxy se disponível
        proxy = self._get_proxy()

        if proxy:
            # Configura a sessão com proxy
            self.logger.info(f"Usando proxy: {proxy}")
            connector = aiohttp.TCPConnector(ssl=False)
            session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                connector=connector
            )
            session.proxy = proxy  # Armazenamos para referência
            return session
        else:
            # Sessão sem proxy
            self.logger.debug("Criando sessão sem proxy")
            return aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )

    def _get_proxy(self) -> Optional[str]:
        """
        Obtém um proxy do gerenciador de proxies.

        Returns:
            String do proxy ou None se não disponível.
        """
        if not self.proxy_manager:
            return None

        # Atualiza cooldowns antes de obter um proxy
        self.proxy_manager.update_cooldowns()
        return self.proxy_manager.get_proxy()

    def _get_headers(self) -> Dict[str, str]:
        """
        Gera cabeçalhos HTTP com User-Agent aleatório.

        Returns:
            Dicionário com cabeçalhos HTTP.
        """
        ua = UserAgent()
        headers = USER_AGENT_HEADERS.copy()
        headers['User-Agent'] = ua.random
        return headers

    def _build_search_url(self, product_name: str, page: int = 1) -> str:
        """
        Constrói a URL de pesquisa para um produto na OLX.

        Args:
            product_name: Nome do produto para pesquisa.
            page: Número da página de resultados.

        Returns:
            URL formatada para a pesquisa.
        """
        # Codifica o termo de pesquisa para URL
        encoded_product = urllib.parse.quote(product_name)

        # Constrói a URL
        url = f"{BASE_URL}/{self.state}?q={encoded_product}&o={page}"

        self.logger.debug(f"URL de pesquisa construída: {url}")
        return url

    def _get_cache_key(self, url: str) -> str:
        """
        Gera uma chave de cache para a URL.

        Args:
            url: URL a ser convertida em chave de cache.

        Returns:
            Chave para uso no cache.
        """
        return f"html:{url}"

    @retry(max_tries=3, delay=2.0, backoff=2.0,
           exceptions=(ClientError, ClientConnectorError,
                      ServerDisconnectedError, asyncio.TimeoutError, ProxyError))
    async def _fetch_page(self, url: str) -> Optional[str]:
        """
        Busca o conteúdo HTML de uma página com retry logic.

        Args:
            url: URL da página a ser buscada.

        Returns:
            Conteúdo HTML da página ou None em caso de falha.
        """
        # Verifica o cache Redis
        cache_key = self._get_cache_key(url)

        if self.use_cache:
            # Tenta Redis primeiro
            if self.redis_cache:
                cached_html = self.redis_cache.get(cache_key)
                if cached_html:
                    self.logger.debug(f"Cache hit no Redis para URL: {url}")
                    return cached_html

            # Fallback para cache em memória
            if url in self._url_cache:
                self.logger.debug(f"Cache hit em memória para URL: {url}")
                return self._url_cache[url]

        if self.session is None:
            self.session = await self._create_session()

        headers = self._get_headers()
        proxy = getattr(self.session, 'proxy', None)

        self.logger.info(f"Buscando página: {url}")
        try:
            # Usa o proxy da sessão se disponível
            proxy_option = {'proxy': proxy} if proxy else {}

            async with self.session.get(url, headers=headers, **proxy_option) as response:
                response.raise_for_status()
                html = await response.text()

                # Armazena no Redis se disponível
                if self.use_cache:
                    if self.redis_cache:
                        self.redis_cache.set(cache_key, html)
                    # Backup no cache de memória
                    self._url_cache[url] = html

                # Reporta sucesso do proxy se usado
                if proxy and self.proxy_manager:
                    self.proxy_manager.report_success(proxy)

                return html

        except Exception as e:
            # Reporta falha do proxy se usado
            if proxy and self.proxy_manager:
                self.proxy_manager.report_failure(proxy)

            self.logger.error(f"Erro ao buscar página {url}: {e}")

            # Recria a sessão para tentar com outro proxy
            if self.session:
                await self.session.close()
                self.session = await self._create_session()

            raise

    async def _extract_price(self, price_text: str) -> Optional[float]:
        """
        Extrai o valor numérico de um texto de preço.

        Args:
            price_text: Texto contendo o preço (ex: "R$ 1.299,00").

        Returns:
            Valor numérico do preço ou None se não puder ser extraído.
        """
        if not price_text:
            self.logger.debug("Texto de preço vazio")
            return None

        # Tenta extrair o valor com regex
        self.logger.debug(f"Aplicando regex ao texto do preço: '{price_text}'")
        price_match = re.search(PRICE_REGEX, price_text)
        if not price_match:
            self.logger.debug(f"Formato de preço não reconhecido: {price_text}")

            # Tentar extrair manualmente removendo "R$" e caracteres não numéricos
            clean_price = price_text.replace("R$", "").strip()
            self.logger.debug(f"Tentativa manual 1 - Preço limpo: '{clean_price}'")

            # Substituir pontos e vírgulas
            clean_price = clean_price.replace(".", "").replace(",", ".")
            self.logger.debug(f"Tentativa manual 2 - Preço com substituição de separadores: '{clean_price}'")

            # Tentar extrair apenas números
            digits_only = ''.join(c for c in clean_price if c.isdigit() or c == '.')
            self.logger.debug(f"Tentativa manual 3 - Apenas dígitos: '{digits_only}'")

            try:
                price = float(digits_only)
                self.logger.debug(f"Extração manual bem-sucedida: {price}")
                return price
            except (ValueError, TypeError):
                self.logger.debug("Extração manual falhou")
                return None

        price_str = price_match.group(1)
        self.logger.debug(f"Texto de preço extraído pelo regex: '{price_str}'")

        price = safe_float_conversion(price_str)
        self.logger.debug(f"Preço após conversão: {price}")

        if price is None:
            self.logger.debug(f"Não foi possível converter o preço: {price_str}")
            return None

        # Valida o preço dentro da faixa aceitável
        if self.min_price <= price <= self.max_price:
            return price
        else:
            self.logger.debug(f"Preço fora da faixa aceitável: R$ {price:.2f}")
            return None

    async def _process_listing(self, listing_data: Dict[str, Any], product_name: str) -> Optional[float]:
        """
        Processa dados de um anúncio e armazena no repositório.

        Args:
            listing_data: Dados do anúncio (título, preço, url).
            product_name: Nome do produto pesquisado.

        Returns:
            Preço extraído ou None se não for válido.
        """
        if not listing_data:
            return None

        url = listing_data.get('url', '')
        title = listing_data.get('title', 'Sem título')
        price_text = listing_data.get('price_text')

        self.logger.debug(f"Processando anúncio: {title}")
        self.logger.debug(f"Texto do preço original: {price_text}")

        # Evita processar URLs duplicadas
        if url in self._processed_urls:
            self.logger.debug(f"URL já processada: {url}")
            return None

        self._processed_urls.add(url)

        # Extracting price value directly here for debugging
        if price_text:
            # Detecta e trata o formato de parcelas (ex: "3x de R$ 333,33")
            if "x de R$" in price_text:
                parts = price_text.split("x de R$")
                if len(parts) > 1:
                    try:
                        parcelas = int(parts[0].strip())
                        valor_parcela = parts[1].strip()
                        valor_parcela_clean = valor_parcela.replace(".", "").replace(",", ".")
                        direct_value = float(valor_parcela_clean) * parcelas
                        self.logger.debug(f"Extraído diretamente do formato parcelado: {direct_value}")
                    except (ValueError, TypeError):
                        self.logger.debug(f"Falha ao extrair preço parcelado diretamente: {price_text}")

            # Remove o símbolo da moeda e espaços
            price_clean = price_text.replace("R$", "").strip()
            self.logger.debug(f"Preço após remover R$: {price_clean}")

            # Substitui pontos por nada (separador de milhar) e vírgula por ponto (separador decimal)
            price_clean = price_clean.replace(".", "").replace(",", ".")
            self.logger.debug(f"Preço após normalizar separadores: {price_clean}")

            # Extrai apenas números e ponto decimal
            match = re.search(r'(\d+\.?\d*)', price_clean)
            if match:
                direct_value = float(match.group(1))
                self.logger.debug(f"Valor extraído diretamente: {direct_value}")
                if self.min_price <= direct_value <= self.max_price:
                    self.logger.info(f"Anúncio válido: R$ {direct_value:.2f} - {title} - {url}")
                    # Armazena no repositório se disponível
                    if self.repository:
                        try:
                            self.repository.insert_product(product_name, direct_value, url, title)
                        except Exception as e:
                            self.logger.error(f"Erro ao armazenar produto no banco de dados: {e}")
                    return direct_value
                else:
                    self.logger.debug(f"Preço fora da faixa: {direct_value} (min={self.min_price}, max={self.max_price})")
            else:
                self.logger.debug(f"Não foi possível extrair número do texto: {price_clean}")

        # Extrai e valida o preço usando o método padrão
        price = await self._extract_price(price_text)
        self.logger.debug(f"Preço extraído pelo método padrão: {price}")

        if price is None:
            self.logger.debug(f"Preço inválido para o anúncio: {title}")
            return None

        # Verifica se o preço está dentro da faixa aceitável
        if not (self.min_price <= price <= self.max_price):
            self.logger.debug(f"Preço fora da faixa aceitável: R$ {price:.2f} (min: {self.min_price}, max: {self.max_price})")
            return None

        self.logger.info(f"Anúncio válido: R$ {price:.2f} - {title} - {url}")

        # Armazena no repositório se disponível
        if self.repository:
            try:
                self.repository.insert_product(product_name, price, url, title)
            except Exception as e:
                self.logger.error(f"Erro ao armazenar produto no banco de dados: {e}")

        return price

    async def scrape_page(self, product_name: str, page: int) -> List[float]:
        """
        Raspa uma página de resultados para um produto.

        Args:
            product_name: Nome do produto pesquisado.
            page: Número da página de resultados.

        Returns:
            Lista de preços válidos encontrados na página.
        """
        url = self._build_search_url(product_name, page)
        prices = []

        try:
            html = await self._fetch_page(url)
            if not html:
                self.logger.warning(f"Não foi possível obter o HTML da página {page}")
                return prices

            # Tenta extrair anúncios com seletores principais ou alternativos
            try:
                listings = self.selector.extract_listings(html)
                self.logger.debug(f"Anúncios extraídos: {len(listings)}")

                # DEBUG: Imprimir informações de cada anúncio
                for i, listing in enumerate(listings[:5]):  # Limita a 5 para não sobrecarregar logs
                    self.logger.debug(f"Anúncio #{i+1}: Título={listing.get('title')}, Preço={listing.get('price_text')}, URL={listing.get('url')}")

            except PageStructureChangedError:
                self.logger.warning("Estrutura da página mudou, tentando seletores alternativos")
                listings = self.selector.try_alternative_selectors(html)

            if not listings:
                self.logger.warning(f"Nenhum anúncio encontrado na página {page}")
                return prices

            self.logger.info(f"Encontrados {len(listings)} anúncios na página {page}")

            # Processa cada anúncio
            for listing_data in listings:
                price = await self._process_listing(listing_data, product_name)
                if price:
                    prices.append(price)

                # Pequeno delay entre processamentos para evitar sobrecarga
                await asyncio.sleep(0.05)

            return prices

        except Exception as e:
            self.logger.error(f"Erro ao raspar a página {page} para '{product_name}': {e}")
            return prices

    async def scrape_product(self, product_name: str, max_pages: int = 3) -> List[float]:
        """
        Raspa várias páginas de resultados para um produto.

        Args:
            product_name: Nome do produto pesquisado.
            max_pages: Número máximo de páginas a serem raspadas.

        Returns:
            Lista com todos os preços válidos encontrados.
        """
        all_prices = []

        async with self:  # Usa context manager para gerenciar a sessão
            tasks = []

            # Cria tasks para cada página
            for page in range(1, max_pages + 1):
                self.logger.info(f"Agendando raspagem para '{product_name}', página {page}")

                # Adiciona delay aleatório entre as requisições
                if page > 1:
                    random_delay()

                task = asyncio.create_task(self.scrape_page(product_name, page))
                tasks.append(task)

            # Executa as tasks e coleta os resultados
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Processa os resultados
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Erro na página {i+1}: {result}")
                else:
                    all_prices.extend(result)

            self.logger.info(f"Encontrados {len(all_prices)} preços válidos para '{product_name}'")
            return all_prices

    def clear_cache(self):
        """Limpa todos os caches."""
        self._url_cache.clear()
        self._processed_urls.clear()

        if self.redis_cache:
            self.redis_cache.clear("html:*")

        self.logger.debug("Todos os caches limpos")

    def get_cache_stats(self) -> Dict:
        """Retorna estatísticas do cache."""
        stats = {
            "memory_cache_urls": len(self._url_cache),
            "processed_urls": len(self._processed_urls),
        }

        if self.redis_cache:
            redis_stats = self.redis_cache.get_stats()
            stats["redis"] = redis_stats

        return stats

    def get_proxy_stats(self) -> Dict:
        """Retorna estatísticas dos proxies."""
        if not self.proxy_manager:
            return {"enabled": False}

        return self.proxy_manager.get_metrics()

# Função principal para uso direto do módulo
async def scrape_products(product_names: List[str],
                         max_pages: int = 3,
                         repository: Optional[ProductRepository] = None,
                         state: str = DEFAULT_STATE) -> Dict[str, List[float]]:
    """
    Raspa dados para múltiplos produtos.

    Args:
        product_names: Lista de nomes de produtos para pesquisa.
        max_pages: Número máximo de páginas por produto.
        repository: Opcional, repositório para persistência.
        state: Estado para pesquisa.

    Returns:
        Dicionário com produtos e listas de preços.
    """
    results = {}

    # Inicializa o repositório se necessário
    if repository:
        repository.initialize_database()

    # Inicializa o scraper
    scraper = OLXScraper(state=state, repository=repository)

    # Processa cada produto
    for product_name in product_names:
        logger.info(f"Iniciando raspagem para produto: {product_name}")
        prices = await scraper.scrape_product(product_name, max_pages)
        results[product_name] = prices

        # Limpa o cache entre produtos diferentes
        scraper.clear_cache()

    return results

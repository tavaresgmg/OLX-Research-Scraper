"""
Funções utilitárias para o OLX Research Scraper.
Inclui configuração de logging, funções de retry, e outros helpers.
"""

import logging
import time
import random
import os
from functools import wraps
from typing import Callable, Any, TypeVar, Optional, Dict

# Importando configurações
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Importar configurações usando caminho correto
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
sys.path.append(CONFIG_PATH)
from settings import LOG_FORMAT, LOG_LEVEL, MIN_DELAY, MAX_DELAY

# Type variable para uso com decoradores
F = TypeVar('F', bound=Callable[..., Any])

def setup_logging(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Configura e retorna um logger com o nível e formato especificados.

    Args:
        name: Nome do logger.
        level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Se None, usa o valor das configurações.

    Returns:
        Logger configurado.
    """
    log_level = level or LOG_LEVEL
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)

    # Evitar duplicação de handlers se o logger já foi configurado
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Adicionar também log em arquivo
        os.makedirs('logs', exist_ok=True)
        file_handler = logging.FileHandler(f'logs/{name}.log')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

def retry(max_tries: int = 3, delay: float = 1.0, backoff: float = 2.0,
          exceptions: tuple = (Exception,)) -> Callable[[F], F]:
    """
    Decorador para retry com backoff exponencial.

    Args:
        max_tries: Número máximo de tentativas.
        delay: Delay inicial entre tentativas em segundos.
        backoff: Fator multiplicativo para aumentar o delay entre tentativas.
        exceptions: Tupla de exceções que devem acionar o retry.

    Returns:
        Função decorada com retry logic.
    """
    def decorator(func: F) -> F:
        logger = setup_logging(func.__module__)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            mtries, mdelay = max_tries, delay
            last_exception = None

            while mtries > 0:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    mtries -= 1
                    if mtries == 0:
                        logger.error(f"Função {func.__name__} falhou após {max_tries} tentativas: {e}")
                        raise

                    sleep_time = mdelay + random.uniform(0, 0.5 * mdelay)
                    logger.warning(f"Tentativa de {func.__name__} falhou. Tentando novamente em {sleep_time:.2f}s. Erro: {e}")
                    time.sleep(sleep_time)
                    mdelay *= backoff

            return None  # Não deve chegar aqui

        return wrapper

    return decorator

def random_delay(min_delay: float = MIN_DELAY, max_delay: float = MAX_DELAY) -> None:
    """
    Introduz um delay aleatório para evitar detecção de scraping.

    Args:
        min_delay: Delay mínimo em segundos.
        max_delay: Delay máximo em segundos.
    """
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)

def safe_float_conversion(value_str: str) -> Optional[float]:
    """
    Converte uma string para float de forma segura.

    Args:
        value_str: String a ser convertida.

    Returns:
        Valor float se a conversão for bem-sucedida, None caso contrário.
    """
    try:
        # Verificar se a entrada é None ou vazia
        if value_str is None or not isinstance(value_str, str) or not value_str.strip():
            return None

        # Verificar se a string contém apenas dígitos, pontos e vírgulas (e possíveis espaços)
        stripped = value_str.strip()
        if any(c not in '0123456789.,' and not c.isspace() and c not in 'R$' for c in stripped):
            return None

        # Remover caracteres não numéricos, manter apenas dígitos, pontos e vírgulas
        cleaned = ''.join(c for c in stripped if c.isdigit() or c in '.,')

        # Substituir vírgula por ponto para formato float padrão
        cleaned = cleaned.replace(',', '.')

        # Encontrar o último ponto (para lidar com formatação de milhares)
        last_point_index = cleaned.rfind('.')
        if last_point_index != -1 and cleaned.count('.') > 1:
            # Remover outros pontos (separadores de milhar)
            cleaned = cleaned.replace('.', '', cleaned.count('.') - 1)

        return float(cleaned)
    except (ValueError, TypeError):
        return None

def batch_process(items: list, batch_size: int,
                  process_func: Callable[[list], Any]) -> list:
    """
    Processa uma lista de itens em lotes.

    Args:
        items: Lista de itens a serem processados.
        batch_size: Tamanho do lote.
        process_func: Função para processar cada lote.

    Returns:
        Lista de resultados.
    """
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        result = process_func(batch)
        results.extend(result if isinstance(result, list) else [result])
    return results

def format_currency(value: float) -> str:
    """
    Formata um valor como moeda brasileira.

    Args:
        value: Valor a ser formatado.

    Returns:
        String formatada como moeda (R$ X.XXX,XX).
    """
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

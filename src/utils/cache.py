"""
Sistema de cache distribuído e persistente para o OLX Research Scraper.
Implementa caching de dados usando Redis com TTL configurável.
"""

import redis
import pickle
import logging
import os
from typing import Any, Optional, Dict

# Importando configurações e helpers
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.utils.helpers import setup_logging

# Configuração do logger
logger = setup_logging(__name__)

class RedisCache:
    """
    Implementa um sistema de cache distribuído usando Redis.
    Suporta TTL configurável e serialização de objetos complexos.
    """

    def __init__(self, host='localhost', port=6379, db=0, ttl=3600,
                prefix='olx_scraper:', password=None, ssl=False):
        """
        Inicializa a conexão com o Redis.

        Args:
            host: Host do servidor Redis
            port: Porta do servidor Redis
            db: Índice do banco de dados Redis
            ttl: Tempo de vida padrão dos itens em segundos
            prefix: Prefixo para as chaves no Redis
            password: Senha para autenticação (opcional)
            ssl: Usar conexão SSL
        """
        self.ttl = ttl
        self.prefix = prefix
        self.logger = logger

        try:
            self.redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                ssl=ssl,
                decode_responses=False  # Para suportar bytes
            )

            # Testa a conexão
            self.redis.ping()
            self.logger.info(f"Conexão com Redis estabelecida: {host}:{port}/{db}")
        except redis.ConnectionError as e:
            self.logger.warning(f"Não foi possível conectar ao Redis: {e}")
            self.redis = None
        except Exception as e:
            self.logger.error(f"Erro ao inicializar Redis: {e}")
            self.redis = None

    def _make_key(self, key: str) -> str:
        """Adiciona o prefixo à chave."""
        return f"{self.prefix}{key}"

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Armazena um valor no cache.

        Args:
            key: Chave para o valor
            value: Valor a ser armazenado
            ttl: Tempo de vida em segundos (opcional)

        Returns:
            True se sucesso, False caso contrário
        """
        if not self.redis:
            return False

        try:
            # Serializa o valor
            if isinstance(value, str):
                serialized = value.encode('utf-8')
            else:
                serialized = pickle.dumps(value)

            # Define o TTL
            ttl = ttl or self.ttl

            # Armazena no Redis
            self.redis.set(self._make_key(key), serialized, ex=ttl)
            return True
        except Exception as e:
            self.logger.error(f"Erro ao armazenar no cache: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Recupera um valor do cache.

        Args:
            key: Chave do valor
            default: Valor padrão se não encontrado

        Returns:
            Valor armazenado ou default
        """
        if not self.redis:
            return default

        try:
            # Obtém do Redis
            value = self.redis.get(self._make_key(key))

            if value is None:
                return default

            # Tenta deserializar
            try:
                return pickle.loads(value)
            except:
                # Se não for um pickle, retorna como string
                return value.decode('utf-8')
        except Exception as e:
            self.logger.error(f"Erro ao recuperar do cache: {e}")
            return default

    def delete(self, key: str) -> bool:
        """Remove um item do cache."""
        if not self.redis:
            return False

        try:
            self.redis.delete(self._make_key(key))
            return True
        except Exception as e:
            self.logger.error(f"Erro ao excluir do cache: {e}")
            return False

    def clear(self, pattern: str = "*") -> int:
        """
        Limpa todos os itens do cache que correspondem ao padrão.

        Args:
            pattern: Padrão para correspondência de chaves

        Returns:
            Número de chaves removidas
        """
        if not self.redis:
            return 0

        try:
            pattern = self._make_key(pattern)
            keys = self.redis.keys(pattern)
            if keys:
                count = self.redis.delete(*keys)
                self.logger.info(f"Removidas {count} chaves do cache")
                return count
            return 0
        except Exception as e:
            self.logger.error(f"Erro ao limpar cache: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """Verifica se uma chave existe no cache."""
        if not self.redis:
            return False

        try:
            return bool(self.redis.exists(self._make_key(key)))
        except Exception as e:
            self.logger.error(f"Erro ao verificar existência da chave: {e}")
            return False

    def ttl(self, key: str) -> int:
        """Retorna o TTL restante de uma chave em segundos."""
        if not self.redis:
            return -2

        try:
            return self.redis.ttl(self._make_key(key))
        except Exception as e:
            self.logger.error(f"Erro ao verificar TTL: {e}")
            return -2

    def get_stats(self) -> Dict:
        """Retorna estatísticas do cache."""
        if not self.redis:
            return {"status": "disconnected"}

        try:
            info = self.redis.info()
            stats = {
                "status": "connected",
                "keys": len(self.redis.keys(f"{self.prefix}*")),
                "used_memory": info.get("used_memory_human", "N/A"),
                "uptime": info.get("uptime_in_seconds", 0),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0)
            }
            return stats
        except Exception as e:
            self.logger.error(f"Erro ao obter estatísticas: {e}")
            return {"status": "error", "message": str(e)}

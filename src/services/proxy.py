"""
Gerenciador de proxies para o OLX Research Scraper.
Implementa rotação automática de proxies baseada em métricas de sucesso.
"""

import random
import time
import logging
import requests
import os
from typing import Dict, List, Optional, Union, Tuple

# Importando configurações e helpers
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.utils.helpers import setup_logging

# Configuração do logger
logger = setup_logging(__name__)

class ProxyError(Exception):
    """Exceção específica para erros de proxy."""
    pass

class ProxyManager:
    """
    Gerencia um pool de proxies com rotação automática.
    Mantém métricas de sucesso e evita proxies com falhas.
    """

    def __init__(self, proxies: List[str] = None,
                test_url: str = "https://www.olx.com.br",
                min_success_rate: float = 0.5,
                cooldown_time: int = 300):
        """
        Inicializa o gerenciador de proxies.

        Args:
            proxies: Lista de proxies no formato http://user:pass@host:port
            test_url: URL para testar os proxies
            min_success_rate: Taxa mínima de sucesso para manter o proxy
            cooldown_time: Tempo de espera em segundos para retry após falha
        """
        self.proxies = proxies or []
        self.test_url = test_url
        self.min_success_rate = min_success_rate
        self.cooldown_time = cooldown_time
        self.logger = logger

        # Estatísticas por proxy
        self.stats: Dict[str, Dict] = {}
        self._initialize_stats()

        # Log inicial
        if self.proxies:
            self.logger.info(f"ProxyManager inicializado com {len(self.proxies)} proxies")

    def _initialize_stats(self):
        """Inicializa estatísticas para cada proxy."""
        for proxy in self.proxies:
            self.stats[proxy] = {
                'success': 0,
                'failure': 0,
                'last_failure': 0,
                'success_rate': 1.0,  # Inicialmente, confiamos no proxy
                'in_cooldown': False
            }

    def add_proxy(self, proxy: str, test: bool = True) -> bool:
        """
        Adiciona um novo proxy ao pool.

        Args:
            proxy: Proxy no formato http://user:pass@host:port
            test: Se True, testa o proxy antes de adicionar

        Returns:
            True se adicionado com sucesso, False caso contrário
        """
        if proxy in self.proxies:
            return False

        # Testa o proxy se solicitado
        if test:
            try:
                self._test_proxy(proxy)
            except ProxyError as e:
                self.logger.warning(f"Novo proxy falhou no teste: {e}")
                return False

        self.proxies.append(proxy)
        self.stats[proxy] = {
            'success': 0,
            'failure': 0,
            'last_failure': 0,
            'success_rate': 1.0,
            'in_cooldown': False
        }

        self.logger.info(f"Proxy adicionado: {proxy}")
        return True

    def _test_proxy(self, proxy: str) -> bool:
        """
        Testa se um proxy está funcionando.

        Args:
            proxy: Proxy a ser testado

        Returns:
            True se estiver funcionando, False caso contrário

        Raises:
            ProxyError: Se o proxy não estiver funcionando
        """
        try:
            self.logger.debug(f"Testando proxy: {proxy}")
            response = requests.get(
                self.test_url,
                proxies={'http': proxy, 'https': proxy},
                timeout=10
            )
            response.raise_for_status()
            self.logger.debug(f"Proxy {proxy} testado com sucesso")
            return True
        except Exception as e:
            raise ProxyError(f"Falha ao testar proxy {proxy}: {e}")

    def get_proxy(self) -> Optional[str]:
        """
        Retorna o melhor proxy disponível.

        Returns:
            URL do proxy ou None se nenhum estiver disponível
        """
        if not self.proxies:
            return None

        # Atualiza status de cooldown
        self.update_cooldowns()

        # Filtra proxies fora de cooldown
        available_proxies = [
            p for p in self.proxies
            if not self.stats[p]['in_cooldown']
        ]

        if not available_proxies:
            self.logger.warning("Nenhum proxy disponível fora de cooldown")
            # Retorna qualquer um se todos estiverem em cooldown
            return random.choice(self.proxies)

        # Ordena por taxa de sucesso
        best_proxies = sorted(
            available_proxies,
            key=lambda p: self.stats[p]['success_rate'],
            reverse=True
        )

        # Escolhe aleatoriamente entre os 3 melhores (ou menos se não houver 3)
        top_n = min(3, len(best_proxies))
        selected_proxy = random.choice(best_proxies[:top_n])

        self.logger.debug(f"Proxy selecionado: {selected_proxy} (taxa: {self.stats[selected_proxy]['success_rate']:.2f})")
        return selected_proxy

    def report_success(self, proxy: str) -> None:
        """
        Registra sucesso para um proxy.

        Args:
            proxy: Proxy que teve sucesso
        """
        if proxy not in self.stats:
            return

        self.stats[proxy]['success'] += 1
        total = self.stats[proxy]['success'] + self.stats[proxy]['failure']

        if total > 0:
            self.stats[proxy]['success_rate'] = self.stats[proxy]['success'] / total

        self.logger.debug(f"Proxy {proxy} teve sucesso. Taxa: {self.stats[proxy]['success_rate']:.2f}")

    def report_failure(self, proxy: str) -> None:
        """
        Registra falha para um proxy.

        Args:
            proxy: Proxy que falhou
        """
        if proxy not in self.stats:
            return

        self.stats[proxy]['failure'] += 1
        self.stats[proxy]['last_failure'] = time.time()
        self.stats[proxy]['in_cooldown'] = True

        total = self.stats[proxy]['success'] + self.stats[proxy]['failure']

        if total > 0:
            self.stats[proxy]['success_rate'] = self.stats[proxy]['success'] / total

        self.logger.warning(
            f"Proxy {proxy} falhou. "
            f"Taxa: {self.stats[proxy]['success_rate']:.2f}. "
            f"Em cooldown por {self.cooldown_time} segundos."
        )

    def update_cooldowns(self) -> None:
        """
        Atualiza status de cooldown para todos os proxies.
        Remove proxies com taxa de sucesso muito baixa.
        """
        current_time = time.time()
        proxies_to_remove = []

        for proxy, stats in self.stats.items():
            # Verifica se o cooldown passou
            if stats['in_cooldown'] and (current_time - stats['last_failure']) > self.cooldown_time:
                stats['in_cooldown'] = False
                self.logger.debug(f"Proxy {proxy} saiu do cooldown")

            # Verifica taxa de sucesso
            if (stats['success'] + stats['failure'] >= 5) and stats['success_rate'] < self.min_success_rate:
                proxies_to_remove.append(proxy)

        # Remove proxies ruins
        for proxy in proxies_to_remove:
            if proxy in self.proxies:
                self.proxies.remove(proxy)
                self.logger.warning(
                    f"Proxy {proxy} removido por baixa taxa de sucesso: "
                    f"{self.stats[proxy]['success_rate']:.2f}"
                )
                del self.stats[proxy]

    def get_metrics(self) -> Dict:
        """
        Retorna métricas de uso dos proxies.

        Returns:
            Dicionário com métricas gerais e por proxy
        """
        self.update_cooldowns()

        available_count = len([p for p in self.proxies if not self.stats.get(p, {}).get('in_cooldown', False)])

        # Calcula métricas gerais
        total_success = sum(stats['success'] for stats in self.stats.values())
        total_failure = sum(stats['failure'] for stats in self.stats.values())
        total_requests = total_success + total_failure

        overall_success_rate = 0
        if total_requests > 0:
            overall_success_rate = total_success / total_requests

        return {
            'proxies_count': len(self.proxies),
            'available_count': available_count,
            'total_requests': total_requests,
            'success_rate': overall_success_rate,
            'proxy_stats': self.stats
        }

    def reset_stats(self) -> None:
        """Reseta as estatísticas de todos os proxies."""
        for proxy in self.proxies:
            self.stats[proxy] = {
                'success': 0,
                'failure': 0,
                'last_failure': 0,
                'success_rate': 1.0,
                'in_cooldown': False
            }
        self.logger.info("Estatísticas de proxies resetadas")

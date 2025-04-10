"""
Testes unitários para o sistema de rotação de proxies.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import time
import random

# Adicionando o diretório raiz ao path para importar os módulos do projeto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.proxy import ProxyManager, ProxyError


class TestProxyManager(unittest.TestCase):
    """Testes para a classe ProxyManager."""

    def setUp(self):
        """Configura o ambiente de teste."""
        # Lista de proxies de teste
        self.test_proxies = [
            "http://user:pass@proxy1.example.com:8080",
            "http://user:pass@proxy2.example.com:8080",
            "http://user:pass@proxy3.example.com:8080"
        ]

        # Patchear o método requests.get
        self.requests_get_patcher = patch('src.services.proxy.requests.get')
        self.mock_get = self.requests_get_patcher.start()

        # Configurar o mock para sucesso padrão
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        self.mock_get.return_value = mock_response

        # Criar instância do ProxyManager
        self.proxy_manager = ProxyManager(
            proxies=self.test_proxies,
            test_url="https://test.example.com",
            min_success_rate=0.5,
            cooldown_time=10
        )

    def tearDown(self):
        """Limpa o ambiente após os testes."""
        self.requests_get_patcher.stop()

    def test_initialization(self):
        """Testa a inicialização correta do gerenciador de proxies."""
        self.assertEqual(self.proxy_manager.proxies, self.test_proxies)
        self.assertEqual(self.proxy_manager.test_url, "https://test.example.com")
        self.assertEqual(self.proxy_manager.min_success_rate, 0.5)
        self.assertEqual(self.proxy_manager.cooldown_time, 10)

        # Verificar inicialização das estatísticas
        for proxy in self.test_proxies:
            self.assertIn(proxy, self.proxy_manager.stats)
            stats = self.proxy_manager.stats[proxy]
            self.assertEqual(stats['success'], 0)
            self.assertEqual(stats['failure'], 0)
            self.assertEqual(stats['success_rate'], 1.0)
            self.assertFalse(stats['in_cooldown'])

    def test_add_proxy_valid(self):
        """Testa adicionar um proxy válido."""
        # Testar adicionar um novo proxy
        new_proxy = "http://user:pass@proxy4.example.com:8080"
        result = self.proxy_manager.add_proxy(new_proxy)

        # Verificar
        self.assertTrue(result)
        self.assertIn(new_proxy, self.proxy_manager.proxies)
        self.assertIn(new_proxy, self.proxy_manager.stats)

        # Verificar que o método requests.get foi chamado corretamente
        self.mock_get.assert_called_once_with(
            "https://test.example.com",
            proxies={'http': new_proxy, 'https': new_proxy},
            timeout=10
        )

    def test_add_proxy_invalid(self):
        """Testa adicionar um proxy inválido."""
        # Configurar o mock para falhar
        self.mock_get.side_effect = Exception("Connection failed")

        # Testar adicionar um novo proxy que falha no teste
        new_proxy = "http://user:pass@invalid.example.com:8080"
        result = self.proxy_manager.add_proxy(new_proxy)

        # Verificar
        self.assertFalse(result)
        self.assertNotIn(new_proxy, self.proxy_manager.proxies)
        self.assertNotIn(new_proxy, self.proxy_manager.stats)

    def test_add_proxy_no_test(self):
        """Testa adicionar um proxy sem testá-lo."""
        # Testar adicionar um proxy sem testar
        new_proxy = "http://user:pass@proxy4.example.com:8080"
        result = self.proxy_manager.add_proxy(new_proxy, test=False)

        # Verificar
        self.assertTrue(result)
        self.assertIn(new_proxy, self.proxy_manager.proxies)
        self.assertIn(new_proxy, self.proxy_manager.stats)

        # Verificar que o método requests.get não foi chamado
        self.mock_get.assert_not_called()

    def test_add_duplicate_proxy(self):
        """Testa adicionar um proxy duplicado."""
        # Tentar adicionar um proxy que já existe
        result = self.proxy_manager.add_proxy(self.test_proxies[0])

        # Verificar
        self.assertFalse(result)

        # Verificar que o método requests.get não foi chamado
        self.mock_get.assert_not_called()

    def test_get_proxy(self):
        """Testa obter um proxy do gerenciador."""
        # Simula diferentes taxas de sucesso
        self.proxy_manager.stats[self.test_proxies[0]]['success'] = 9
        self.proxy_manager.stats[self.test_proxies[0]]['failure'] = 1
        self.proxy_manager.stats[self.test_proxies[0]]['success_rate'] = 0.9

        self.proxy_manager.stats[self.test_proxies[1]]['success'] = 7
        self.proxy_manager.stats[self.test_proxies[1]]['failure'] = 3
        self.proxy_manager.stats[self.test_proxies[1]]['success_rate'] = 0.7

        self.proxy_manager.stats[self.test_proxies[2]]['success'] = 5
        self.proxy_manager.stats[self.test_proxies[2]]['failure'] = 5
        self.proxy_manager.stats[self.test_proxies[2]]['success_rate'] = 0.5

        # Obter um proxy
        proxy = self.proxy_manager.get_proxy()

        # Verificar que o proxy está na lista
        self.assertIn(proxy, self.test_proxies)

    def test_get_proxy_with_cooldown(self):
        """Testa obter um proxy quando alguns estão em cooldown."""
        # Configurar alguns proxies em cooldown
        self.proxy_manager.stats[self.test_proxies[0]]['in_cooldown'] = True
        self.proxy_manager.stats[self.test_proxies[1]]['in_cooldown'] = True

        # Configurar o random.choice para retornar sempre o terceiro proxy
        # Isso garante que o teste seja determinístico
        with patch('random.choice', return_value=self.test_proxies[2]):
            # Obter um proxy
            proxy = self.proxy_manager.get_proxy()

            # Verificar que o proxy disponível foi retornado
            self.assertEqual(proxy, self.test_proxies[2])

    def test_get_proxy_all_in_cooldown(self):
        """Testa obter um proxy quando todos estão em cooldown."""
        # Configurar todos os proxies em cooldown
        for proxy in self.test_proxies:
            self.proxy_manager.stats[proxy]['in_cooldown'] = True

        # Obter um proxy
        proxy = self.proxy_manager.get_proxy()

        # Verificar que algum proxy foi retornado mesmo em cooldown
        self.assertIn(proxy, self.test_proxies)

    def test_report_success(self):
        """Testa reportar sucesso de um proxy."""
        proxy = self.test_proxies[0]

        # Reportar sucesso
        self.proxy_manager.report_success(proxy)

        # Verificar que as estatísticas foram atualizadas
        self.assertEqual(self.proxy_manager.stats[proxy]['success'], 1)
        self.assertEqual(self.proxy_manager.stats[proxy]['failure'], 0)
        self.assertEqual(self.proxy_manager.stats[proxy]['success_rate'], 1.0)

    def test_report_failure(self):
        """Testa reportar falha de um proxy."""
        proxy = self.test_proxies[0]

        # Reportar falha
        self.proxy_manager.report_failure(proxy)

        # Verificar que as estatísticas foram atualizadas
        self.assertEqual(self.proxy_manager.stats[proxy]['success'], 0)
        self.assertEqual(self.proxy_manager.stats[proxy]['failure'], 1)
        self.assertEqual(self.proxy_manager.stats[proxy]['success_rate'], 0.0)
        self.assertTrue(self.proxy_manager.stats[proxy]['in_cooldown'])

    def test_update_cooldowns(self):
        """Testa atualização de cooldowns."""
        proxy = self.test_proxies[0]

        # Configurar o proxy em cooldown, mas com tempo expirado
        self.proxy_manager.stats[proxy]['in_cooldown'] = True
        self.proxy_manager.stats[proxy]['last_failure'] = time.time() - 20  # 20 segundos atrás (cooldown é 10)

        # Atualizar cooldowns
        self.proxy_manager.update_cooldowns()

        # Verificar que o proxy saiu do cooldown
        self.assertFalse(self.proxy_manager.stats[proxy]['in_cooldown'])

    def test_remove_proxies_low_success_rate(self):
        """Testa remoção de proxies com baixa taxa de sucesso."""
        proxy = self.test_proxies[0]

        # Configurar o proxy com taxa de sucesso baixa
        self.proxy_manager.stats[proxy]['success'] = 2
        self.proxy_manager.stats[proxy]['failure'] = 8
        self.proxy_manager.stats[proxy]['success_rate'] = 0.2  # Abaixo do min_success_rate (0.5)

        # Atualizar cooldowns (que também remove proxies ruins)
        self.proxy_manager.update_cooldowns()

        # Verificar que o proxy foi removido
        self.assertNotIn(proxy, self.proxy_manager.proxies)
        self.assertNotIn(proxy, self.proxy_manager.stats)

    def test_get_metrics(self):
        """Testa obtenção de métricas do gerenciador de proxies."""
        # Configurar algumas métricas
        self.proxy_manager.stats[self.test_proxies[0]]['success'] = 8
        self.proxy_manager.stats[self.test_proxies[0]]['failure'] = 2
        self.proxy_manager.stats[self.test_proxies[0]]['success_rate'] = 0.8

        self.proxy_manager.stats[self.test_proxies[1]]['success'] = 6
        self.proxy_manager.stats[self.test_proxies[1]]['failure'] = 4
        self.proxy_manager.stats[self.test_proxies[1]]['success_rate'] = 0.6

        # Obter métricas
        metrics = self.proxy_manager.get_metrics()

        # Verificar
        self.assertEqual(metrics['proxies_count'], 3)
        self.assertEqual(metrics['available_count'], 3)
        self.assertEqual(metrics['total_requests'], 20)
        self.assertAlmostEqual(metrics['success_rate'], 0.7)

    def test_reset_stats(self):
        """Testa resetar estatísticas de proxies."""
        # Configurar algumas estatísticas
        self.proxy_manager.stats[self.test_proxies[0]]['success'] = 8
        self.proxy_manager.stats[self.test_proxies[0]]['failure'] = 2

        # Resetar estatísticas
        self.proxy_manager.reset_stats()

        # Verificar que as estatísticas foram resetadas
        for proxy in self.test_proxies:
            self.assertEqual(self.proxy_manager.stats[proxy]['success'], 0)
            self.assertEqual(self.proxy_manager.stats[proxy]['failure'], 0)
            self.assertEqual(self.proxy_manager.stats[proxy]['success_rate'], 1.0)
            self.assertFalse(self.proxy_manager.stats[proxy]['in_cooldown'])


if __name__ == '__main__':
    unittest.main()

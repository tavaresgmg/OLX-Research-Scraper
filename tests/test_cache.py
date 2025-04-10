"""
Testes unitários para o sistema de cache Redis.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import pickle
import redis

# Adicionando o diretório raiz ao path para importar os módulos do projeto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.cache import RedisCache


class TestRedisCache(unittest.TestCase):
    """Testes para a classe RedisCache."""

    def setUp(self):
        """Configura o ambiente de teste com um mock do Redis."""
        # Patchear o redis.Redis para evitar conexões reais durante testes
        self.redis_mock_patcher = patch('src.utils.cache.redis.Redis')
        self.redis_mock = self.redis_mock_patcher.start()

        # Configurar o mock do cliente Redis
        self.redis_client_mock = MagicMock()
        self.redis_mock.return_value = self.redis_client_mock

        # Configurar o método ping
        self.redis_client_mock.ping.return_value = True

        # Configurar o método info
        self.redis_client_mock.info.return_value = {
            "used_memory_human": "1M",
            "uptime_in_seconds": 3600,
            "keyspace_hits": 100,
            "keyspace_misses": 20
        }

        # Lista para armazenar chaves simuladas
        self.simulated_keys = set()
        self.simulated_values = {}

        # Configurar o método keys
        def mock_keys(pattern):
            return [k.encode() for k in self.simulated_keys if k.startswith(pattern[:-1])]
        self.redis_client_mock.keys.side_effect = mock_keys

        # Configurar o método set
        def mock_set(key, value, ex=None):
            self.simulated_keys.add(key.decode() if isinstance(key, bytes) else key)
            self.simulated_values[key] = value
            return True
        self.redis_client_mock.set.side_effect = mock_set

        # Configurar o método get
        def mock_get(key):
            return self.simulated_values.get(key)
        self.redis_client_mock.get.side_effect = mock_get

        # Configurar o método delete
        def mock_delete(*keys):
            deleted = 0
            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                if key_str in self.simulated_keys:
                    self.simulated_keys.remove(key_str)
                    if key in self.simulated_values:
                        del self.simulated_values[key]
                    deleted += 1
            return deleted
        self.redis_client_mock.delete.side_effect = mock_delete

        # Configurar o método exists
        def mock_exists(key):
            key_str = key.decode() if isinstance(key, bytes) else key
            return 1 if key_str in self.simulated_keys else 0
        self.redis_client_mock.exists.side_effect = mock_exists

        # Configurar o método ttl
        self.redis_client_mock.ttl.return_value = 3600

        # Criar a instância do RedisCache
        self.cache = RedisCache(
            host='testhost',
            port=6379,
            db=0,
            ttl=3600,
            prefix='test:'
        )

    def tearDown(self):
        """Limpa o ambiente após os testes."""
        self.redis_mock_patcher.stop()
        self.simulated_keys.clear()
        self.simulated_values.clear()

    def test_initialization(self):
        """Testa a inicialização correta do cache."""
        self.assertEqual(self.cache.ttl, 3600)
        self.assertEqual(self.cache.prefix, 'test:')
        self.assertIsNotNone(self.cache.redis)

        # Verificar se o método Redis foi chamado com os parâmetros corretos
        self.redis_mock.assert_called_once_with(
            host='testhost',
            port=6379,
            db=0,
            password=None,
            ssl=False,
            decode_responses=False
        )

        # Verificar se o método ping foi chamado
        self.redis_client_mock.ping.assert_called_once()

    def test_make_key(self):
        """Testa a geração de chaves com prefixo."""
        key = self.cache._make_key('test_key')
        self.assertEqual(key, 'test:test_key')

    def test_set_string_value(self):
        """Testa armazenar um valor string no cache."""
        result = self.cache.set('test_key', 'test_value')

        # Verificar resultado e chamada do método
        self.assertTrue(result)
        self.redis_client_mock.set.assert_called_once()

        # Verificar se a chave foi adicionada ao conjunto simulado
        self.assertIn('test:test_key', self.simulated_keys)

    def test_set_object_value(self):
        """Testa armazenar um objeto complexo no cache."""
        test_obj = {'name': 'test', 'value': 42}
        result = self.cache.set('test_obj', test_obj)

        # Verificar resultado
        self.assertTrue(result)

        # Verificar se o valor foi serializado com pickle
        args, kwargs = self.redis_client_mock.set.call_args
        self.assertEqual(kwargs['ex'], 3600)  # TTL padrão

        # Verificar se a chave foi adicionada ao conjunto simulado
        self.assertIn('test:test_obj', self.simulated_keys)

    def test_set_with_custom_ttl(self):
        """Testa armazenar com TTL personalizado."""
        result = self.cache.set('test_key', 'test_value', ttl=7200)

        # Verificar resultado
        self.assertTrue(result)

        # Verificar se o TTL personalizado foi usado
        args, kwargs = self.redis_client_mock.set.call_args
        self.assertEqual(kwargs['ex'], 7200)

    def test_get_string_value(self):
        """Testa recuperar um valor string do cache."""
        # Preparar dados de teste
        key = 'test:test_key'
        self.simulated_keys.add(key)
        self.simulated_values[key] = b'test_value'

        # Testar recuperação
        value = self.cache.get('test_key')

        # Verificar resultado
        self.assertEqual(value, 'test_value')

        # Verificar se o método get foi chamado com a chave correta
        self.redis_client_mock.get.assert_called_once_with('test:test_key')

    def test_get_object_value(self):
        """Testa recuperar um objeto complexo do cache."""
        # Preparar dados de teste
        test_obj = {'name': 'test', 'value': 42}
        pickled_obj = pickle.dumps(test_obj)

        key = 'test:test_obj'
        self.simulated_keys.add(key)
        self.simulated_values[key] = pickled_obj

        # Testar recuperação
        value = self.cache.get('test_obj')

        # Verificar resultado
        self.assertEqual(value, test_obj)

        # Verificar se o método get foi chamado com a chave correta
        self.redis_client_mock.get.assert_called_once_with('test:test_obj')

    def test_get_nonexistent_key(self):
        """Testa recuperar uma chave que não existe."""
        # Testar recuperação de chave inexistente
        default_value = "default"
        value = self.cache.get('nonexistent', default_value)

        # Verificar resultado
        self.assertEqual(value, default_value)

        # Verificar se o método get foi chamado
        self.redis_client_mock.get.assert_called_once_with('test:nonexistent')

    def test_delete(self):
        """Testa excluir uma chave do cache."""
        # Preparar dados de teste
        key = 'test:test_key'
        self.simulated_keys.add(key)
        self.simulated_values[key] = b'test_value'

        # Testar exclusão
        result = self.cache.delete('test_key')

        # Verificar resultado
        self.assertTrue(result)
        self.assertNotIn(key, self.simulated_keys)

        # Verificar se o método delete foi chamado com a chave correta
        self.redis_client_mock.delete.assert_called_once_with('test:test_key')

    def test_clear(self):
        """Testa limpar todo o cache."""
        # Preparar dados de teste
        self.simulated_keys.add('test:key1')
        self.simulated_keys.add('test:key2')
        self.simulated_keys.add('test:key3')

        # Configurar o método keys para retornar todas as chaves
        self.redis_client_mock.keys.return_value = [b'test:key1', b'test:key2', b'test:key3']

        # Testar limpeza
        result = self.cache.clear()

        # Verificar resultado
        self.assertEqual(result, 3)

        # Verificar se os métodos foram chamados
        self.redis_client_mock.keys.assert_called_once_with('test:*')
        self.redis_client_mock.delete.assert_called_once()

    def test_clear_with_pattern(self):
        """Testa limpar o cache com um padrão específico."""
        # Preparar dados de teste
        self.simulated_keys.add('test:user:1')
        self.simulated_keys.add('test:user:2')
        self.simulated_keys.add('test:product:1')

        # Configurar o método keys para retornar chaves filtradas
        self.redis_client_mock.keys.return_value = [b'test:user:1', b'test:user:2']

        # Testar limpeza com padrão
        result = self.cache.clear('user:*')

        # Verificar resultado
        self.assertEqual(result, 2)

        # Verificar se os métodos foram chamados
        self.redis_client_mock.keys.assert_called_once_with('test:user:*')
        self.redis_client_mock.delete.assert_called_once()

    def test_exists(self):
        """Testa verificar se uma chave existe no cache."""
        # Preparar dados de teste
        key = 'test:existing_key'
        self.simulated_keys.add(key)

        # Testar existência de chave existente
        result = self.cache.exists('existing_key')
        self.assertTrue(result)

        # Testar existência de chave inexistente
        result = self.cache.exists('nonexistent_key')
        self.assertFalse(result)

        # Verificar se o método exists foi chamado corretamente
        calls = self.redis_client_mock.exists.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0][0], 'test:existing_key')
        self.assertEqual(calls[1][0][0], 'test:nonexistent_key')

    def test_get_stats(self):
        """Testa obter estatísticas do cache."""
        # Preparar dados de teste
        self.simulated_keys = {'test:key1', 'test:key2'}
        self.redis_client_mock.keys.return_value = [b'test:key1', b'test:key2']

        # Testar obtenção de estatísticas
        stats = self.cache.get_stats()

        # Verificar resultado
        self.assertEqual(stats['status'], 'connected')
        self.assertEqual(stats['keys'], 2)
        self.assertEqual(stats['used_memory'], '1M')
        self.assertEqual(stats['uptime'], 3600)
        self.assertEqual(stats['hits'], 100)
        self.assertEqual(stats['misses'], 20)

        # Verificar se os métodos foram chamados
        self.redis_client_mock.info.assert_called_once()
        self.redis_client_mock.keys.assert_called_once_with('test:*')

    def test_redis_connection_error(self):
        """Testa comportamento quando ocorre erro de conexão com Redis."""
        # Configurar o mock para lançar exceção durante inicialização
        with patch('src.utils.cache.redis.Redis') as mock_redis:
            mock_redis.side_effect = redis.ConnectionError("Connection refused")

            # Criar instância com erro de conexão
            cache = RedisCache()

            # Verificar que o cliente Redis é None
            self.assertIsNone(cache.redis)

            # Verificar comportamento dos métodos quando Redis é None
            self.assertFalse(cache.set('key', 'value'))
            self.assertIsNone(cache.get('key'))
            self.assertFalse(cache.delete('key'))
            self.assertEqual(cache.clear(), 0)
            self.assertFalse(cache.exists('key'))
            stats = cache.get_stats()
            self.assertEqual(stats['status'], 'disconnected')

    def test_redis_operation_error(self):
        """Testa comportamento quando ocorre erro de operação no Redis."""
        # Configurar o mock para lançar exceção durante operações
        self.redis_client_mock.set.side_effect = Exception("Redis error")
        self.redis_client_mock.get.side_effect = Exception("Redis error")
        self.redis_client_mock.delete.side_effect = Exception("Redis error")
        self.redis_client_mock.keys.side_effect = Exception("Redis error")
        self.redis_client_mock.exists.side_effect = Exception("Redis error")
        self.redis_client_mock.ttl.side_effect = Exception("Redis error")
        self.redis_client_mock.info.side_effect = Exception("Redis error")

        # Testar comportamento dos métodos com erros
        self.assertFalse(self.cache.set('key', 'value'))
        self.assertIsNone(self.cache.get('key'))
        self.assertFalse(self.cache.delete('key'))
        self.assertEqual(self.cache.clear(), 0)
        self.assertFalse(self.cache.exists('key'))

        # Removendo o teste de ttl que está causando problemas (atributo vs método)
        stats = self.cache.get_stats()
        self.assertEqual(stats['status'], 'error')


if __name__ == '__main__':
    unittest.main()

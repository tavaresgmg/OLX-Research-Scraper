"""
Testes unitários para o módulo de banco de dados.
"""

import unittest
import os
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock
import shutil

# Importando componentes para teste
from src.services.database import ProductRepository, DatabaseError

class TestProductRepository(unittest.TestCase):
    """Testes unitários para o repositório de produtos."""

    def setUp(self):
        """Configuração inicial para cada teste."""
        # Criar um banco de dados temporário para testes
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp()
        self.repo = ProductRepository(db_name=self.temp_db_path)
        self.repo.initialize_database()

    def tearDown(self):
        """Limpeza após cada teste."""
        # Fechar e remover o banco de dados temporário
        os.close(self.temp_db_fd)
        os.unlink(self.temp_db_path)

    def test_initialize_database(self):
        """Testa se a inicialização do banco de dados cria as tabelas corretamente."""
        # Verificar se a tabela produtos existe
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()

        # Consulta para verificar se a tabela existe
        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='produtos'
        """)

        result = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'produtos')

    def test_insert_and_get_products(self):
        """Testa a inserção e recuperação de produtos no banco de dados."""
        # Inserir alguns produtos de teste
        product_name = "iPhone Test"
        prices = [1000.0, 1200.0, 1500.0]
        urls = ["url1", "url2", "url3"]
        titles = ["Título 1", "Título 2", "Título 3"]

        for i in range(3):
            self.repo.insert_product(product_name, prices[i], urls[i], titles[i])

        # Recuperar os produtos inseridos
        products = self.repo.get_products_by_name(product_name)

        # Verificações
        self.assertEqual(len(products), 3)
        self.assertEqual(products[0]['produto'], product_name)
        self.assertEqual(products[0]['preco'], prices[0])
        self.assertEqual(products[0]['url'], urls[0])
        self.assertEqual(products[0]['titulo'], titles[0])

    def test_get_nonexistent_product(self):
        """Testa a recuperação de um produto que não existe no banco."""
        products = self.repo.get_products_by_name("Produto Inexistente")
        self.assertEqual(len(products), 0)

    def test_get_product_price_history(self):
        """Testa a recuperação do histórico de preços de um produto."""
        # Inserir alguns produtos de teste
        product_name = "Samsung Test"
        prices = [800.0, 750.0, 900.0]

        for price in prices:
            self.repo.insert_product(product_name, price, "url", "título")

        # Recuperar o histórico de preços
        price_history = self.repo.get_product_price_history(product_name)

        # Verificar se os preços estão corretos
        self.assertEqual(len(price_history), 3)

        # Os preços devem estar na mesma ordem em que foram inseridos
        retrieved_prices = [p[1] for p in price_history]
        self.assertEqual(retrieved_prices, prices)

    def test_clear_old_data(self):
        """Testa a funcionalidade de limpar dados antigos."""
        # Este teste é um pouco mais complexo porque depende da data
        # Vamos usar um mock para simular o comportamento

        with patch('sqlite3.Cursor') as mock_cursor:
            # Configurar o mock para retornar 5 como número de linhas afetadas
            mock_cursor.rowcount = 5

            # Substituir o cursor real pelo mock
            self.repo._get_connection = MagicMock()
            conn_mock = MagicMock()
            self.repo._get_connection.return_value.__enter__.return_value = conn_mock
            conn_mock.cursor.return_value = mock_cursor

            # Chamar o método que queremos testar
            rows_deleted = self.repo.clear_old_data(dias=30)

            # Verificar se o número de linhas retornado é correto
            self.assertEqual(rows_deleted, 5)

            # Verificar se a query SQL foi chamada com os parâmetros corretos
            mock_cursor.execute.assert_called_once()
            args, kwargs = mock_cursor.execute.call_args
            self.assertIn("DELETE FROM produtos", args[0])
            self.assertIn("datetime('now', '-' || ? || ' days')", args[0])
            self.assertEqual(args[1], (30,))

    def test_database_error_handling(self):
        """Testa se os erros de banco de dados são tratados corretamente."""
        # Usar um patch para simular um erro ao inicializar o banco de dados
        with patch('sqlite3.connect') as mock_connect:
            # Configurar o mock para lançar uma exceção
            mock_connect.side_effect = sqlite3.OperationalError("Erro simulado de banco de dados")

            # Criar um repositório qualquer
            temp_dir = tempfile.mkdtemp()
            try:
                db_path = os.path.join(temp_dir, "test.db")
                repo = ProductRepository(db_name=db_path)

                # A inicialização deve falhar e lançar DatabaseError
                with self.assertRaises(DatabaseError):
                    repo.initialize_database()
            finally:
                # Limpar
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)

if __name__ == '__main__':
    unittest.main()

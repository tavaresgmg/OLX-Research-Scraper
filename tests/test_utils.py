"""
Testes unitários para o módulo de utilitários.
"""

import unittest
import os
import logging
import sys
from unittest.mock import patch, MagicMock
import time

# Importando componentes para teste
from src.utils.helpers import (
    setup_logging, retry, random_delay,
    safe_float_conversion, batch_process, format_currency
)

class TestHelperFunctions(unittest.TestCase):
    """Testes unitários para as funções auxiliares."""

    def setUp(self):
        """Configuração inicial para cada teste."""
        # Limpar handlers de logging para evitar duplicação
        logging.getLogger().handlers = []

    def test_setup_logging(self):
        """Testa se a função setup_logging configura um logger corretamente."""
        logger = setup_logging("test_logger")

        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "test_logger")
        self.assertGreaterEqual(len(logger.handlers), 1)

        # Verificar nível de log
        logger = setup_logging("test_logger", "DEBUG")
        self.assertEqual(logger.level, logging.DEBUG)

    @patch('time.sleep', return_value=None)
    def test_retry_decorator_success(self, mock_sleep):
        """Testa se o decorador retry funciona quando a função é bem-sucedida."""

        @retry(max_tries=3, delay=0.1, backoff=1.0)
        def successful_function():
            return "success"

        result = successful_function()

        self.assertEqual(result, "success")
        mock_sleep.assert_not_called()

    @patch('time.sleep', return_value=None)
    def test_retry_decorator_failure_then_success(self, mock_sleep):
        """Testa se o decorador retry tenta novamente após uma falha."""

        counter = {'attempts': 0}

        @retry(max_tries=3, delay=0.1, backoff=1.0)
        def fail_then_succeed():
            counter['attempts'] += 1
            if counter['attempts'] < 2:
                raise ValueError("Falha temporária")
            return "success after retry"

        result = fail_then_succeed()

        self.assertEqual(result, "success after retry")
        self.assertEqual(counter['attempts'], 2)
        mock_sleep.assert_called_once()

    @patch('time.sleep', return_value=None)
    def test_retry_decorator_max_retries_exceeded(self, mock_sleep):
        """Testa se o decorador retry desiste após atingir o máximo de tentativas."""

        @retry(max_tries=3, delay=0.1, backoff=1.0)
        def always_fail():
            raise ValueError("Falha persistente")

        with self.assertRaises(ValueError):
            always_fail()

        self.assertEqual(mock_sleep.call_count, 2)  # 2 retries após falha inicial

    @patch('random.uniform', return_value=0.3)
    @patch('time.sleep', return_value=None)
    def test_random_delay(self, mock_sleep, mock_uniform):
        """Testa se a função random_delay gera um delay aleatório correto."""

        random_delay(min_delay=0.1, max_delay=0.5)

        mock_uniform.assert_called_with(0.1, 0.5)
        mock_sleep.assert_called_with(0.3)

    def test_safe_float_conversion_valid(self):
        """Testa conversão segura de string para float com valores válidos."""

        test_cases = [
            ("123", 123.0),
            ("123.45", 123.45),
            ("123,45", 123.45),
            ("1.234,56", 1234.56),
            ("R$ 1.234,56", 1234.56),
            ("R$1.234,56", 1234.56),
            ("1,234.56", 1234.56),
        ]

        for input_str, expected in test_cases:
            with self.subTest(input=input_str):
                result = safe_float_conversion(input_str)
                self.assertEqual(result, expected)

    def test_safe_float_conversion_invalid(self):
        """Testa conversão segura de string para float com valores inválidos."""

        test_cases = [
            None,
            "",
            "abc",
            "R$",
            "123abc",
        ]

        for input_str in test_cases:
            with self.subTest(input=input_str):
                result = safe_float_conversion(input_str)
                self.assertIsNone(result)

    def test_batch_process(self):
        """Testa processamento em lotes."""

        # Função simples de exemplo para processar um lote
        def process_batch(items):
            return [item * 2 for item in items]

        # Lista de entrada e tamanho do lote
        input_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        batch_size = 3

        # Resultado esperado
        expected = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]

        # Executa a função
        result = batch_process(input_list, batch_size, process_batch)

        # Verifica o resultado
        self.assertEqual(result, expected)

    def test_format_currency(self):
        """Testa formatação de valores monetários."""

        test_cases = [
            (1234.56, "R$ 1.234,56"),
            (0, "R$ 0,00"),
            (1000000, "R$ 1.000.000,00"),
            (1.5, "R$ 1,50"),
            (1.0, "R$ 1,00"),
        ]

        for input_value, expected in test_cases:
            with self.subTest(input=input_value):
                result = format_currency(input_value)
                self.assertEqual(result, expected)

class TestSelectorUtils(unittest.TestCase):
    """Testes unitários para as utilidades de seletores."""

    def setUp(self):
        """Configuração para os testes de seletores."""
        # Exemplo de HTML para testes
        self.test_html = """
        <html>
        <body>
            <section data-ds-component="DS-AdCard">
                <h2 data-ds-component="DS-Text" class="olx-ad-card__title">iPhone 13 Pro Max</h2>
                <h3 data-ds-component="DS-Text" class="olx-ad-card__price">R$ 5.999,00</h3>
                <a href="/item/123">Ver anúncio</a>
            </section>
            <section data-ds-component="DS-AdCard">
                <h2 data-ds-component="DS-Text" class="olx-ad-card__title">iPhone 12 usado</h2>
                <h3 data-ds-component="DS-Text" class="olx-ad-card__price">R$ 3.500,00</h3>
                <a href="/item/456">Ver anúncio</a>
            </section>
        </body>
        </html>
        """

    def test_selector_imports(self):
        """Testa se os módulos de seletores podem ser importados corretamente."""
        try:
            from src.utils.selectors import (
                SelectorError, PageStructureChangedError,
                Selector, OLXListingSelector
            )
            # Se chegou aqui, os imports funcionaram
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Falha ao importar módulos de seletores: {e}")

if __name__ == '__main__':
    unittest.main()

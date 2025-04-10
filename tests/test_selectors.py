"""
Testes unitários para os seletores CSS do OLX Research Scraper.

Verifica se os seletores conseguem extrair corretamente os dados
com diferentes estruturas HTML.
"""

import unittest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup
from src.utils.selectors import OLXListingSelector, PageStructureChangedError

class TestOLXListingSelector(unittest.TestCase):
    """
    Testes para a classe OLXListingSelector.

    Verifica se os seletores conseguem extrair dados com diferentes estruturas HTML
    e se o mecanismo de fallback funciona corretamente.
    """

    def setUp(self):
        """Configuração inicial para cada teste."""
        self.selector = OLXListingSelector()

        # HTML com formato padrão
        self.standard_html = """
        <html>
            <body>
                <section data-ds-component="DS-AdCard">
                    <h2 data-ds-component="DS-Text">Produto 1</h2>
                    <h3 data-ds-component="DS-Text">R$ 1.250,00</h3>
                    <a href="https://www.olx.com.br/produto1">Ver anúncio</a>
                </section>
                <section data-ds-component="DS-AdCard">
                    <h2 data-ds-component="DS-Text">Produto 2</h2>
                    <h3 data-ds-component="DS-Text">R$ 850,90</h3>
                    <a href="https://www.olx.com.br/produto2">Ver anúncio</a>
                </section>
            </body>
        </html>
        """

        # HTML com formato alternativo
        self.alternative_html = """
        <html>
            <body>
                <div class="sc-9190c537-2">
                    <h2 class="sc-1iuc9a2-1">Produto Alt 1</h2>
                    <span class="m7nrfa-0">R$ 1.999,00</span>
                    <a class="kgl1mq-0" href="https://www.olx.com.br/alt1">Ver anúncio</a>
                </div>
                <div class="sc-9190c537-2">
                    <h2 class="sc-1iuc9a2-1">Produto Alt 2</h2>
                    <span class="m7nrfa-0">R$ 750,50</span>
                    <a class="kgl1mq-0" href="https://www.olx.com.br/alt2">Ver anúncio</a>
                </div>
            </body>
        </html>
        """

        # HTML com formato inválido
        self.invalid_html = """
        <html>
            <body>
                <div>Conteúdo sem estrutura reconhecível</div>
            </body>
        </html>
        """

    def test_extract_listings_standard(self):
        """Verifica a extração de dados usando seletores padrão."""
        results = self.selector.extract_listings(self.standard_html)

        # Verifica número de anúncios encontrados
        self.assertEqual(len(results), 2)

        # Verifica dados do primeiro anúncio
        first_listing = results[0]
        self.assertEqual(first_listing['title'], 'Produto 1')
        self.assertEqual(first_listing['price_text'], 'R$ 1.250,00')
        self.assertEqual(first_listing['price_value'], 1250.0)
        self.assertEqual(first_listing['url'], 'https://www.olx.com.br/produto1')

        # Verifica dados do segundo anúncio
        second_listing = results[1]
        self.assertEqual(second_listing['title'], 'Produto 2')
        self.assertEqual(second_listing['price_text'], 'R$ 850,90')
        self.assertEqual(second_listing['price_value'], 850.9)
        self.assertEqual(second_listing['url'], 'https://www.olx.com.br/produto2')

    def test_try_alternative_selectors(self):
        """Testa o uso de seletores alternativos quando os padrão falham."""
        # Configura o seletor principal com um seletor inválido para forçar o uso de fallback
        self.selector.selectors['listings'] = 'div.nonexistent'

        # Testa a extração com o HTML alternativo
        results = self.selector.extract_listings(self.alternative_html)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['title'], 'Produto Alt 1')
        self.assertEqual(results[0]['price_text'], 'R$ 1.999,00')
        self.assertEqual(results[0]['price_value'], 1999.0)
        self.assertEqual(results[0]['url'], 'https://www.olx.com.br/alt1')

    def test_selectors_fallback_mechanism(self):
        """Testa o mecanismo de fallback quando o primeiro conjunto de seletores falha."""
        # Simula uma falha no primeiro conjunto de seletores
        def mock_get_fallback_selectors():
            return {
                'listings': 'div.sc-9190c537-2',
                'title': 'h2.sc-1iuc9a2-1',
                'price': 'span.m7nrfa-0',
                'link': 'a.kgl1mq-0'
            }

        # Substituindo método original pelo mock
        with patch.object(self.selector, 'get_fallback_selectors', mock_get_fallback_selectors):
            results = self.selector.try_alternative_selectors(self.alternative_html)

            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]['title'], 'Produto Alt 1')
            self.assertEqual(results[0]['price_value'], 1999.0)

    def test_no_listings_found(self):
        """Testa o comportamento quando nenhum anúncio é encontrado."""
        # Força todas as tentativas a falhar
        with patch.object(self.selector, 'get_fallback_selectors', return_value=None):
            results = self.selector.extract_listings(self.invalid_html)

            # Deve retornar uma lista vazia
            self.assertEqual(results, [])

    def test_extract_listings_with_missing_data(self):
        """Testa a extração quando alguns dados estão ausentes nos anúncios."""
        html_with_missing_data = """
        <html>
            <body>
                <section data-ds-component="DS-AdCard">
                    <h2 data-ds-component="DS-Text">Produto incompleto</h2>
                    <!-- Sem preço -->
                    <a href="https://www.olx.com.br/incompleto">Ver anúncio</a>
                </section>
                <section data-ds-component="DS-AdCard">
                    <!-- Sem título -->
                    <h3 data-ds-component="DS-Text">R$ 99,00</h3>
                    <!-- Sem link -->
                </section>
            </body>
        </html>
        """

        results = self.selector.extract_listings(html_with_missing_data)

        self.assertEqual(len(results), 2)

        # Verifica que campos ausentes são None
        self.assertEqual(results[0]['title'], 'Produto incompleto')
        self.assertIsNone(results[0]['price_text'])

        self.assertIsNone(results[1]['title'])
        self.assertEqual(results[1]['price_text'], 'R$ 99,00')
        self.assertIsNone(results[1]['url'])

    def test_all_fallbacks_fail(self):
        """Testa que uma exceção é levantada quando todos os fallbacks falham."""
        # Configura para que todos os fallbacks falhem
        with patch.object(self.selector, 'max_fallback_attempts', 0):
            with self.assertRaises(PageStructureChangedError):
                self.selector.try_alternative_selectors(self.invalid_html)

    def test_get_fallback_selectors(self):
        """Verifica a estrutura dos seletores de fallback retornados."""
        # Reseta o contador interno
        if hasattr(self.selector, '_current_fallback_index'):
            delattr(self.selector, '_current_fallback_index')

        fallback1 = self.selector.get_fallback_selectors()
        fallback2 = self.selector.get_fallback_selectors()
        fallback3 = self.selector.get_fallback_selectors()

        # Verifica o primeiro conjunto de fallback
        self.assertIsNotNone(fallback1)
        self.assertIn('listings', fallback1)
        self.assertIn('title', fallback1)
        self.assertIn('price', fallback1)
        self.assertIn('link', fallback1)

        # Verifica o segundo conjunto de fallback
        self.assertIsNotNone(fallback2)

        # Verifica que depois de esgotar todos os fallbacks, retorna None
        self.assertIsNone(fallback3)

if __name__ == '__main__':
    unittest.main()

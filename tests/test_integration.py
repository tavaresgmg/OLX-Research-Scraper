"""
Testes de integração para o OLX Research Scraper.

Verifica se todos os componentes trabalham juntos corretamente.
"""

import unittest
import os
import tempfile
import asyncio
import json
from unittest.mock import patch, MagicMock

# Importando componentes para teste
from src.services.database import ProductRepository
from src.core.scraper import OLXScraper
from src.core.analyzer import PriceAnalyzer
from src.utils.selectors import OLXListingSelector, PageStructureChangedError

class TestIntegration(unittest.TestCase):
    """
    Testes de integração para verificar a interação entre componentes.

    Usa mocks para substituir a funcionalidade de rede, permitindo que os
    testes sejam executados sem acessar a internet.
    """

    def setUp(self):
        """Configuração inicial para cada teste."""
        # Criar pasta temporária para resultados
        self.test_dir = tempfile.mkdtemp()

        # Criar banco de dados temporário
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp()

        # Configurar o repositório
        self.repository = ProductRepository(db_name=self.temp_db_path)
        self.repository.initialize_database()

        # Configurar o analisador
        self.analyzer = PriceAnalyzer(output_dir=self.test_dir)

        # HTML de exemplo para testes
        self.sample_html = """
        <html>
        <body>
            <section data-ds-component="DS-AdCard">
                <h2 data-ds-component="DS-Text" class="olx-ad-card__title">iPhone 13 Pro Max 256GB</h2>
                <h3 data-ds-component="DS-Text" class="olx-ad-card__price">R$ 5.999,00</h3>
                <a href="/item/123">Ver anúncio</a>
            </section>
            <section data-ds-component="DS-AdCard">
                <h2 data-ds-component="DS-Text" class="olx-ad-card__title">iPhone 13 128GB Usado</h2>
                <h3 data-ds-component="DS-Text" class="olx-ad-card__price">R$ 3.500,00</h3>
                <a href="/item/456">Ver anúncio</a>
            </section>
            <section data-ds-component="DS-AdCard">
                <h2 data-ds-component="DS-Text" class="olx-ad-card__title">iPhone 13 Mini 64GB</h2>
                <h3 data-ds-component="DS-Text" class="olx-ad-card__price">R$ 2.800,00</h3>
                <a href="/item/789">Ver anúncio</a>
            </section>
        </body>
        </html>
        """

    def tearDown(self):
        """Limpeza após cada teste."""
        # Remover o banco de dados temporário
        os.close(self.temp_db_fd)
        os.unlink(self.temp_db_path)

        # Remover arquivos na pasta temporária
        for f in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, f))
        os.rmdir(self.test_dir)

    def test_scraper_database_integration(self):
        """
        Testa a integração entre o scraper e o banco de dados.

        Verifica se os dados extraídos pelo scraper são corretamente
        armazenados no banco de dados.
        """
        scraper = OLXScraper(repository=self.repository)
        selector = OLXListingSelector()

        # Extrair dados do HTML de exemplo
        listings = selector.extract_listings(self.sample_html)

        # Processar cada anúncio e armazenar no banco de dados
        product_name = "iPhone 13"
        prices = []

        for listing in listings:
            # Usar a função process_listing do scraper para processar cada anúncio
            price = asyncio.run(scraper._process_listing(listing, product_name))
            if price:
                prices.append(price)

        # Verificar se os dados foram armazenados corretamente
        products = self.repository.get_products_by_name(product_name)

        # Deve haver 3 produtos
        self.assertEqual(len(products), 3)

        # Verificar se os preços correspondem
        stored_prices = [p["preco"] for p in products]
        self.assertIn(5999.0, stored_prices)
        self.assertIn(3500.0, stored_prices)
        self.assertIn(2800.0, stored_prices)

        # Verificar se o histórico de preços retorna os mesmos valores
        price_history = self.repository.get_product_price_history(product_name)
        history_prices = [p[1] for p in price_history]
        self.assertListEqual(sorted(history_prices), sorted(stored_prices))

    def test_scraper_analyzer_integration(self):
        """
        Testa a integração entre o scraper e o analisador.

        Verifica se os dados extraídos pelo scraper podem ser corretamente
        analisados pelo analisador de preços.
        """
        scraper = OLXScraper()
        selector = OLXListingSelector()

        # Extrair dados do HTML de exemplo
        listings = selector.extract_listings(self.sample_html)

        # Processar cada anúncio sem armazenar no banco de dados
        product_name = "iPhone 13"
        prices = []

        for listing in listings:
            # Processar o anúncio manualmente para evitar dependência do banco de dados
            price_text = listing.get('price_text')
            if price_text and "R$" in price_text:
                # Extrair o valor numérico do preço
                import re
                price_match = re.search(r'R\$\s*([\d.,]+)', price_text)
                if price_match:
                    price_str = price_match.group(1)
                    price = float(price_str.replace('.', '').replace(',', '.'))
                    prices.append(price)

        # Agora usar o analisador para analisar os preços
        analysis = self.analyzer.analyze_prices(prices)

        # Verificar se a análise contém os resultados esperados
        self.assertEqual(analysis['Total Anúncios'], 3)
        self.assertEqual(analysis['Anúncios Válidos'], 3)
        self.assertEqual(analysis['Mínimo'], 2800.0)
        self.assertEqual(analysis['Máximo'], 5999.0)

        # A média deve ser aproximadamente 4099.67
        self.assertAlmostEqual(analysis['Média'], 4099.67, delta=0.1)

        # Gerar um histograma
        histogram_path = self.analyzer.plot_histogram(prices, product_name)

        # Verificar se o histograma foi gerado
        self.assertTrue(os.path.exists(histogram_path))

        # Exportar para CSV
        csv_path = self.analyzer.export_to_csv({product_name: prices})
        self.assertTrue(os.path.exists(csv_path))

        # Exportar para JSON
        json_path = self.analyzer.save_analysis_json({product_name: analysis})
        self.assertTrue(os.path.exists(json_path))

    @patch('aiohttp.ClientSession')
    async def test_full_integration_mock(self, mock_session):
        """
        Testa o fluxo completo do scraper com mocks para chamadas HTTP.

        Esta é uma simulação completa do processo, desde a extração dos dados
        até a análise e armazenamento dos resultados.
        """
        # Configurar o mock para simular a resposta HTTP
        mock_response = MagicMock()
        mock_response.text = asyncio.Future()
        mock_response.text.set_result(self.sample_html)
        mock_response.raise_for_status = MagicMock()

        # Configurar o contexto assíncrono
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.__aenter__.return_value = mock_session_instance
        mock_session_instance.get.return_value.__aenter__.return_value = mock_response

        # Criar o scraper com o repositório
        scraper = OLXScraper(repository=self.repository)

        # Executar o scraper com o mock de HTTP
        product_name = "iPhone 13"
        prices = await scraper.scrape_product(product_name, max_pages=1)

        # Verificar se os preços foram extraídos corretamente
        self.assertEqual(len(prices), 3)
        self.assertIn(5999.0, prices)
        self.assertIn(3500.0, prices)
        self.assertIn(2800.0, prices)

        # Verificar se os dados foram armazenados no banco de dados
        products = self.repository.get_products_by_name(product_name)
        self.assertEqual(len(products), 3)

        # Analisar os preços
        analysis = self.analyzer.analyze_prices(prices)

        # Verificar a análise
        self.assertEqual(analysis['Total Anúncios'], 3)
        self.assertEqual(analysis['Anúncios Válidos'], 3)

        # Gerar visualizações
        histogram_path = self.analyzer.plot_histogram(prices, product_name)
        self.assertTrue(os.path.exists(histogram_path))

    def test_integration_selectors_extraction(self):
        """
        Testa a integração entre os seletores e a extração de dados.

        Verifica se os seletores conseguem extrair corretamente os dados
        do HTML de exemplo.
        """
        selector = OLXListingSelector()

        # Extrair os anúncios
        listings = selector.extract_listings(self.sample_html)

        # Verificar se três anúncios foram extraídos
        self.assertEqual(len(listings), 3)

        # Verificar o conteúdo do primeiro anúncio
        first_listing = listings[0]
        self.assertEqual(first_listing['title'], "iPhone 13 Pro Max 256GB")
        self.assertEqual(first_listing['price_text'], "R$ 5.999,00")
        self.assertEqual(first_listing['url'], "/item/123")

        # Verificar se a estratégia de fallback funciona
        original_selectors = selector.selectors

        # Configurar seletores inválidos para forçar o fallback
        selector.selectors = {
            'listings': 'invalid-selector',
            'price': 'invalid-price',
            'title': 'invalid-title',
            'link': 'invalid-link'
        }

        # Configurar o fallback para retornar os seletores originais
        selector.get_fallback_selectors = MagicMock(return_value=original_selectors)

        # Tentar extrair com seletores inválidos deve usar o fallback
        alternative_listings = selector.try_alternative_selectors(self.sample_html)

        # Verificar se o fallback foi usado e os dados foram extraídos
        selector.get_fallback_selectors.assert_called_once()
        self.assertEqual(len(alternative_listings), 3)

def async_test(coro):
    """
    Decorador para executar testes assíncronos.

    Args:
        coro: Coroutine a ser executada no teste.

    Returns:
        Função de teste que executa a coroutine.
    """
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper

if __name__ == '__main__':
    unittest.main()

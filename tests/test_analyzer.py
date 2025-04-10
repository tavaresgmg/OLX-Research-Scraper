"""
Testes unitários para o módulo de análise de dados.
"""

import unittest
import os
import tempfile
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use backend não-interativo para testes
from unittest.mock import patch, MagicMock

# Importando componentes para teste
from src.core.analyzer import PriceAnalyzer, analyze_product_prices

class TestPriceAnalyzer(unittest.TestCase):
    """Testes unitários para o analisador de preços."""

    def setUp(self):
        """Configuração inicial para cada teste."""
        # Criar um diretório temporário para os arquivos de saída
        self.test_dir = tempfile.mkdtemp()
        self.analyzer = PriceAnalyzer(output_dir=self.test_dir)

        # Dados de exemplo para testes
        self.sample_prices = [1000.0, 1200.0, 1300.0, 1250.0, 900.0, 950.0, 1100.0,
                            10000.0, 50.0]  # Os últimos são outliers

    def tearDown(self):
        """Limpeza após cada teste."""
        # Remover arquivos temporários
        for f in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, f))
        os.rmdir(self.test_dir)

    def test_remove_outliers_iqr(self):
        """Testa a remoção de outliers usando o método IQR."""
        # A lista tem outliers claros em 10000.0 e 50.0
        clean_data = self.analyzer.remove_outliers(self.sample_prices, method='iqr')

        # Verificar se os outliers foram removidos
        self.assertNotIn(10000.0, clean_data)
        self.assertNotIn(50.0, clean_data)

        # Verificar se os dados válidos foram mantidos
        self.assertEqual(len(clean_data), 7)  # Original tem 9, removemos 2 outliers

    def test_remove_outliers_zscore(self):
        """Testa a remoção de outliers usando o método Z-Score."""
        clean_data = self.analyzer.remove_outliers(self.sample_prices, method='zscore')

        # Verificar se o outlier extremo foi removido
        self.assertNotIn(10000.0, clean_data)

        # Z-Score pode não remover outliers menos extremos dependendo do threshold
        # então apenas verificamos que pelo menos 1 outlier foi removido
        self.assertLess(len(clean_data), len(self.sample_prices))

    def test_remove_outliers_invalid_method(self):
        """Testa o comportamento com método de remoção de outliers inválido."""
        result = self.analyzer.remove_outliers(self.sample_prices, method='invalid_method')

        # Deve retornar os dados originais sem modificação
        self.assertEqual(result, self.sample_prices)

    def test_analyze_prices(self):
        """Testa a análise estatística de preços."""
        analysis = self.analyzer.analyze_prices(self.sample_prices)

        # Verificar se todas as estatísticas esperadas estão presentes
        expected_keys = ['Média', 'Mediana', 'Mínimo', 'Máximo', 'Desvio Padrão',
                       'Variância', 'Total Anúncios', 'Anúncios Válidos',
                       'Percentil 25%', 'Percentil 75%', 'Moda']

        for key in expected_keys:
            self.assertIn(key, analysis)

        # Verificar valores específicos
        self.assertEqual(analysis['Total Anúncios'], 9)
        self.assertLess(analysis['Anúncios Válidos'], 9)  # Outliers removidos

        # Verificar se a média e mediana são valores numéricos razoáveis
        self.assertTrue(800 < analysis['Média'] < 1500)
        self.assertTrue(800 < analysis['Mediana'] < 1500)

    def test_analyze_prices_empty_list(self):
        """Testa o comportamento quando a lista de preços está vazia."""
        result = self.analyzer.analyze_prices([])
        self.assertIsNone(result)

    def test_analyze_prices_keep_outliers(self):
        """Testa análise sem remoção de outliers."""
        analysis = self.analyzer.analyze_prices(self.sample_prices, remove_outliers=False)

        # Todos os anúncios devem ser considerados válidos
        self.assertEqual(analysis['Total Anúncios'], analysis['Anúncios Válidos'])

        # Média deve ser afetada pelos outliers
        self.assertGreater(analysis['Média'], 1500)  # Com outlier de 10000, a média sobe

    def test_calculate_mode(self):
        """Testa o cálculo da moda."""
        # Lista com valor mais frequente claro
        data = [100.0, 200.0, 100.0, 300.0, 100.0, 400.0]
        mode = self.analyzer._calculate_mode(data)
        self.assertEqual(mode, 100.0)

        # Lista vazia
        self.assertEqual(self.analyzer._calculate_mode([]), 0.0)

    def test_plot_histogram(self):
        """Testa a geração de histograma."""
        output_path = self.analyzer.plot_histogram(
            self.sample_prices,
            "Produto Teste",
            output_format="png"
        )

        # Verificar se o arquivo foi criado
        self.assertTrue(os.path.exists(output_path))

        # Verificar o formato do arquivo
        self.assertTrue(output_path.endswith(".png"))

    def test_plot_histogram_empty_list(self):
        """Testa o comportamento ao tentar gerar um histograma com lista vazia."""
        output_path = self.analyzer.plot_histogram(
            [],
            "Produto Sem Dados",
            output_format="png"
        )

        # Deve retornar None quando não há dados
        self.assertIsNone(output_path)

    def test_plot_price_comparison(self):
        """Testa a geração de gráfico de comparação de preços."""
        # Dados de exemplo para dois produtos
        products_data = {
            "Produto A": [1000.0, 1200.0, 1100.0],
            "Produto B": [800.0, 850.0, 750.0]
        }

        output_path = self.analyzer.plot_price_comparison(
            products_data,
            output_format="png"
        )

        # Verificar se o arquivo foi criado
        self.assertTrue(os.path.exists(output_path))

        # Verificar o formato do arquivo
        self.assertTrue(output_path.endswith(".png"))

    def test_plot_price_comparison_insufficient_data(self):
        """Testa o comportamento quando não há dados suficientes para comparação."""
        # Caso 1: Apenas um produto
        result = self.analyzer.plot_price_comparison(
            {"Produto A": [1000.0, 1200.0]},
            output_format="png"
        )
        self.assertIsNone(result)

        # Caso 2: Nenhum produto
        result = self.analyzer.plot_price_comparison({}, output_format="png")
        self.assertIsNone(result)

    def test_export_to_csv(self):
        """Testa a exportação para CSV."""
        products_data = {
            "Produto A": [1000.0, 1200.0, 1100.0],
            "Produto B": [800.0, 850.0, 750.0]
        }

        output_path = self.analyzer.export_to_csv(products_data)

        # Verificar se o arquivo foi criado
        self.assertTrue(os.path.exists(output_path))

        # Verificar o formato do arquivo
        self.assertTrue(output_path.endswith(".csv"))

        # Verificar o conteúdo do arquivo (simples)
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("produto,preco", content)
            self.assertIn("Produto A", content)
            self.assertIn("Produto B", content)

    def test_save_analysis_json(self):
        """Testa a exportação da análise para JSON."""
        products_stats = {
            "Produto A": {
                "Média": 1100.0,
                "Mediana": 1100.0,
                "Mínimo": 1000.0,
                "Máximo": 1200.0
            },
            "Produto B": {
                "Média": 800.0,
                "Mediana": 800.0,
                "Mínimo": 750.0,
                "Máximo": 850.0
            }
        }

        output_path = self.analyzer.save_analysis_json(products_stats)

        # Verificar se o arquivo foi criado
        self.assertTrue(os.path.exists(output_path))

        # Verificar o formato do arquivo
        self.assertTrue(output_path.endswith(".json"))

        # Verificar o conteúdo do arquivo
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertIn("timestamp", data)
            self.assertIn("products", data)
            self.assertIn("Produto A", data["products"])
            self.assertIn("Produto B", data["products"])

    def test_sanitize_filename(self):
        """Testa a sanitização de nomes de arquivo."""
        test_cases = [
            ("Nome Normal", "Nome_Normal"),
            ("Nome Com Espaços", "Nome_Com_Espaços"),
            ("Nome-Com-Hifens", "Nome-Com-Hifens"),
            ("Nome Com Caracteres Especiais: !@#$%", "Nome_Com_Caracteres_Especiais_"),
            ("../../tentando/hackear/caminho", "tentando_hackear_caminho")
        ]

        for input_name, expected in test_cases:
            result = self.analyzer._sanitize_filename(input_name)
            self.assertEqual(result, expected)

class TestAnalyzeProductPrices(unittest.TestCase):
    """Testes para a função de conveniência analyze_product_prices."""

    def setUp(self):
        """Configuração inicial para cada teste."""
        self.test_dir = tempfile.mkdtemp()

        # Dados de exemplo para testes
        self.products_data = {
            "Produto A": [1000.0, 1200.0, 1100.0],
            "Produto B": [800.0, 850.0, 750.0]
        }

    def tearDown(self):
        """Limpeza após cada teste."""
        for f in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, f))
        os.rmdir(self.test_dir)

    @patch('src.core.analyzer.PriceAnalyzer')
    def test_analyze_product_prices(self, MockAnalyzer):
        """Testa se a função analyze_product_prices chama os métodos corretos."""
        # Configurar o mock
        mock_instance = MagicMock()
        MockAnalyzer.return_value = mock_instance

        # Chamar a função que queremos testar
        results = analyze_product_prices(
            self.products_data,
            output_dir=self.test_dir,
            generate_plots=True,
            export_csv=True,
            export_json=True
        )

        # Verificar se o analisador foi criado com o diretório correto
        MockAnalyzer.assert_called_once_with(output_dir=self.test_dir)

        # Verificar se os métodos esperados foram chamados
        self.assertEqual(mock_instance.analyze_prices.call_count, 2)  # Uma vez para cada produto
        self.assertEqual(mock_instance.plot_histogram.call_count, 2)  # Uma vez para cada produto
        mock_instance.plot_price_comparison.assert_called_once()
        mock_instance.export_to_csv.assert_called_once()
        mock_instance.save_analysis_json.assert_called_once()

if __name__ == '__main__':
    unittest.main()

"""
Componente de análise para o OLX Research Scraper.

Implementa funcionalidades para análise estatística e visualização
dos dados coletados pelo scraper.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from typing import List, Dict, Any, Optional, Tuple, Union
import json
from datetime import datetime
import pandas as pd
from pathlib import Path

# Importando os componentes do projeto
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Importar configurações usando caminho correto
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
sys.path.append(CONFIG_PATH)
from settings import HISTOGRAM_BINS, FIGURE_WIDTH, FIGURE_HEIGHT

from src.utils.helpers import setup_logging, format_currency

# Configuração do logger
logger = setup_logging(__name__)

class PriceAnalyzer:
    """
    Analisador de preços para dados coletados da OLX.

    Implementa funcionalidades para análise estatística e visualização
    dos dados de preços coletados pelo scraper.
    """

    def __init__(self, output_dir: str = "results"):
        """
        Inicializa o analisador com o diretório de saída.

        Args:
            output_dir: Diretório onde os resultados serão salvos.
        """
        self.output_dir = output_dir
        self.logger = logger

        # Garantir que o diretório de saída exista
        os.makedirs(self.output_dir, exist_ok=True)

    def remove_outliers(self, data: List[float], method: str = 'iqr') -> List[float]:
        """
        Remove outliers dos dados usando o método especificado.

        Args:
            data: Lista de preços para remover outliers.
            method: Método para remover outliers ('iqr' ou 'zscore').

        Returns:
            Lista de preços sem outliers.
        """
        if not data or len(data) < 4:
            return data

        if method == 'iqr':
            # Método IQR (Interquartile Range)
            q1, q3 = np.percentile(data, [25, 75])
            iqr = q3 - q1
            lower = q1 - (1.5 * iqr)
            upper = q3 + (1.5 * iqr)

            clean_data = [x for x in data if lower <= x <= upper]
            removed = len(data) - len(clean_data)
            self.logger.info(f"Método IQR: Removidos {removed} outliers ({removed/len(data):.1%})")

            return clean_data

        elif method == 'zscore':
            # Método Z-Score
            mean = np.mean(data)
            std = np.std(data)
            z_threshold = 3.0  # Este é um limiar padrão para z-score

            # Garantir que o desvio padrão não seja zero
            if std == 0:
                return data

            # Calcula a distância de cada valor da média em termos de desvios padrão
            clean_data = [x for x in data if abs((x - mean) / std) <= z_threshold]

            # Se não houver outliers detectados e houver valores muito discrepantes,
            # use um limiar mais rigoroso para casos extremos
            if len(clean_data) == len(data) and len(data) > 5:
                max_value = max(data)
                min_value = min(data)

                # Se o valor máximo for muito maior que a média ou o mínimo muito menor
                if max_value > mean * 5 or min_value < mean / 5:
                    z_threshold = 2.0  # Limiar mais rigoroso
                    clean_data = [x for x in data if abs((x - mean) / std) <= z_threshold]

            removed = len(data) - len(clean_data)
            self.logger.info(f"Método Z-Score: Removidos {removed} outliers ({removed/len(data):.1%})")

            return clean_data

        else:
            self.logger.warning(f"Método desconhecido: {method}. Usando dados originais.")
            return data

    def analyze_prices(self, prices: List[float], remove_outliers: bool = True,
                     outlier_method: str = 'iqr') -> Dict[str, Any]:
        """
        Realiza análise estatística de preços.

        Args:
            prices: Lista de preços para análise.
            remove_outliers: Se True, remove outliers antes da análise.
            outlier_method: Método para remoção de outliers.

        Returns:
            Dicionário com estatísticas calculadas.
        """
        if not prices:
            self.logger.warning("Nenhum preço válido para análise")
            return None

        # Remove outliers se solicitado
        if remove_outliers:
            clean_prices = self.remove_outliers(prices, outlier_method)
        else:
            clean_prices = prices

        if not clean_prices:
            self.logger.warning("Nenhum preço válido após remoção de outliers")
            return None

        # Calcula estatísticas básicas
        analysis = {
            'Média': float(np.mean(clean_prices)),
            'Mediana': float(np.median(clean_prices)),
            'Mínimo': float(np.min(clean_prices)),
            'Máximo': float(np.max(clean_prices)),
            'Desvio Padrão': float(np.std(clean_prices)),
            'Variância': float(np.var(clean_prices)),
            'Total Anúncios': len(prices),
            'Anúncios Válidos': len(clean_prices),
            'Percentil 25%': float(np.percentile(clean_prices, 25)),
            'Percentil 75%': float(np.percentile(clean_prices, 75)),
            'Moda': float(self._calculate_mode(clean_prices))
        }

        self.logger.info(f"Análise concluída: {len(clean_prices)} preços válidos")
        return analysis

    def _calculate_mode(self, data: List[float]) -> float:
        """
        Calcula a moda de uma lista de números.

        Args:
            data: Lista de números.

        Returns:
            Valor da moda (ou o primeiro valor se múltiplas modas).
        """
        if not data:
            return 0.0

        # Arredonda para o valor mais próximo para facilitar o cálculo da moda
        rounded = [round(x, 2) for x in data]
        unique, counts = np.unique(rounded, return_counts=True)

        # Encontra o índice do valor mais frequente
        if len(unique) > 0:
            mode_index = np.argmax(counts)
            return float(unique[mode_index])
        else:
            return float(data[0])

    def plot_histogram(self, prices: List[float], product_name: str,
                     output_format: str = 'png', show_stats: bool = True) -> str:
        """
        Gera um histograma de preços com estatísticas.

        Args:
            prices: Lista de preços para o histograma.
            product_name: Nome do produto (usado no título e nome do arquivo).
            output_format: Formato do arquivo de saída ('png', 'pdf', 'svg').
            show_stats: Se True, exibe estatísticas no gráfico.

        Returns:
            Caminho para o arquivo gerado.
        """
        if not prices:
            self.logger.warning(f"Nenhum preço para gerar histograma de {product_name}")
            return None

        # Limpa o nome do produto para usar no nome do arquivo
        safe_product_name = self._sanitize_filename(product_name)

        # Remove outliers para visualização
        clean_prices = self.remove_outliers(prices)

        # Configuração do matplotlib para caracteres especiais
        plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # Cria a figura
        plt.figure(figsize=(FIGURE_WIDTH, FIGURE_HEIGHT))

        # Gera o histograma
        n, bins, patches = plt.hist(clean_prices, bins=HISTOGRAM_BINS,
                                  color='dodgerblue', edgecolor='black', alpha=0.7)

        # Adiciona linha para média e mediana
        mean = np.mean(clean_prices)
        median = np.median(clean_prices)

        plt.axvline(mean, color='red', linestyle='dashed', linewidth=1.5,
                   label=f'Média: {format_currency(mean)}')
        plt.axvline(median, color='green', linestyle='dashed', linewidth=1.5,
                   label=f'Mediana: {format_currency(median)}')

        # Configurações do gráfico
        plt.title(f'Distribuição de Preços - {product_name}', fontsize=14)
        plt.xlabel('Preço (R$)', fontsize=12)
        plt.ylabel('Frequência', fontsize=12)
        plt.grid(True, alpha=0.3)

        # Formata os valores do eixo X como moeda
        formatter = mticker.FuncFormatter(lambda x, pos: f'R$ {x:,.0f}')
        plt.gca().xaxis.set_major_formatter(formatter)

        # Adiciona estatísticas no gráfico
        if show_stats:
            stats = self.analyze_prices(prices)
            if stats:
                stats_text = (
                    f"Total: {stats['Total Anúncios']} anúncios\n"
                    f"Média: {format_currency(stats['Média'])}\n"
                    f"Mediana: {format_currency(stats['Mediana'])}\n"
                    f"Mín: {format_currency(stats['Mínimo'])}\n"
                    f"Máx: {format_currency(stats['Máximo'])}\n"
                    f"Desvio: {format_currency(stats['Desvio Padrão'])}"
                )

                plt.annotate(stats_text, xy=(0.02, 0.98), xycoords='axes fraction',
                           fontsize=9, verticalalignment='top',
                           bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))

        # Adiciona legenda
        plt.legend(loc='upper right')

        # Salva a figura
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{safe_product_name}_histograma_{timestamp}.{output_format}"
        output_path = os.path.join(self.output_dir, filename)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300)
        plt.close()

        self.logger.info(f"Histograma salvo em: {output_path}")
        return output_path

    def plot_price_comparison(self, products_data: Dict[str, List[float]],
                            output_format: str = 'png') -> str:
        """
        Gera um gráfico de comparação de preços entre produtos.

        Args:
            products_data: Dicionário com nome dos produtos e listas de preços.
            output_format: Formato do arquivo de saída.

        Returns:
            Caminho para o arquivo gerado.
        """
        if not products_data or len(products_data) < 2:
            self.logger.warning("Dados insuficientes para comparação de preços")
            return None

        # Calcula estatísticas para cada produto
        products_stats = {}
        for product_name, prices in products_data.items():
            if prices:
                stats = self.analyze_prices(prices)
                if stats:
                    products_stats[product_name] = stats

        if len(products_stats) < 2:
            self.logger.warning("Estatísticas insuficientes para comparação")
            return None

        # Extrai nomes dos produtos e valores medianos (usamos mediana por ser mais representativa)
        product_names = list(products_stats.keys())
        median_values = [stats['Mediana'] for stats in products_stats.values()]

        # Configuração do matplotlib
        plt.figure(figsize=(FIGURE_WIDTH, FIGURE_HEIGHT))

        # Cria gráfico de barras
        bars = plt.bar(product_names, median_values, color='skyblue', edgecolor='black', alpha=0.7)

        # Adiciona valor em cima das barras
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.05 * max(median_values),
                    f'R$ {height:,.2f}', ha='center', va='bottom', rotation=0)

        # Configurações do gráfico
        plt.title('Comparação de Preços Medianos', fontsize=14)
        plt.ylabel('Preço Mediano (R$)', fontsize=12)
        plt.grid(True, alpha=0.3, axis='y')

        # Formata os valores do eixo Y como moeda
        formatter = mticker.FuncFormatter(lambda x, pos: f'R$ {x:,.0f}')
        plt.gca().yaxis.set_major_formatter(formatter)

        # Rotaciona os rótulos do eixo X se forem muitos produtos
        if len(product_names) > 3:
            plt.xticks(rotation=45, ha='right')

        # Salva a figura
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"comparacao_precos_{timestamp}.{output_format}"
        output_path = os.path.join(self.output_dir, filename)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300)
        plt.close()

        self.logger.info(f"Gráfico de comparação salvo em: {output_path}")
        return output_path

    def export_to_csv(self, products_data: Dict[str, List[float]]) -> str:
        """
        Exporta os dados para um arquivo CSV.

        Args:
            products_data: Dicionário com nome dos produtos e listas de preços.

        Returns:
            Caminho para o arquivo gerado.
        """
        if not products_data:
            self.logger.warning("Nenhum dado para exportar para CSV")
            return None

        # Cria um DataFrame com os dados
        data_frames = []

        for product_name, prices in products_data.items():
            if prices:
                df = pd.DataFrame({
                    'produto': product_name,
                    'preco': prices
                })
                data_frames.append(df)

        if not data_frames:
            self.logger.warning("Nenhum dado válido para exportar")
            return None

        # Concatena os DataFrames
        result_df = pd.concat(data_frames, ignore_index=True)

        # Salva o DataFrame como CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"dados_precos_{timestamp}.csv"
        output_path = os.path.join(self.output_dir, filename)

        result_df.to_csv(output_path, index=False, encoding='utf-8')

        self.logger.info(f"Dados exportados para CSV: {output_path}")
        return output_path

    def save_analysis_json(self, products_stats: Dict[str, Dict[str, Any]]) -> str:
        """
        Salva os resultados da análise em um arquivo JSON.

        Args:
            products_stats: Dicionário com estatísticas por produto.

        Returns:
            Caminho para o arquivo gerado.
        """
        if not products_stats:
            self.logger.warning("Nenhum dado para salvar como JSON")
            return None

        # Adiciona timestamp
        result = {
            'timestamp': datetime.now().isoformat(),
            'products': products_stats
        }

        # Salva como JSON
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"analise_precos_{timestamp}.json"
        output_path = os.path.join(self.output_dir, filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Análise salva em JSON: {output_path}")
        return output_path

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitiza uma string para uso seguro como nome de arquivo.

        Args:
            filename: String para sanitizar.

        Returns:
            String sanitizada.
        """
        # Tratar especificamente tentativas de path traversal
        if filename.startswith("../") or filename.startswith("./") or "../" in filename:
            filename = filename.replace("../", "").replace("./", "")

        # Substitui caracteres especiais por underscores
        sanitized = ''
        for c in filename:
            if c.isalnum() or c in '._- ':
                sanitized += c
            else:
                sanitized += '_'

        # Remove espaços extras e substitui por underscore
        sanitized = '_'.join(sanitized.split())

        # Remove sequências de underscores, deixando apenas um
        while '__' in sanitized:
            sanitized = sanitized.replace('__', '_')

        return sanitized

# Função para uso direto do módulo
def analyze_product_prices(products_data: Dict[str, List[float]],
                         output_dir: str = "results",
                         generate_plots: bool = True,
                         export_csv: bool = True,
                         export_json: bool = True) -> Dict[str, Dict[str, Any]]:
    """
    Analisa preços para múltiplos produtos.

    Args:
        products_data: Dicionário com nome dos produtos e listas de preços.
        output_dir: Diretório para salvar resultados.
        generate_plots: Se True, gera gráficos.
        export_csv: Se True, exporta dados para CSV.
        export_json: Se True, exporta análise para JSON.

    Returns:
        Dicionário com estatísticas por produto.
    """
    analyzer = PriceAnalyzer(output_dir=output_dir)
    results = {}

    # Analisa cada produto
    for product_name, prices in products_data.items():
        if prices:
            stats = analyzer.analyze_prices(prices)
            if stats:
                results[product_name] = stats

                if generate_plots:
                    analyzer.plot_histogram(prices, product_name)

    # Gera comparação se houver múltiplos produtos
    if generate_plots and len(results) >= 2:
        analyzer.plot_price_comparison(products_data)

    # Exporta dados se solicitado
    if export_csv:
        analyzer.export_to_csv(products_data)

    # Exporta análise se solicitado
    if export_json:
        analyzer.save_analysis_json(results)

    return results

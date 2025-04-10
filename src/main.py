"""
Ponto de entrada principal para o OLX Research Scraper.

Integra todos os componentes e fornece uma interface de linha de comando
para configurar e executar o scraper com diferentes opções.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import textwrap
from typing import List, Dict, Any
from multiprocessing import Pool, freeze_support

# Importando os componentes do projeto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar configurações usando caminho correto
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
sys.path.append(CONFIG_PATH)
from settings import DEFAULT_PAGES, DEFAULT_STATE

from src.core.scraper import OLXScraper, scrape_products
from src.core.analyzer import PriceAnalyzer, analyze_product_prices
from src.services.database import ProductRepository
from src.utils.helpers import setup_logging, format_currency

# Configuração do logger
logger = setup_logging(__name__)

def process_product(product_name: str, args: argparse.Namespace) -> Dict[str, Any]:
    """
    Processa um produto: extrai dados, armazena no banco e realiza análise.

    Args:
        product_name: Nome do produto a ser processado.
        args: Argumentos da linha de comando com configurações.

    Returns:
        Dicionário com resultados da análise ou None em caso de falha.
    """
    print(f"\n{'='*60}")
    print(f"INICIANDO ANÁLISE PARA: {product_name}")
    print(f"{'='*60}")

    start_time = time.time()

    try:
        # Configurar o repositório
        repository = ProductRepository(args.database)
        repository.initialize_database()

        # Coletar os preços
        scraper = OLXScraper(
            state=args.estado,
            min_price=args.min_preco,
            max_price=args.max_preco,
            repository=repository if args.salvar_banco else None,
            use_cache=not args.no_cache
        )

        prices = asyncio.run(scraper.scrape_product(product_name, args.paginas))

        if not prices:
            print(f"\n[FALHA] Nenhum preço válido coletado para {product_name}")
            return None

        # Analisar os preços
        analyzer = PriceAnalyzer(output_dir=args.output)

        # Define o método de remoção de outliers
        outlier_method = 'zscore' if args.zscore else 'iqr'

        # Analisa os preços
        analysis = analyzer.analyze_prices(prices, remove_outliers=not args.keep_outliers,
                                         outlier_method=outlier_method)

        if not analysis:
            print(f"\n[AVISO] Dados insuficientes para análise estatística de {product_name}")
            return None

        # Exibe os resultados
        print(f"\n{'-'*60}")
        print(f"RESULTADOS PARA: {product_name}")
        print(f"{'-'*60}")
        print(f"🔍 Anúncios analisados: {analysis['Total Anúncios']}")
        print(f"✅ Anúncios válidos: {analysis['Anúncios Válidos']}")
        print(f"📊 Média de preço: {format_currency(analysis['Média'])}")
        print(f"📈 Mediana de preço: {format_currency(analysis['Mediana'])}")
        print(f"⬇️  Preço mínimo: {format_currency(analysis['Mínimo'])}")
        print(f"⬆️  Preço máximo: {format_currency(analysis['Máximo'])}")
        print(f"📉 Desvio padrão: {format_currency(analysis['Desvio Padrão'])}")
        print(f"📊 Moda: {format_currency(analysis['Moda'])}")

        # Gera o histograma se solicitado
        if args.visualizacao:
            histogram_path = analyzer.plot_histogram(prices, product_name,
                                                  output_format=args.formato)
            if histogram_path:
                print(f"📊 Histograma gerado: {histogram_path}")

        # Exporta para CSV se solicitado
        if args.csv:
            csv_path = analyzer.export_to_csv({product_name: prices})
            if csv_path:
                print(f"📄 Dados exportados para CSV: {csv_path}")

        # Exporta para JSON se solicitado
        if args.json:
            json_path = analyzer.save_analysis_json({product_name: analysis})
            if json_path:
                print(f"📄 Análise exportada para JSON: {json_path}")

        elapsed_time = time.time() - start_time
        print(f"\n⏱️  Tempo de processamento: {elapsed_time:.2f} segundos")

        return {product_name: analysis}

    except Exception as e:
        logger.error(f"Erro ao processar produto {product_name}: {e}", exc_info=True)
        print(f"\n[ERRO] Falha ao processar {product_name}: {e}")
        return None

def main():
    """Função principal do programa."""

    # Em Windows, necessário para multiprocessing
    if sys.platform == 'win32':
        freeze_support()

    # Configurar argumentos da linha de comando
    parser = argparse.ArgumentParser(
        description="OLX Research Scraper - Ferramenta para análise de preços na OLX",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Exemplos:
          python src/main.py "iphone 13"
          python src/main.py "iphone 13, galaxy s22" -p 5 -e estado-sp
          python src/main.py "playstation 5" -p 10 --csv --json -o resultados
        """)
    )

    # Argumentos obrigatórios
    parser.add_argument('produtos', type=str,
                      help='Lista de produtos para pesquisa (separados por vírgula)')

    # Argumentos opcionais
    parser.add_argument('-p', '--paginas', type=int, default=DEFAULT_PAGES,
                      help=f'Número de páginas para analisar por produto (padrão: {DEFAULT_PAGES})')

    parser.add_argument('-e', '--estado', type=str, default=DEFAULT_STATE,
                      help=f'Estado para realizar a busca (ex: estado-sp, estado-go) (padrão: {DEFAULT_STATE})')

    parser.add_argument('-o', '--output', type=str, default='results',
                      help='Diretório para salvar os resultados (padrão: results)')

    parser.add_argument('--min-preco', type=float, default=50,
                      help='Preço mínimo a considerar (padrão: 50)')

    parser.add_argument('--max-preco', type=float, default=100000,
                      help='Preço máximo a considerar (padrão: 100000)')

    parser.add_argument('--database', type=str, default='data/olx_precos.db',
                      help='Caminho para o banco de dados SQLite (padrão: data/olx_precos.db)')

    parser.add_argument('--formato', type=str, choices=['png', 'pdf', 'svg'], default='png',
                      help='Formato dos gráficos gerados (padrão: png)')

    # Flags
    parser.add_argument('--no-visual', dest='visualizacao', action='store_false',
                      help='Não gerar visualizações')

    parser.add_argument('--csv', action='store_true',
                      help='Exportar dados para CSV')

    parser.add_argument('--json', action='store_true',
                      help='Exportar análise para JSON')

    parser.add_argument('--keep-outliers', action='store_true',
                      help='Manter outliers na análise')

    parser.add_argument('--zscore', action='store_true',
                      help='Usar método Z-Score para remoção de outliers (padrão: IQR)')

    parser.add_argument('--comparar', action='store_true',
                      help='Gerar gráfico de comparação entre produtos')

    parser.add_argument('--sequential', action='store_true',
                      help='Executar sequencialmente (sem multiprocessing)')

    parser.add_argument('--no-cache', action='store_true',
                      help='Desativar cache de URLs')

    parser.add_argument('--no-banco', dest='salvar_banco', action='store_false',
                      help='Não salvar dados no banco SQLite')

    parser.add_argument('--debug', action='store_true',
                      help='Ativar modo de depuração (logs detalhados)')

    # Configurar a aplicação com base nos argumentos
    args = parser.parse_args()

    # Configurar o nível de log baseado no argumento de debug
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Modo de depuração ativado")

    # Limpar e processar a lista de produtos
    product_list = [p.strip() for p in args.produtos.split(',') if p.strip()]

    if not product_list:
        parser.error("Nenhum produto válido especificado")

    # Garantir que o diretório de saída exista
    os.makedirs(args.output, exist_ok=True)

    # Processar cada produto (com ou sem multiprocessing)
    all_results = {}

    print(f"\n{'='*60}")
    print(f"OLX RESEARCH SCRAPER - INICIANDO ANÁLISE")
    print(f"{'='*60}")
    print(f"Produtos: {', '.join(product_list)}")
    print(f"Páginas por produto: {args.paginas}")
    print(f"Estado: {args.estado}")
    print(f"{'='*60}\n")

    start_time = time.time()

    if args.sequential or len(product_list) == 1:
        # Execução sequencial
        for product in product_list:
            result = process_product(product, args)
            if result:
                all_results.update(result)
    else:
        # Execução com multiprocessing
        with Pool(processes=min(len(product_list), os.cpu_count())) as pool:
            results = pool.starmap(process_product, [(product, args) for product in product_list])

            for result in results:
                if result:
                    all_results.update(result)

    # Gerar comparação entre produtos se solicitado
    if args.comparar and len(all_results) >= 2:
        try:
            print("\nGerando comparação entre produtos...")

            # Precisamos dos preços originais, não apenas as estatísticas
            # Vamos coletar novamente usando o repositório
            product_prices = {}
            repository = ProductRepository(args.database)

            for product_name in all_results.keys():
                # Tentar obter do banco primeiro
                try:
                    products = repository.get_products_by_name(product_name)
                    if products:
                        product_prices[product_name] = [p['preco'] for p in products]
                        continue
                except Exception:
                    pass

                # Se não conseguir do banco, tentar coletar novamente
                scraper = OLXScraper(
                    state=args.estado,
                    min_price=args.min_preco,
                    max_price=args.max_preco
                )
                prices = asyncio.run(scraper.scrape_product(product_name, args.paginas))
                if prices:
                    product_prices[product_name] = prices

            # Gerar o gráfico de comparação
            analyzer = PriceAnalyzer(output_dir=args.output)
            comparison_path = analyzer.plot_price_comparison(product_prices, output_format=args.formato)

            if comparison_path:
                print(f"📊 Gráfico de comparação gerado: {comparison_path}")

        except Exception as e:
            logger.error(f"Erro ao gerar comparação: {e}", exc_info=True)
            print(f"[ERRO] Falha ao gerar comparação: {e}")

    # Finalização
    total_time = time.time() - start_time
    product_count = len(all_results)

    print(f"\n{'='*60}")
    print(f"ANÁLISE CONCLUÍDA")
    print(f"{'='*60}")
    print(f"Produtos analisados com sucesso: {product_count} de {len(product_list)}")
    print(f"Tempo total de execução: {total_time:.2f} segundos")
    print(f"{'='*60}")

    return 0

if __name__ == "__main__":
    sys.exit(main())

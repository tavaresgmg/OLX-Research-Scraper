import argparse
from multiprocessing import Pool
from scraper import get_prices_async
from analysis import analyze_prices, plot_histogram
from database import Database
import asyncio
import logging

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_product(product_name, max_pages):
    print(f"\n=== INICIANDO ANÁLISE PARA {product_name} ===")

    # Configurar o banco de dados
    db = Database()
    db.connect()
    db.create_table()

    # Coletar os preços
    prices = asyncio.run(get_prices_async(product_name, max_pages, db))

    db.close()

    if not prices:
        print(f"\n[FALHA] Nenhum preço válido coletado para {product_name}")
        return None

    analysis = analyze_prices(prices)
    if analysis:
        print(f"\n=== RESULTADOS PARA {product_name} ===")
        print(f"🔍 Anúncios analisados: {analysis['Total Anúncios']}")
        print(f"✅ Anúncios válidos: {analysis['Anúncios Válidos']}")
        print(f"📊 Média de preço: R$ {analysis['Média']:,.2f}")
        print(f"📈 Mediana de preço: R$ {analysis['Mediana']:,.2f}")
        print(f"⬇️  Preço mínimo: R$ {analysis['Mínimo']:,.2f}")
        print(f"⬆️  Preço máximo: R$ {analysis['Máximo']:,.2f}")
        print(f"📉 Desvio padrão: R$ {analysis['Desvio Padrão']:,.2f}")
        plot_histogram(prices, product_name)
        return analysis
    else:
        print(f"\n[AVISO] Dados insuficientes para análise estatística de {product_name}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Analisador de preços OLX')
    parser.add_argument('produtos', type=str, help='Lista de produtos para pesquisa (separados por vírgula)')
    parser.add_argument('-p', '--paginas', type=int, default=3, help='Número de páginas para analisar por produto')
    args = parser.parse_args()

    product_list = [p.strip() for p in args.produtos.split(',')]

    # Execução em Multiprocessing
    with Pool(processes=len(product_list)) as pool:
        results = pool.starmap(process_product, [(product, args.paginas) for product in product_list])

    print("\n=== ANÁLISE CONCLUÍDA ===")

if __name__ == "__main__":
    main()
import numpy as np
import matplotlib.pyplot as plt

def remove_outliers(data):
    if len(data) < 4:
        return data

    q1, q3 = np.percentile(data, [25, 75])
    iqr = q3 - q1
    lower = q1 - (1.5 * iqr)
    upper = q3 + (1.5 * iqr)

    return [x for x in data if lower <= x <= upper]

def analyze_prices(prices):
    if not prices:
        return None

    clean_prices = remove_outliers(prices)

    return {
        'Média': np.mean(clean_prices),
        'Mediana': np.median(clean_prices),
        'Mínimo': np.min(clean_prices),
        'Máximo': np.max(clean_prices),
        'Desvio Padrão': np.std(clean_prices),
        'Total Anúncios': len(prices),
        'Anúncios Válidos': len(clean_prices)
    }

def plot_histogram(prices, product_name):
    plt.figure(figsize=(10, 5))
    plt.hist(prices, bins=20, color='blue', edgecolor='black')
    plt.title(f'Distribuição de Preços - {product_name}')
    plt.xlabel('Preço (R$)')
    plt.ylabel('Frequência')
    plt.grid(True)
    plt.savefig(f'{product_name}_histograma.png')
    plt.close()
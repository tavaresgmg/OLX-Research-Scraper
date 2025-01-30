import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
from fake_useragent import UserAgent
import logging
import numpy as np

async def fetch(session, url):
    ua = UserAgent()
    headers = {
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.olx.com.br/',
        'DNT': '1',
        'Upgrade-Insecure-Requests': '1'
    }
    try:
        async with session.get(url, headers=headers, timeout=20) as response:
            response.raise_for_status()
            return await response.text()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logging.error(f"Erro ao acessar {url}: {e}")
        return None

async def scrape_page(session, url, product_name, database):
    prices = []
    html = await fetch(session, url)
    if html is None:
        return prices

    soup = BeautifulSoup(html, 'html.parser')

    listings = soup.select('section[data-ds-component="DS-AdCard"]')

    if not listings:
        logging.warning(f"Nenhum anúncio encontrado em {url}")
        return prices

    for listing in listings:
        try:
            price_tag = listing.select_one('h3[data-ds-component="DS-Text"].olx-ad-card__price')
            if not price_tag:
                logging.debug("Preço não encontrado em um anúncio.")
                continue

            price_text = price_tag.text.strip()

            link_tag = listing.select_one('a')
            ad_link = link_tag['href'] if link_tag else "Link não encontrado"

            title_tag = listing.select_one('h2[data-ds-component="DS-Text"].olx-ad-card__title')
            title = title_tag.text.strip() if title_tag else "Título não encontrado"

            price_match = re.search(r'R\$\s*([\d.,]+)', price_text)
            if not price_match:
                logging.debug(f"Formato de preço inválido: {price_text}")
                continue

            price_str = price_match.group(1)
            price = float(price_str.replace('.', '').replace(',', '.'))

            if 50 < price < 100000:
                prices.append(price)
                logging.info(f"Preço válido encontrado: R$ {price:,.2f} - URL: {ad_link} - Título: {title}")
                database.insert_data(product_name, price, ad_link, title)
            else:
                logging.warning(f"Preço fora da faixa: R$ {price:,.2f} - URL: {ad_link} - Título: {title}")

        except Exception as e:
            logging.error(f"Erro ao processar um anúncio: {e}")

    return prices

async def get_prices_async(product_name, max_pages, database):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for page in range(1, max_pages + 1):
            url = f'https://www.olx.com.br/estado-go?q={product_name.replace(" ", "%20")}&o={page}'
            logging.info(f"Agendando raspagem da página {page}: {url}")
            tasks.append(scrape_page(session, url, product_name, database))
            await asyncio.sleep(np.random.uniform(0.2, 0.5))

        results = await asyncio.gather(*tasks)
        all_prices = [price for sublist in results for price in sublist]
        return all_prices
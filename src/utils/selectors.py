"""
Utilitários para seletores CSS com estratégia de dois estágios para scraping.

Este módulo implementa uma abordagem de seletores CSS em dois estágios:
1. Estrutural: verifica a estrutura geral da página e identifica regiões relevantes
2. Dados: extrai dados específicos dentro das regiões identificadas
"""

import logging
import re
from typing import Optional, List, Tuple, Any, Dict, Callable
from bs4 import BeautifulSoup, Tag

# Importando configurações
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Importar configurações usando caminho correto
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
sys.path.append(CONFIG_PATH)
from settings import CSS_SELECTORS
from src.utils.helpers import setup_logging

logger = setup_logging(__name__)

class SelectorError(Exception):
    """Exceção para erros relacionados a seletores."""
    pass

class PageStructureChangedError(SelectorError):
    """Exceção para quando a estrutura da página mudou."""
    pass

class Selector:
    """
    Classe base para seletores que implementa o padrão de dois estágios.
    """

    def __init__(self, structural_selector: str, data_selector: str,
                 required: bool = True, description: str = None):
        """
        Inicializa um seletor de dois estágios.

        Args:
            structural_selector: Seletor CSS que identifica uma região estrutural da página.
            data_selector: Seletor CSS relativo que extrai dados dentro da região estrutural.
            required: Se True, lançará exceção quando o seletor estrutural não encontrar elementos.
            description: Descrição do que este seletor busca (para logs e depuração).
        """
        self.structural_selector = structural_selector
        self.data_selector = data_selector
        self.required = required
        self.description = description or f"Seletor {structural_selector} > {data_selector}"

    def find_structures(self, soup: BeautifulSoup) -> List[Tag]:
        """
        Encontra todas as estruturas que correspondem ao seletor estrutural.

        Args:
            soup: Objeto BeautifulSoup da página.

        Returns:
            Lista de elementos Tag que correspondem ao seletor estrutural.

        Raises:
            PageStructureChangedError: Se o seletor estrutural é obrigatório e não encontrou elementos.
        """
        structures = soup.select(self.structural_selector)

        if not structures and self.required:
            error_msg = f"Estrutura da página mudou. Seletor não encontrou: {self.structural_selector}"
            logger.error(error_msg)
            raise PageStructureChangedError(error_msg)

        logger.debug(f"Encontrados {len(structures)} elementos com seletor estrutural: {self.structural_selector}")
        return structures

    def extract_data(self, structure: Tag) -> Optional[Tag]:
        """
        Extrai dados de uma estrutura usando o seletor de dados relativo.

        Args:
            structure: Elemento Tag que foi encontrado pelo seletor estrutural.

        Returns:
            Elemento Tag encontrado pelo seletor de dados ou None se não encontrado.
        """
        data_element = structure.select_one(self.data_selector)

        if data_element is None:
            logger.debug(f"Seletor de dados não encontrou elemento: {self.data_selector}")

        return data_element

    def extract_all(self, soup: BeautifulSoup) -> List[Tag]:
        """
        Aplica o padrão de dois estágios e retorna todos os elementos de dados encontrados.

        Args:
            soup: Objeto BeautifulSoup da página.

        Returns:
            Lista de elementos Tag encontrados pelos seletores.
        """
        results = []

        try:
            structures = self.find_structures(soup)

            for structure in structures:
                data_element = self.extract_data(structure)
                if data_element:
                    results.append(data_element)

            logger.debug(f"Extraídos {len(results)} elementos de dados usando {self.description}")
            return results

        except PageStructureChangedError:
            if self.required:
                raise
            return []

class OLXListingSelector:
    """
    Seletor para extrair dados dos anúncios da OLX.

    Implementa estratégia de seletores múltiplos com fallback para
    lidar com mudanças na estrutura da página.
    """

    def __init__(self):
        """Inicializa os seletores CSS principais."""
        # Seletores principais
        self.selectors = {
            'listings': 'section[data-ds-component="DS-AdCard"]',
            'title': 'h2[data-ds-component="DS-Text"]',
            'price': 'h3[data-ds-component="DS-Text"]',
            'link': 'a'
        }

        # Lista de conjuntos de seletores alternativos
        self.fallback_selectors = [
            # Fallback 1 - Versão alternativa encontrada na análise com Playwright
            {
                'listings': 'section[data-ds-component="DS-AdCard"]',
                'title': 'h2[data-ds-component="DS-Text"]',
                'price': 'span[data-ds-component="DS-Text"]',  # Novo seletor para o preço
                'link': 'a[data-ds-component="DS-NewAdCard-Link"]'  # Novo seletor para o link
            },
            # Fallback 2 - Versão alternativa antiga
            {
                'listings': 'div.sc-9190c537-2',
                'title': 'h2.sc-1iuc9a2-1',
                'price': 'span.m7nrfa-0',
                'link': 'a.kgl1mq-0'
            },
            # Fallback 3 - Outra versão alternativa antiga
            {
                'listings': 'li.ej84nb0',
                'title': 'div.ej84nb3',
                'price': 'div.ej84nb5',
                'link': 'a.ej84nb8'
            }
        ]

        # Número máximo de tentativas de fallback
        self.max_fallback_attempts = 3

    def extract_listings(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Extrai os dados dos anúncios a partir do HTML da página.

        Args:
            html_content: Conteúdo HTML da página a ser processado.

        Returns:
            Lista de dicionários com os dados dos anúncios.
        """
        try:
            # Nova abordagem: primeiro tenta método direto
            results = self.extract_listings_directly(html_content)
            if results:
                return results

            # Se não der certo, tenta a abordagem antiga
            soup = BeautifulSoup(html_content, 'html.parser')
            listing_elements = soup.select(self.selectors['listings'])

            # Se não encontrou nenhum anúncio, tenta com seletores alternativos
            if not listing_elements:
                logger.warning("Nenhum anúncio encontrado com os seletores principais, tentando alternativas.")
                return self.try_alternative_selectors(html_content)

            # Extrai os dados de cada anúncio
            return self._extract_data_from_elements(listing_elements)

        except Exception as e:
            logger.error(f"Erro ao extrair dados dos anúncios: {str(e)}")
            # Tenta recuperar usando seletores alternativos
            try:
                return self.try_alternative_selectors(html_content)
            except PageStructureChangedError:
                logger.critical("Todos os seletores falharam. Estrutura da página mudou significativamente.")
                return []

    def extract_listings_directly(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Extrai os dados dos anúncios diretamente, usando uma abordagem mais robusta.
        Esta é uma nova implementação para lidar com mudanças na estrutura da página.

        Args:
            html_content: Conteúdo HTML da página a ser processado.

        Returns:
            Lista de dicionários com os dados dos anúncios.
        """
        try:
            logger.debug("Iniciando extração direta dos anúncios")
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []

            # Seleciona todos os cards de anúncios
            ad_cards = soup.select('section[data-ds-component="DS-AdCard"]')
            logger.debug(f"Encontrados {len(ad_cards)} anúncios na extração direta")

            if not ad_cards:
                logger.debug("Nenhum anúncio encontrado na extração direta")
                return []

            # Para cada card, extrai as informações
            for i, card in enumerate(ad_cards):
                # Título
                title_element = card.select_one('h2[data-ds-component="DS-Text"]')
                title = title_element.text.strip() if title_element else 'Sem título'

                # Preço - tenta ambos os seletores (h3 e span)
                price_element = card.select_one('h3[data-ds-component="DS-Text"]')
                if not price_element:
                    price_element = card.select_one('span[data-ds-component="DS-Text"]')

                price_text = price_element.text.strip() if price_element else None

                # URL
                link_element = card.select_one('a')
                url = link_element.get('href') if link_element else None

                # Se conseguimos extrair o texto do preço, processamos para obter o valor numérico
                if price_text:
                    logger.debug(f"Anúncio {i+1}: Título: {title}, Preço: {price_text}, URL: {url}")
                    results.append({
                        'title': title,
                        'price_text': price_text,
                        'url': url
                    })

            logger.debug(f"Extração direta concluída com {len(results)} anúncios")
            return results

        except Exception as e:
            logger.error(f"Erro na extração direta: {str(e)}")
            return []

    def _extract_data_from_elements(self, listing_elements) -> List[Dict[str, Any]]:
        """
        Extrai os dados de cada elemento de anúncio.

        Args:
            listing_elements: Lista de elementos BeautifulSoup representando anúncios.

        Returns:
            Lista de dicionários com os dados extraídos.
        """
        listings = []
        logger.debug(f"Iniciando extração de dados de {len(listing_elements)} anúncios")

        for i, element in enumerate(listing_elements):
            # Extrai título
            title_element = element.select_one(self.selectors['title'])
            title = title_element.text.strip() if title_element else None
            logger.debug(f"Anúncio {i+1}: Título: {title}")

            # Extrai preço - Tenta com o seletor principal, mas se não encontrar tenta alternativo
            price_element = element.select_one(self.selectors['price'])
            if not price_element:
                # Tenta um seletor mais genérico como fallback
                price_element = element.select_one('span[data-ds-component="DS-Text"]')

            price_text = price_element.text.strip() if price_element else None
            logger.debug(f"Anúncio {i+1}: Texto do preço: {price_text}")

            # Extrai URL
            link_element = element.select_one(self.selectors['link'])
            url = link_element.get('href') if link_element else None
            logger.debug(f"Anúncio {i+1}: URL: {url}")

            # Processa o preço para extrair o valor numérico
            price_value = self._extract_price_value(price_text) if price_text else None
            logger.debug(f"Anúncio {i+1}: Valor do preço extraído: {price_value}")

            # Adiciona os dados extraídos à lista
            listings.append({
                'title': title,
                'price_text': price_text,
                'price_value': price_value,
                'url': url
            })

        logger.debug(f"Extração completa. Obtidos {len(listings)} anúncios.")
        return listings

    def _extract_price_value(self, price_text: str) -> Optional[float]:
        """
        Extrai o valor numérico do preço a partir do texto.

        Args:
            price_text: Texto contendo o preço (ex: "R$ 1.999,00").

        Returns:
            Valor numérico do preço ou None se não for possível extrair.
        """
        try:
            if not price_text:
                logger.debug("Texto de preço vazio")
                return None

            # Detecta e trata o formato de parcelas (ex: "3x de R$ 333,33")
            if "x de R$" in price_text:
                parts = price_text.split("x de R$")
                if len(parts) > 1:
                    try:
                        parcelas = int(parts[0].strip())
                        valor_parcela = parts[1].strip()
                        valor_parcela_clean = valor_parcela.replace(".", "").replace(",", ".")
                        return float(valor_parcela_clean) * parcelas
                    except (ValueError, TypeError):
                        logger.debug(f"Falha ao extrair preço parcelado: {price_text}")

            # Remove o símbolo da moeda e espaços
            price_clean = price_text.replace("R$", "").strip()

            # Substitui pontos por nada (separador de milhar) e vírgula por ponto (separador decimal)
            price_clean = price_clean.replace(".", "").replace(",", ".")

            # Extrai apenas números e ponto decimal
            match = re.search(r'(\d+\.?\d*)', price_clean)
            if match:
                return float(match.group(1))

            logger.debug(f"Não foi possível extrair valor de '{price_text}'")
            return None

        except Exception as e:
            logger.error(f"Erro ao extrair valor numérico do preço '{price_text}': {str(e)}")
            return None

    def try_alternative_selectors(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Tenta extrair os dados usando conjuntos alternativos de seletores.

        Args:
            html_content: Conteúdo HTML da página.

        Returns:
            Lista de dicionários com os dados dos anúncios.

        Raises:
            PageStructureChangedError: Se todos os seletores falharem.
        """
        attempt = 0
        max_attempts = self.max_fallback_attempts

        while attempt < max_attempts:
            # Obtém o próximo conjunto de seletores alternativos
            fallback_selectors = self.get_fallback_selectors()
            if not fallback_selectors:
                break

            # Atualiza os seletores com o conjunto de fallback
            self.selectors = fallback_selectors

            try:
                # Tenta extrair com os novos seletores
                soup = BeautifulSoup(html_content, 'html.parser')
                listing_elements = soup.select(self.selectors['listings'])

                if listing_elements:
                    logger.info(f"Usando seletores alternativos (tentativa {attempt+1})")
                    return self._extract_data_from_elements(listing_elements)
            except Exception as e:
                logger.warning(f"Fallback {attempt+1} falhou: {str(e)}")

            attempt += 1

        # Se chegou aqui, todos os seletores falharam
        raise PageStructureChangedError("Todos os seletores falharam. A estrutura da página mudou significativamente.")

    def get_fallback_selectors(self) -> Dict[str, str]:
        """
        Retorna o próximo conjunto de seletores alternativos.

        Returns:
            Dicionário com os seletores alternativos ou None se não houver mais.
        """
        if not hasattr(self, '_current_fallback_index'):
            self._current_fallback_index = 0

        # Verifica se ainda há conjuntos de fallback disponíveis
        if self._current_fallback_index < len(self.fallback_selectors):
            fallback = self.fallback_selectors[self._current_fallback_index]
            self._current_fallback_index += 1
            return fallback

        return None

"""
Serviço de banco de dados para o OLX Research Scraper.
Implementa o padrão Repository para acesso a dados.
"""

import sqlite3
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager

# Importando configurações
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Importar configurações usando caminho correto
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
sys.path.append(CONFIG_PATH)
from settings import DATABASE_NAME

class DatabaseError(Exception):
    """Exceção específica para erros de banco de dados."""
    pass

class ProductRepository:
    """
    Implementação do padrão Repository para produtos.
    Gerencia a persistência e recuperação de dados de produtos.
    """

    def __init__(self, db_name: Optional[str] = None):
        """
        Inicializa o repositório com o nome do banco de dados.

        Args:
            db_name: Nome do arquivo do banco de dados. Se não for fornecido,
                    usa o valor padrão das configurações.
        """
        self.db_name = db_name or DATABASE_NAME
        self.logger = logging.getLogger(__name__)

        # Garantir que o diretório de dados exista
        os.makedirs(os.path.dirname(self.db_name), exist_ok=True)

    @contextmanager
    def _get_connection(self):
        """
        Gerenciador de contexto para obter conexão com o banco de dados.
        Garante que a conexão seja fechada após o uso.

        Yields:
            Conexão com o banco de dados.

        Raises:
            DatabaseError: Se ocorrer um erro ao conectar ou operar o banco de dados.
        """
        connection = None
        try:
            connection = sqlite3.connect(self.db_name)
            yield connection
        except sqlite3.Error as e:
            self.logger.error(f"Erro de banco de dados: {e}")
            raise DatabaseError(f"Erro ao conectar ao banco de dados: {e}")
        finally:
            if connection:
                connection.close()

    def initialize_database(self) -> None:
        """
        Inicializa o banco de dados criando as tabelas necessárias se não existirem.

        Raises:
            DatabaseError: Se ocorrer um erro ao criar tabelas.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS produtos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produto TEXT NOT NULL,
                    preco REAL NOT NULL,
                    url TEXT,
                    titulo TEXT,
                    data_extracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Índices para melhorar a performance de consultas comuns
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_produto ON produtos(produto)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_extracao ON produtos(data_extracao)")

                conn.commit()
                self.logger.info("Banco de dados inicializado com sucesso.")
        except Exception as e:
            self.logger.error(f"Erro ao inicializar banco de dados: {e}")
            raise DatabaseError(f"Falha ao inicializar banco de dados: {e}")

    def insert_product(self, produto: str, preco: float, url: str, titulo: str) -> int:
        """
        Insere um novo registro de produto no banco de dados.

        Args:
            produto: Nome do produto pesquisado.
            preco: Preço do produto.
            url: URL do anúncio.
            titulo: Título do anúncio.

        Returns:
            ID do produto inserido.

        Raises:
            DatabaseError: Se ocorrer um erro ao inserir dados.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO produtos (produto, preco, url, titulo)
                VALUES (?, ?, ?, ?)
                """, (produto, preco, url, titulo))
                conn.commit()
                self.logger.debug(f"Produto inserido com ID {cursor.lastrowid}")
                return cursor.lastrowid
        except Exception as e:
            self.logger.error(f"Erro ao inserir produto: {e}")
            raise DatabaseError(f"Falha ao inserir produto no banco de dados: {e}")

    def get_products_by_name(self, produto: str) -> List[Dict[str, Any]]:
        """
        Recupera produtos pelo nome.

        Args:
            produto: Nome do produto para filtrar.

        Returns:
            Lista de produtos encontrados.

        Raises:
            DatabaseError: Se ocorrer um erro ao consultar o banco de dados.
        """
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                SELECT id, produto, preco, url, titulo, data_extracao
                FROM produtos
                WHERE produto = ?
                ORDER BY data_extracao DESC
                """, (produto,))

                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Erro ao recuperar produtos: {e}")
            raise DatabaseError(f"Falha ao consultar produtos no banco de dados: {e}")

    def get_product_price_history(self, produto: str) -> List[Tuple[str, float]]:
        """
        Obtém o histórico de preços de um produto.

        Args:
            produto: Nome do produto para consultar.

        Returns:
            Lista de tuplas (data, preço) ordenadas por data.

        Raises:
            DatabaseError: Se ocorrer um erro ao consultar o banco de dados.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT data_extracao, preco
                FROM produtos
                WHERE produto = ?
                ORDER BY data_extracao
                """, (produto,))

                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Erro ao recuperar histórico de preços: {e}")
            raise DatabaseError(f"Falha ao consultar histórico de preços: {e}")

    def clear_old_data(self, dias: int = 30) -> int:
        """
        Remove dados antigos do banco de dados.

        Args:
            dias: Número de dias para manter os dados.

        Returns:
            Número de registros removidos.

        Raises:
            DatabaseError: Se ocorrer um erro ao excluir dados.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                DELETE FROM produtos
                WHERE data_extracao < datetime('now', '-' || ? || ' days')
                """, (dias,))

                conn.commit()
                rows_deleted = cursor.rowcount
                self.logger.info(f"Removidos {rows_deleted} registros antigos.")
                return rows_deleted
        except Exception as e:
            self.logger.error(f"Erro ao limpar dados antigos: {e}")
            raise DatabaseError(f"Falha ao remover dados antigos: {e}")

# 🔍 OLX Research Scraper

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Este repositório contém um projeto de pesquisa para extração e análise de preços de produtos anunciados na [OLX Brasil](https://www.olx.com.br/). O objetivo é coletar dados de forma automatizada para fins de estudo e pesquisa, permitindo análises estatísticas e visualizações de tendências de mercado.

**⚠️ Disclaimer:** Este projeto foi desenvolvido para fins de pesquisa e estudo. Os autores não se responsabilizam por qualquer uso que viole os termos de serviço da OLX ou a legislação aplicável. O uso desta ferramenta é de total responsabilidade do usuário.

## 🚀 Funcionalidades

*   Extração de preços, títulos e URLs de anúncios da OLX para o estado de Goiás.
*   Pesquisa por múltiplos produtos simultaneamente.
*   Configuração do número de páginas a serem raspadas.
*   Armazenamento dos dados coletados em um banco de dados SQLite.
*   Análise estatística básica dos preços (média, mediana, mínimo, máximo, desvio padrão).
*   Geração de histogramas para visualização da distribuição de preços.
*   Utilização de `multiprocessing` para agilizar a coleta de dados.
*   Implementação de `User-Agent` aleatório e *delays* para reduzir a chance de bloqueios.

## 🛠️ Instalação

1.  **Clone o repositório:**

    ```bash
    git clone [https://github.com/tavaresgmg/OLX-Research-Scraper.git](https://github.com/tavaresgmg/OLX-Research-Scraper.git)
    cd OLX-Research-Scraper
    ```

2.  **Crie e ative um ambiente virtual (recomendado):**

    ```bash
    python3 -m venv olx-env
    source olx-env/bin/activate  # Linux/macOS
    ```
    No Windows, use `olx-env\Scripts\activate`.

3.  **Instale as dependências:**

    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Uso

```bash
python src/main.py "produto1, produto2, ..." -p <número de páginas>
Exemplo:

Bash
python src/main.py "iphone 13, galaxy s22" -p 5
Este comando pesquisa por "iphone 13" e "galaxy s22" nas 5 primeiras páginas de resultados da OLX para o estado de Goiás, extrai os dados, realiza análises estatísticas e gera os histogramas correspondentes.

## 🤝 Contribuições

Contribuições são bem-vindas! Sinta-se à vontade para melhorar este projeto. Para contribuir:

Faça um fork do repositório.
Crie uma branch para sua feature (git checkout -b feature/sua-feature).
Faça commit das suas alterações (git commit -am 'Adiciona nova feature').
Faça push para a branch (git push origin feature/sua-feature).
Abra um Pull Request.
Sugestões de Contribuições:

Refinar os seletores CSS para maior robustez.
Implementar estratégias avançadas para evitar bloqueios (e.g., proxies rotativos).
Adicionar novas funcionalidades de análise de dados.
Desenvolver uma interface gráfica.
Melhorar a documentação.

## 📄 Licença

Este projeto está licenciado sob a GNU General Public License v3.0 (GPLv3). Veja o arquivo LICENSE para mais detalhes.

## 🎯 Considerações Éticas e Legais

Este é um projeto de pesquisa e deve ser usado para fins educacionais e de análise de dados.
Respeite os termos de serviço da OLX ao usar este scraper.
Evite sobrecarregar os servidores da OLX com requisições excessivas.
Os autores deste projeto não se responsabilizam por qualquer uso inadequado desta ferramenta.

## 📞 Contato

Para dúvidas, sugestões ou relatar problemas, por favor, abra uma Issue neste repositório.

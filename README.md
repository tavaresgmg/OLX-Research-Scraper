# 🔍 OLX Research Scraper

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Este repositório contém um projeto de pesquisa para extração e análise de preços de produtos anunciados na OLX Brasil. O objetivo é coletar dados de forma automatizada para fins de estudo e pesquisa, permitindo análises estatísticas e visualizações de tendências de mercado.

**⚠️ Disclaimer:** Este projeto é puramente para fins de pesquisa e estudo. O uso indevido desta ferramenta para atividades que violem os termos de serviço da OLX é de total responsabilidade do usuário. Os autores deste projeto não se responsabilizam por qualquer uso inapropriado ou ilegal.

## 🚀 Funcionalidades

- Extração de preços, títulos e URLs de anúncios da OLX.
- Pesquisa por múltiplos produtos simultaneamente.
- Configuração do número de páginas a serem raspadas.
- Armazenamento dos dados coletados em um banco de dados SQLite.
- Análise estatística básica dos preços (média, mediana, mínimo, máximo, desvio padrão).
- Geração de histograma para visualização da distribuição de preços.
- Utilização de multiprocessing para agilizar a coleta.
- Implementação de User-Agent aleatório e delays para evitar bloqueios.

## 🛠️ Instalação

1.  **Clone o repositório:**

    ```bash
    git clone <URL do seu repositório>
    cd <nome do repositório>
    ```

2.  **Crie um ambiente virtual (recomendado):**

    ```bash
    python3 -m venv olx-env
    ```

3.  **Ative o ambiente virtual:**

    - **Linux/macOS:**

      ```bash
      source olx-env/bin/activate
      ```

    - **Windows:**

      ```bash
      olx-env\Scripts\activate
      ```

4.  **Instale as dependências:**

    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Uso

```bash
python olx.py "produto1, produto2, produto3" -p <número de páginas>
Exemplo:

Bash
python olx.py "iphone 13, galaxy s22" -p 5
Este comando irá pesquisar por "iphone 13" e "galaxy s22" em 5 páginas da OLX no estado de Goiás, extrair os dados, realizar análises estatísticas e gerar histogramas.

🤝 Contribuições
Contribuições são bem-vindas! Se você deseja melhorar este projeto, siga os passos abaixo:

Faça um fork do repositório.
Crie uma branch para sua feature (git checkout -b feature/sua-feature).
Faça commit das suas alterações (git commit -am 'Adiciona nova feature').
Faça push para a branch (git push origin feature/sua-feature).
Abra um Pull Request.
Áreas para contribuir:

Melhorar a robustez dos seletores CSS.
Implementar estratégias avançadas para evitar bloqueios.
Adicionar novas funcionalidades de análise de dados.
Criar uma interface gráfica amigável.
Melhorar a documentação.
📄 Licença
Este projeto está licenciado sob a Licença MIT. Veja o arquivo LICENSE para mais detalhes.

🎯 Considerações Éticas e Legais
Web scraping deve ser feito de forma responsável e ética.
Respeite os termos de serviço da OLX.
Não sobrecarregue os servidores da OLX com requisições excessivas.
Utilize os dados coletados de forma responsável e para fins de pesquisa.
Este projeto é independente e não possui qualquer vínculo com a OLX.
📞 Contato
Para dúvidas, sugestões ou relatar problemas, por favor, abra uma Issue neste repositório.

Divirta-se e faça pesquisas incríveis! 😄
```

<div align="center">
  <img src="./assets/icon.png" alt="Bolão da Cabine do Glória Logo" width="120" height="120" />
  <h1>Bolão da Cabine do Glória</h1>
  <p><strong>Copa do Mundo 2026 • Bolão inteligente com simulador interativo interno, conferência e ranking automático</strong></p>

  <p>
    <a href="#-português">Português</a> •
    <a href="#-english">English</a> •
    <a href="#-tecnologias--technologies">Tecnologias</a> •
    <a href="#-como-executar--how-to-run">Como executar</a> •
    <a href="#-deploy">Deploy</a> •
    <a href="#-licença--license">Licença</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/version-2.0.0-blue.svg" alt="Version 2.0.0" />
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT" />
    <img src="https://img.shields.io/badge/Streamlit-FF4B4B.svg?style=flat-square&logo=streamlit&logoColor=white" alt="Streamlit" />
    <img src="https://img.shields.io/badge/Python-3.11-3776AB.svg?style=flat-square&logo=python&logoColor=white" alt="Python 3.11" />
    <img src="https://img.shields.io/badge/Supabase-ready-3ECF8E.svg?style=flat-square&logo=supabase&logoColor=white" alt="Supabase Ready" />
  </p>
</div>

---

# 🇧🇷 Português

## 📋 Visão geral

O **Bolão da Cabine do Glória** é uma aplicação web feita para criar, simular e acompanhar palpites da **Copa do Mundo 2026** com uma experiência simples, visual e 100% nativa.

A ideia central é eliminar o trabalho manual com planilhas, JSONs e dependências de simuladores externos (como o do ge.globo) ou OCR de imagens. Todo o fluxo de preenchimento acontece diretamente dentro do sistema. O participante informa seu nome, simula os placares da fase de grupos, o sistema calcula a classificação e os melhores terceiros automaticamente, monta o chaveamento do mata-mata, e permite que o participante escolha os vencedores das rodadas eliminatórias até o campeão.

> Um bolão feito para ser fácil para quem participa e poderoso para quem administra.

---

## 🧭 Fluxo do participante

```text
1. Identifique-se com seu nome
       ↓
2. Simule a Fase de Grupos (preencha os placares)
       ↓
3. Confira os Classificados (1º, 2º e ranking dos melhores 3ºs)
       ↓
4. Escolha o Mata-mata (selecione os vencedores de cada chave)
       ↓
5. Revise e envie seu palpite
```

---

## ✨ Funcionalidades

### 🌐 Área pública

- **Início (Home):** apresentação clara do novo fluxo interativo, com botões para iniciar o palpite ou visualizar o ranking.
- **Fazer palpite:** fluxo integrado de simulação por etapas (Fase de grupos, Classificados, Mata-mata e Envio).
- **Ranking:** pódio interativo dos primeiros colocados, tabela de classificação geral de todos os participantes e detalhes de acertos.

### 🔐 Área administrativa

- **Dashboard:** estatísticas do bolão, carregamento de dados demo e limpeza de estado.
- **Participantes:** visualização detalhada, edição manual e exclusão de palpites.
- **Resultados oficiais:** simulação ou cadastro de resultados oficiais para sincronizar com os palpites dos usuários.
- **Ranking administrativo:** controle total das pontuações e logs de auditoria.
- **Exportações:** backup em CSV/JSON, formatação pronta de mensagens de ranking para Discord e exportação de pódio em HTML.
- **Configurações:** controle dos pesos da pontuação, regras de pontuação V2 e status público da aplicação.

---

## 🧮 Pontuação (Modo V2)

O sistema utiliza preferencialmente o **Modo V2** de pontuação:
- **Fase de grupos:** a pontuação considera os placares exatos dos jogos (peso configurável).
- **Mata-mata:** a pontuação considera os classificados corretos escolhidos pelo usuário em cada uma das fases (Dezesseis-avos, Oitavas, Quartas, Semifinais, Terceiro Lugar e Final), além do acerto do Campeão.

### Critérios de desempate
1. Maior pontuação no mata-mata.
2. Acerto do campeão.
3. Maior pontuação na fase de grupos.
4. Ordem alfabética.

---

# 🇺🇸 English

## 📋 Overview

**Bolão da Cabine do Glória** is a web application designed to create, simulate, and track predictions for the **2026 FIFA World Cup** with a clean, responsive, and 100% native user experience.

The core goal is to eliminate manual spreadsheets, JSON imports, external simulators, and image OCR. The entire flow happens within the system. The participant enters their name, enters scorelines for the group stage, views live standings and automatically computed best third-place qualifiers, fills out the knockout bracket, and confirms their prediction before submitting.

> A prediction pool built to be easy for participants and powerful for administrators.

---

## 🧭 Participant flow

```text
1. Identify yourself with your name
       ↓
2. Simulate the Group Stage (fill in the match scores)
       ↓
3. View Standings (1st, 2nd, and best 3rd-place teams)
       ↓
4. Pick the Knockout Bracket (select winners for each match)
       ↓
5. Review and submit your prediction
```

---

## ✨ Features

### 🌐 Public area

- **Home:** clear presentation of the simulation workflow and quick links to start or view the ranking.
- **Make prediction:** integrated step-by-step simulation (Group stage, Standings, Knockouts, and Submission).
- **Ranking:** interactive podium, general leaderboard, and score breakdowns.

### 🔐 Admin area

- **Dashboard:** pool KPIs, demo data loader, and state resets.
- **Participants:** view, edit, or delete submitted predictions.
- **Official results:** input official tournament results to update participant scores.
- **Admin ranking:** detailed score audit logs.
- **Exports:** CSV/JSON backups, Discord-ready leaderboard messages, and HTML podium code.
- **Settings:** score weight configurations, V2 scoring rules, and public status toggle.

---

## 🧮 Scoring (Mode V2)

The system defaults to the **V2 Scoring Mode**:
- **Group stage:** points awarded based on exact match scores (configurable weight).
- **Knockout stage:** points awarded based on correctly predicting the qualified teams in each round (Round of 32, Round of 16, Quarterfinals, Semifinals, Third place, and Finals), plus the Champion.

### Tie-breakers
1. Higher knockout-stage score.
2. Correct champion prediction.
3. Higher group-stage score.
4. Alphabetical order.

---

# 🧰 Tecnologias / Technologies

- [Streamlit](https://streamlit.io/) — interface web rápida e interativa.
- [Python 3.11+](https://python.org/) — linguagem principal da aplicação.
- [Supabase](https://supabase.com/) — persistência em produção.
- CSV / JSON — exportação, backup e interoperabilidade.
- *Nota: O processamento de imagens (OCR) via Tesseract e o parser de textos legados foram mantidos internamente apenas para fins de compatibilidade técnica e administrativa.*

---

# ⚙️ Como executar / How to run

## Pré-requisitos / Requirements

- Python 3.11+
- Windows PowerShell, Terminal, Bash ou shell compatível.

## Instalação local / Local setup

```bash
# Clone o repositório / Clone the repository
git clone https://github.com/BarujaFe1/Bol-o-CabineDoGl-ria.git
cd Bol-o-CabineDoGl-ria

# Crie um ambiente virtual / Create virtual env
python -m venv .venv

# Ative o ambiente virtual / Activate virtual env
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Instale as dependências / Install dependencies
pip install -r requirements.txt

# Execute o app / Run the app
streamlit run app.py
```

Acesse em seu navegador / Open in your browser:
`http://localhost:8501`

---

# ☁️ Deploy & Configuração de Banco de Dados

Esta instância do bolão é independente da versão de Vargem Grande. Para que funcione corretamente, é necessário configurar um banco de dados **Supabase** exclusivo para o grupo de São Carlos (Sanca).

## Pré-requisito: Configuração do Supabase (São Carlos)

1. Crie uma conta ou projeto no [Supabase](https://supabase.com/).
2. Obtenha a URL do projeto (`SUPABASE_URL`) e a chave do Service Role (`SUPABASE_SERVICE_ROLE_KEY`) nas configurações de API do Supabase.
3. Ao rodar localmente ou no Streamlit Cloud, essas variáveis serão usadas para criar automaticamente as tabelas necessárias (`bolao_config`, `bolao_submissions` e `bolao_official`).

## Configuração Local (.env ou secrets.toml)

Para rodar localmente, copie o arquivo `.env.example` para `.env` (ou `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml`) e preencha as variáveis de ambiente locais com placeholders ou dados do seu banco de desenvolvimento. **Nunca commite chaves reais no repositório.**

## Streamlit Community Cloud

1. Acesse [Streamlit Community Cloud](https://share.streamlit.io).
2. Conecte sua conta do GitHub.
3. Selecione o repositório do projeto: `https://github.com/BarujaFe1/Bol-o-CabineDoGl-ria`.
4. Configure o arquivo principal como `app.py` e clique em **Deploy**.

## Streamlit secrets

Nas configurações da aplicação no painel da Streamlit Cloud (App > Settings > Secrets), adicione as variáveis em **Secrets**:

```toml
# Obrigatório para produção (Banco Supabase de São Carlos)
SUPABASE_URL = "https://seu-projeto-sanca.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "sua-chave-service-role-sanca"

# Senha da Área Administrativa para o grupo de Sanca
ADMIN_PASSWORD = "sua-senha-admin-segura"
```
```

---

# 📄 Licença / License

Distribuído sob a licença MIT. Veja `LICENSE` para mais informações.

---

# 👨‍💻 Autor / Author

Desenvolvido por **BarujaFe**.

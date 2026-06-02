<div align="center">
  <img src="./assets/icon.png" alt="Bolão da Cabine do Glória Logo" width="120" height="120" />
  <h1>Bolão da Cabine do Glória</h1>
  <p><strong>Copa do Mundo 2026 • Bolão inteligente com OCR, conferência e ranking automático</strong></p>

  <p>
    <a href="#-português">Português</a> •
    <a href="#-english">English</a> •
    <a href="#-tecnologias--technologies">Tecnologias</a> •
    <a href="#-como-executar--how-to-run">Como executar</a> •
    <a href="#-deploy">Deploy</a> •
    <a href="#-licença--license">Licença</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/version-1.0.0-blue.svg" alt="Version 1.0.0" />
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT" />
    <img src="https://img.shields.io/badge/Streamlit-FF4B4B.svg?style=flat-square&logo=streamlit&logoColor=white" alt="Streamlit" />
    <img src="https://img.shields.io/badge/Python-3.11-3776AB.svg?style=flat-square&logo=python&logoColor=white" alt="Python 3.11" />
    <img src="https://img.shields.io/badge/Supabase-ready-3ECF8E.svg?style=flat-square&logo=supabase&logoColor=white" alt="Supabase Ready" />
    <img src="https://img.shields.io/badge/OCR-Tesseract-5A5A5A.svg?style=flat-square" alt="OCR Tesseract" />
  </p>
</div>

---

# 🇧🇷 Português

## 📋 Visão geral

**Bolão da Cabine do Glória** é uma aplicação web feita para organizar bolões da **Copa do Mundo 2026** com uma experiência simples, visual e automatizada.

A ideia central é eliminar o trabalho manual com planilhas, JSONs e conferência complicada. O participante preenche o simulador do ge.globo, envia dois prints dos grupos, cola o texto do mata-mata e revisa tudo em uma tela de conferência antes de confirmar o palpite.

O sistema processa os dados automaticamente, interpreta os grupos por OCR visual, lê o mata-mata, salva o palpite e calcula o ranking com critérios configuráveis.

> Um bolão feito para ser fácil para quem participa e poderoso para quem administra.

---

## 🧭 Fluxo do participante

```text
1. Acesse o simulador do ge.globo
      ↓
2. Preencha grupos e mata-mata
      ↓
3. Tire 2 prints dos grupos: A–F e G–L
      ↓
4. Copie o texto do mata-mata
      ↓
5. Envie tudo no site
      ↓
6. Revise a conferência obrigatória
      ↓
7. Confirme o palpite
```

---

## ✨ Funcionalidades

### 🌐 Área pública

- **Home:** instruções claras, passo a passo e link direto para o simulador.
- **Enviar palpite:** upload de 2 imagens dos grupos + texto do mata-mata.
- **Conferência obrigatória:** o participante revisa o que foi detectado antes de confirmar.
- **Ranking:** pódio visual, tabela geral e detalhamento por participante.

### 🔐 Área administrativa

- **Dashboard:** KPIs, carregamento de dados demo e limpeza de estado.
- **Participantes:** visualizar, editar e excluir palpites.
- **Resultados oficiais:** colar texto, sincronizar API-Football, revisar e aprovar.
- **Ranking administrativo:** pódio, tabela completa e detalhes de pontuação.
- **Exportações:** CSV, JSON, backup completo, texto para Discord e HTML do pódio.
- **Configurações:** modo de pontuação, pesos, bônus e status público.
- **Ajuda:** fluxo resumido para operação do sistema.

### 🧠 Sistema inteligente

- **OCR visual por cor:** detecta 1º, 2º, 3º e 4º lugares com base nas cores das linhas do print do ge.globo.
- **Parser do mata-mata:** interpreta fases eliminatórias com suporte a variações de acentuação e formato.
- **Pontuação configurável:** modo ponderado ou uniforme, com critérios de desempate.
- **Persistência dual:** JSON local para desenvolvimento ou Supabase para produção.
- **Revisão manual controlada:** resultados oficiais e dados importados passam por conferência antes da aprovação.

---

## 🧮 Pontuação

### Modo ponderado

| Item | Pontos |
|---|---:|
| 1º lugar no grupo | 5 |
| 2º lugar no grupo | 3 |
| 3º lugar classificado | 2 |
| Melhor terceiro | 2 |
| Cada acerto no mata-mata | 5 |
| Campeã | configurável |

### Modo uniforme

Cada decisão correta vale uma pontuação única configurável, com possibilidade de bônus para a campeã.

### Critérios de desempate

1. Maior pontuação no mata-mata.
2. Acerto da campeã.
3. Maior pontuação em grupos.
4. Ordem alfabética.

---

## 🛡️ Segurança e boas práticas

- Nunca commite secrets, senhas ou chaves de API.
- Use `.env.example` como referência e configure variáveis reais no ambiente de produção.
- Proteja a área administrativa com `ADMIN_PASSWORD`.
- Em produção, prefira Supabase em vez de persistência local.
- Revise resultados oficiais antes de aprovar pontuação pública.

---

## 🔍 Limitações conhecidas

1. **OCR visual:** calibrado para prints do simulador do ge.globo. Prints cortados, borrados ou com zoom irregular podem exigir correção manual.
2. **Terceiros classificados:** quando não aparecem explicitamente, o sistema infere a partir da fase de 32.
3. **API-Football:** a resposta da API pode exigir revisão manual antes da aprovação.
4. **Persistência local:** ideal para desenvolvimento; em produção, use Supabase.

---

## 🚧 Roadmap

- [ ] Login por Discord via OAuth.
- [ ] Múltiplos bolões por servidor.
- [ ] Cards compartilháveis do pódio em PNG.
- [ ] Integração automática com fonte oficial de resultados.
- [ ] Dashboard avançado de estatísticas.
- [ ] Histórico de edições e auditoria administrativa.
- [ ] Página pública com status do bolão e próximos jogos.

---

# 🇺🇸 English

## 📋 Overview

**Bolão da Cabine do Glória** is a web application designed to manage a **2026 FIFA World Cup prediction pool** with a simple, visual and automated experience.

The core goal is to remove the manual work of spreadsheets, JSON files and complicated validation. Participants fill out the ge.globo simulator, upload two screenshots of the group stage, paste the knockout-stage text and review everything on a required confirmation screen before submitting.

The system automatically processes the data, reads group standings through visual OCR, parses the knockout bracket, stores the prediction and calculates the ranking with configurable scoring rules.

> A prediction pool built to be easy for participants and powerful for administrators.

---

## 🧭 Participant flow

```text
1. Open the ge.globo simulator
      ↓
2. Fill in the groups and knockout stage
      ↓
3. Take 2 screenshots of the groups: A–F and G–L
      ↓
4. Copy the knockout-stage text
      ↓
5. Submit everything on the website
      ↓
6. Review the required confirmation screen
      ↓
7. Confirm the prediction
```

---

## ✨ Features

### 🌐 Public area

- **Home:** clear instructions, step-by-step guide and direct simulator link.
- **Submit prediction:** upload 2 group-stage images + knockout-stage text.
- **Required confirmation:** participants review detected data before confirming.
- **Ranking:** visual podium, general table and participant-level details.

### 🔐 Admin area

- **Dashboard:** KPIs, demo data loader and state cleanup.
- **Participants:** view, edit and delete predictions.
- **Official results:** paste text, sync API-Football, review and approve.
- **Admin ranking:** podium, complete table and full score breakdown.
- **Exports:** CSV, JSON, full backup, Discord-ready text and podium HTML.
- **Settings:** scoring mode, weights, bonuses and public status.
- **Help:** compact operational guide.

### 🧠 Intelligent system

- **Color-based visual OCR:** detects 1st, 2nd, 3rd and 4th places based on row colors from ge.globo screenshots.
- **Knockout parser:** robustly interprets elimination rounds with support for accent and formatting variations.
- **Configurable scoring:** weighted or uniform scoring, with automatic tie-breakers.
- **Dual persistence:** local JSON for development or Supabase for production.
- **Controlled manual review:** official results and imported data can be reviewed before approval.

---

## 🧮 Scoring

### Weighted mode

| Item | Points |
|---|---:|
| 1st place in group | 5 |
| 2nd place in group | 3 |
| Qualified 3rd place | 2 |
| Best third-place team | 2 |
| Each knockout-stage hit | 5 |
| Champion | configurable |

### Uniform mode

Each correct decision receives a configurable fixed score, with optional champion bonus.

### Tie-breakers

1. Higher knockout-stage score.
2. Correct champion.
3. Higher group-stage score.
4. Alphabetical order.

---

## 🛡️ Security and best practices

- Never commit secrets, passwords or API keys.
- Use `.env.example` as a reference and configure real variables in production.
- Protect the admin area with `ADMIN_PASSWORD`.
- In production, prefer Supabase instead of local persistence.
- Review official results before approving public scoring.

---

## 🔍 Known limitations

1. **Visual OCR:** calibrated for ge.globo simulator screenshots. Cropped, blurry or irregularly zoomed screenshots may require manual correction.
2. **Qualified third-place teams:** when not explicitly shown, the system infers them from the round of 32.
3. **API-Football:** API responses may require manual review before approval.
4. **Local persistence:** suitable for development; use Supabase in production.

---

## 🚧 Roadmap

- [ ] Discord OAuth login.
- [ ] Multiple pools per server.
- [ ] Shareable podium cards as PNG.
- [ ] Automatic integration with an official results source.
- [ ] Advanced statistics dashboard.
- [ ] Edit history and admin audit trail.
- [ ] Public pool status page with upcoming matches.

---

# 🧰 Tecnologias / Technologies

- [Streamlit](https://streamlit.io/) — interface web rápida e interativa.
- [Python 3.11+](https://python.org/) — linguagem principal da aplicação.
- [Supabase](https://supabase.com/) — persistência em produção.
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — leitura visual dos grupos.
- [API-Football](https://www.api-football.com/) — sincronização opcional de resultados.
- CSV / JSON — exportação, backup e interoperabilidade.

---

# 📁 Estrutura do projeto / Project structure

```text
bolao_cabine_gloria_public_ocr/
├── app.py                       # Aplicação principal / Main application
├── requirements.txt             # Dependências Python / Python dependencies
├── packages.txt                 # Pacotes de sistema, como Tesseract / System packages
├── runtime.txt                  # Versão do Python / Python version
├── .streamlit/
│   └── config.toml              # Configuração do Streamlit / Streamlit config
├── .env.example                 # Exemplo de variáveis / Environment example
├── .gitignore                   # Arquivos ignorados pelo Git / Ignored files
├── src/bolao/
│   ├── api_service.py           # Integração API-Football / API-Football integration
│   ├── constants.py             # Constantes e configurações / Constants and settings
│   ├── exporters.py             # Exportações / Exports
│   ├── models.py                # Modelos de dados / Data models
│   ├── ocr_groups.py            # Leitura visual dos grupos / Visual group OCR
│   ├── parser_ge.py             # Parser do texto do ge / ge.globo text parser
│   ├── scoring.py               # Sistema de pontuação / Scoring system
│   ├── storage.py               # Persistência local + Supabase / Storage layer
│   ├── ui_components.py         # Componentes de UI / UI components
│   ├── utils.py                 # Utilitários / Utilities
│   └── validation.py            # Validação de palpites / Prediction validation
├── data/
│   ├── examples/                # Exemplos / Examples
│   ├── demo_state/              # Dados demo / Demo state
│   └── state/                   # Dados locais não versionados / Local runtime data
└── tests/
    └── test_parser_scoring.py   # Testes / Tests
```

---

# ⚙️ Como executar / How to run

## Pré-requisitos / Requirements

- Python 3.11+
- Windows PowerShell, Terminal, Bash or compatible shell
- Tesseract OCR installed locally when using OCR features

## Instalação local / Local setup

```bash
# Clone the repository
git clone https://github.com/SEU_USUARIO/bolao-cabine-gloria.git

# Enter the project folder
cd bolao-cabine-gloria

# Create a virtual environment
python -m venv .venv

# Activate the environment on Windows
.venv\Scripts\activate

# Or activate it on Linux/macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run Streamlit
streamlit run app.py
```

Acesse / Open:

```text
http://localhost:8501
```

---

# ☁️ Deploy

## Streamlit Community Cloud

1. Acesse [Streamlit Community Cloud](https://share.streamlit.io).
2. Conecte sua conta GitHub.
3. Selecione o repositório do projeto.
4. Configure o arquivo principal como `app.py`.
5. Clique em **Deploy**.

## Streamlit secrets

No painel do Streamlit Cloud, acesse **App Settings > Secrets** e adicione:

```toml
# Required for production
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"

# Required to protect admin area
ADMIN_PASSWORD = "your-secure-password"

# Optional
APIFOOTBALL_KEY = "your-api-key"
```

---

# 🔧 Supabase setup

## Criar projeto / Create project

1. Acesse [supabase.com](https://supabase.com).
2. Crie um novo projeto.
3. Vá em **Settings > API**.
4. Copie a **Project URL** e a **service_role key**.
5. Configure os valores nos secrets do Streamlit.

## Tabelas / Tables

O app pode criar as tabelas automaticamente na primeira execução. Para criar manualmente, use:

```sql
CREATE TABLE IF NOT EXISTS bolao_config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bolao_submissions (
    id TEXT PRIMARY KEY,
    participant TEXT NOT NULL,
    groups JSONB NOT NULL,
    best_thirds JSONB,
    knockout JSONB,
    champion TEXT,
    submission_id TEXT NOT NULL,
    submitted_at TEXT,
    status TEXT DEFAULT 'confirmado',
    meta JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bolao_official (
    id TEXT PRIMARY KEY DEFAULT 'official',
    participant TEXT NOT NULL,
    groups JSONB NOT NULL,
    best_thirds JSONB,
    knockout JSONB,
    champion TEXT,
    submission_id TEXT,
    submitted_at TEXT,
    status TEXT DEFAULT 'aprovado',
    meta JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

# 📦 Demonstração / Demo data

Na área administrativa, use **Carregar dados de demonstração** para visualizar o sistema completo com:

- Participantes simulados.
- Ranking geral.
- Pódio.
- Resultado oficial de exemplo.
- Pontuação calculada.

In the admin area, use **Load demo data** to preview the full system with simulated participants, ranking, podium, example official result and calculated scores.

---

# 🤝 Contribuição / Contributing

Contribuições são bem-vindas.

Contributions are welcome.

```bash
# Create a feature branch
git checkout -b feature/minha-feature

# Commit your changes
git commit -m "feat: adiciona nova funcionalidade"

# Push to GitHub
git push origin feature/minha-feature
```

Depois, abra um Pull Request descrevendo claramente a melhoria proposta.

Then open a Pull Request clearly describing the proposed improvement.

---

# 📄 Licença / License

Distribuído sob a licença MIT. Veja `LICENSE` para mais informações.

Distributed under the MIT License. See `LICENSE` for more information.

---

# 👨‍💻 Autor / Author

Desenvolvido por **BarujaFe**.

Developed by **BarujaFe**.

[![GitHub](https://img.shields.io/badge/-GitHub-181717?style=flat-square&logo=github)](https://github.com/BarujaFe1)

---

<p align="center">
  <strong>Feito com ❤️ para a Copa do Mundo 2026.</strong><br/>
  <strong>Made with ❤️ for the 2026 FIFA World Cup.</strong>
</p>

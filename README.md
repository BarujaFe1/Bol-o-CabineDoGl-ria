# 🏆 Bolão da Cabine do Glória

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellowgreen?style=for-the-badge)](LICENSE)

**Copa do Mundo 2026** — Um bolão completo e fácil de usar, sem necessidade de lidar com JSON ou planilhas.

---

## 📋 Visão Geral

O **Bolão da Cabine do Glória** é uma aplicação web para organizar bolões da Copa do Mundo 2026. O diferencial é a **experiência simples para o participante**: ele só precisa enviar dois prints dos grupos e colar o texto do mata-mata exportado pelo simulador do ge.globo.

O sistema faz o resto: detecta os grupos automaticamente via OCR visual, interpreta o mata-mata, mostra uma tela de conferência obrigatória e salva o palpite.

### Fluxo do Participante

```
1. Acesse o simulador do ge
      ↓
2. Preencha os grupos e mata-mata
      ↓
3. Tire 2 prints (A-F e G-L)
      ↓
4. Copie o texto do mata-mata
      ↓
5. Envie no site
      ↓
6. Revise e confirme ✓
```

---

## ✨ Funcionalidades

### Área Pública
- **Home** — Instruções claras com passo a passo e link direto para o simulador do ge
- **Enviar Palpite** — Upload de 2 imagens + texto do mata-mata + conferência obrigatória
- **Ranking** — Pódio visual, tabela geral e detalhamento por participante

### Área Administrativa (protegida por senha)
- **Dashboard** — KPI, carregar dados demo, limpar estado
- **Participantes** — Ver, editar e excluir palpites
- **Resultados Oficiais** — Colar texto, sincronizar API-Football, revisar e aprovar
- **Ranking** — Ver pódio, tabela e detalhamento completo
- **Exportações** — CSV, JSON, backup completo, texto para Discord, HTML do pódio
- **Configurações** — Modo de pontuação, pesos, status público
- **Ajuda** — Fluxo resumido

### Sistema Inteligente
- **OCR visual por cor** — Detecta 1º, 2º, 3º e 4º lugares pela cor das linhas no print do ge
- **Parser do mata-mata** — Interpretador robusto com suporte a variações de acentuação
- **Conferência obrigatória** — O participante revisa antes de confirmar
- **Pontuação configurável** — Modo ponderado ou uniforme, com desempate automático
- **Persistência dual** — Local JSON (dev) ou Supabase (produção)

---

## 🚀 Como Rodar Localmente

### Pré-requisitos
- Python 3.11+
- Windows PowerShell ou Terminal

### Passos

```powershell
# Clone ou extraia o projeto
cd bolao_cabine_gloria_public_ocr

# Crie o ambiente virtual
python -m venv .venv

# Ative o ambiente (Windows)
.venv\Scripts\activate

# Ou no Linux/Mac
source .venv/bin/activate

# Instale as dependências
pip install -r requirements.txt

# Execute o Streamlit
streamlit run app.py
```

Acesse: **http://localhost:8501**

### Dados de Demonstração

Na área Admin, clique em **Carregar dados de demonstração** para ver o sistema completo com ranking, pódio e exemplo de resultado oficial.

---

## ☁️ Como Publicar no Streamlit Cloud

### 1. Prepare o repositório GitHub

```bash
git init
git add .
git commit -m "feat: Bolão da Cabine do Glória - Copa 2026"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git
git push -u origin main
```

### 2. Configure o Deploy

1. Acesse [Streamlit Community Cloud](https://share.streamlit.io)
2. Conecte sua conta GitHub
3. Selecione o repositório
4. Selecione o arquivo principal: `app.py`
5. Clique em **Deploy**

### 3. Configure os Secrets

No Streamlit Cloud, vá em **App Settings > Secrets** e adicione:

```toml
# Obrigatório para produção
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Obrigatório para proteger admin
ADMIN_PASSWORD = "sua-senha-segura"

# Opcional
APIFOOTBALL_KEY = "sua-chave-api-aqui"
```

---

## 🔧 Configuração do Supabase

### Criar projeto Supabase

1. Acesse [supabase.com](https://supabase.com)
2. Crie um novo projeto
3. Vá em **Settings > API**
4. Copie a **Project URL** e **service_role key**

### Criar tabelas (automático)

O app cria as tabelas automaticamente na primeira execução. Para criar manualmente:

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

## 📊 Pontuação

### Modo Ponderado (padrão)

| Item | Pontos |
|------|--------|
| 1º lugar no grupo | 5 |
| 2º lugar no grupo | 3 |
| 3º lugar (classificado) | 2 |
| Melhor terceiro | 2 |
| Cada acerto no mata-mata | 5 |
| Campeã | configurável (padrão 0) |

### Modo Uniforme

Cada decisão correta vale 1 ponto (configurável), mais bônus da campeã.

### Critérios de Desempate

1. Maior pontuação no mata-mata
2. Acerto da campeã
3. Maior pontuação em grupos
4. Ordem alfabética

---

## 🛡️ Segurança

- **Nunca commite secrets** — Use `.gitignore` e `.env.example`
- **Admin protegido** — Senha configurável nos secrets
- **Dados dos participantes** — Armazenados com ID único, sem dados pessoais sensíveis

---

## 📁 Estrutura do Projeto

```
bolao_cabine_gloria_public_ocr/
├── app.py                      # Aplicação principal
├── requirements.txt            # Dependências Python
├── packages.txt                # Pacotes de sistema (Tesseract)
├── runtime.txt                # Versão do Python
├── .streamlit/
│   └── config.toml            # Configuração do Streamlit
├── .env.example               # Exemplo de variáveis de ambiente
├── .gitignore                 # Arquivos ignorados pelo Git
├── src/bolao/
│   ├── api_service.py        # Integração API-Football
│   ├── constants.py           # Constantes e configurações
│   ├── exporters.py          # Exportações (CSV, JSON, Discord)
│   ├── models.py             # Modelos de dados
│   ├── ocr_groups.py         # Leitura visual dos grupos
│   ├── parser_ge.py          # Parser do texto do ge
│   ├── scoring.py            # Sistema de pontuação
│   ├── storage.py            # Persistência (local + Supabase)
│   ├── ui_components.py     # Componentes de UI
│   ├── utils.py             # Funções utilitárias
│   └── validation.py        # Validação de palpites
├── data/
│   ├── examples/            # Exemplos de imagens e textos
│   ├── demo_state/          # Estado de demonstração
│   └── state/               # Dados运行时 (não versionado)
└── tests/
    └── test_parser_scoring.py # Testes
```

---

## 🔍 Limitações Conhecidas

1. **OCR visual** — Calibrado para prints do simulador do ge. Prints cortados ou borrados podem exigir correção manual.
2. **Terceiros classificados** — O ge não mostra explicitamente; o sistema infere a partir da fase de 32.
3. **API-Football** — Pode não entregar formato ideal; revisão manual obrigatória.
4. **Persistência local** — Em dev, os dados ficam em `data/state`. Em produção, use Supabase.

---

## 🚧 Roadmap

- [ ] Login por Discord (OAuth)
- [ ] Múltiplos bolões por servidor
- [ ] Cards compartilháveis do pódio (PNG)
- [ ] Integração automática com API oficial
- [ ] Dashboard de estatísticas
- [ ] Histórico de edições

---

## 📄 Licença

MIT License —贡献 bem-vindo!

---

## 💬 Contato

Dúvidas ou sugestões? Abra uma issue no GitHub ou entre em contato pelo Discord.

---

*Feito com ❤️ para a Copa do Mundo 2026*
# PROJECT_CONTEXT.md — Bolão Copa do Mundo 2026 (Nova Versão)
> Gerado automaticamente por análise agêntica em 2026-06-16. Versão local: `C:\dev\BolaoCopaSanca`

---

## 1. VISÃO GERAL DO PROJETO

**Bolão da Cabine do Glória** é um sistema web de bolão (apostas esportivas) para a **Copa do Mundo 2026**, desenvolvido em Python com Streamlit. O sistema permite que participantes enviem palpites sobre resultados de partidas (Modo Clássico — cartela única pré-Copa; e Modo Jogo a Jogo — palpites por partida em tempo real) e acompanhem rankings automáticos.

O projeto foi desenvolvido pelo usuário **BarujaFe** para o grupo de amigos de São Carlos ("Cabine do Glória"), substituindo o sistema anterior baseado em planilhas/OCR por uma experiência 100% digital com simulador interativo, pontuação automática e persistência em nuvem via Supabase.

**Público-alvo:** ~10 participantes (Baruja, Fantato, Henrique, Murilov, Lucão, Mantovas, Jonaldo, Nikolas, etc.)
**Objetivo principal:** Eliminar trabalho manual com planilhas/OCR e centralizar toda a gestão do bolão.

---

## 2. ARQUITETURA GERAL

```
┌─────────────────────────────────────────────────────┐
│                    USUÁRIO                          │
│          (Navegador Web / Mobile)                    │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│              STREAMLIT (app.py)                      │
│   ┌───────────────┬──────────────────┬────────────┐  │
│   │   Páginas     │    Lógica de     │ Cache      │  │
│   │   Públicas    │    Negócio       │ @st.cache  │  │
│   │   (12)        │    (src/bolao/)  │ data/resource│ │
│   │   + Admin     │    30 módulos    │ TTL=15s    │  │
│   │   (10)        │                  │            │  │
│   └───────────────┴──────────────────┴────────────┘  │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │    CAMADA DE DADOS       │
        │   (Dual Backend)         │
        │                          │
        │  ┌────────────────────┐  │
        │  │   SUPABASE (nuvem)  │  │ ← produção
        │  │   PostgreSQL        │  │
        │  │   9 tabelas         │  │
        │  └────────────────────┘  │
        │         ou               │
        │  ┌────────────────────┐  │
        │  │   JSON Local       │  │ ← desenvolvimento
        │  │   data/state/*.json│  │
        │  └────────────────────┘  │
        └──────────────────────────┘
```

### Fluxo de dados principal

```
1. Usuário acessa app → choose() verifica session_state[nav_page]
2. Login screen → identifica-se (nome) → st.session_state["live_user_name"]
3. Sidebar menu → navegação por grupos (radio/selectbox)
4. Cada página carrega dados via load_app_data_cached() (cache TTL 15s)
5. Palpites são salvos via save_submission() / upsert_live_prediction()
6. Escrita vai para Supabase (se configurado) ou data/state/*.json (fallback)
7. Ranking é calculado sob demanda via rank_predictions() / calculate_live_ranking()
```

### Diferença entre leitura de arquivos locais vs. banco de dados

O sistema usa um **backend duplo** determinado por `get_storage_backend()`:
- Se `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` estão configurados no secrets → usa **Supabase**
- Caso contrário → usa **arquivos JSON locais** em `data/state/`

**Problema conhecido:** O sistema nunca sincroniza dados do Supabase de volta para os arquivos locais. Se o Supabase falha durante uma operação de escrita, há fallback para JSON local, mas isso pode levar a estado inconsistente ("split-brain").

---

## 3. ESTRUTURA DE ARQUIVOS

```
C:\dev\BolaoCopaSanca\
├── app.py                          # 2.863 linhas — entry point Streamlit
├── requirements.txt                # Dependências pip
├── packages.txt                    # Pacotes apt (tesseract-ocr)
├── runtime.txt                     # Python 3.11
├── start.bat                       # Script de inicialização Windows
├── .env.example                    # Template de variáveis de ambiente
├── .gitignore                      # Ignora .venv, __pycache__, .env, dados
├── LICENSE                         # MIT
├── README.md                       # Documentação completa (PT/EN)
├── GUIA_BOLAO.md                   # Guia do usuário
├── CORRECAO_OCR_GE.md              # Documentação do OCR para grupos GE
│
├── src/
│   ├── __init__.py
│   └── bolao/                      # Pacote principal
│       ├── __init__.py
│       ├── app.py                  # [NÃO USADO] bytecode cache artefato
│       ├── achievements.py         # 17.587 B — Sistema de badges/conquistas
│       ├── api_service.py          # 4.289 B — Integração API-Football
│       ├── constants.py            # 13.499 B — Constantes (times, grupos, regras)
│       ├── events.py               # 3.381 B — Sistema de eventos/auditoria
│       ├── exporters.py            # 14.077 B — Exportação CSV/JSON/HTML
│       ├── live_scoring.py         # 11.938 B — Pontuação ao vivo (jogo a jogo)
│       ├── migrations.py           # 21.265 B — Migrações de dados
│       ├── models.py               # 13.498 B — Modelos de dados (dataclasses)
│       ├── navigation.py           # 809 B — Navegação centralizada
│       ├── ocr_groups.py           # 16.716 B — OCR para prints de grupos
│       ├── parser_ge.py            # 7.093 B — Parser HTML GE
│       ├── scoring.py              # 20.541 B — Motor de pontuação (3 modos)
│       ├── simulator_engine.py     # 18.892 B — Simulador de grupos/mata-mata
│       ├── simulator_models.py     # 1.665 B — Modelos do simulador
│       ├── social.py               # 7.887 B — Compartilhamento social
│       ├── storage.py              # 62.033 B — Camada de persistência
│       ├── styles.py               # 19.774 B — CSS customizado (tema claro/escuro)
│       ├── ui_admin_brasil.py      # 9.253 B — Admin: Módulo Brasil
│       ├── ui_admin_matches.py     # 35.665 B — Admin: Jogos e agenda
│       ├── ui_cartela.py           # 31.829 B — UI: Minha Cartela
│       ├── ui_components.py        # 11.096 B — Componentes compartilhados
│       ├── ui_live_matches.py      # 94.100 B — UI: Jogos ao vivo (maior módulo)
│       ├── ui_ranking.py           # 43.073 B — UI: Rankings
│       ├── ui_simulator.py         # 32.426 B — UI: Simulador interativo
│       ├── ui_social_pages.py      # 38.654 B — UI: Páginas sociais
│       ├── utils.py                # 6.905 B — Utilitários
│       ├── validation.py           # 1.922 B — Validação de palpites
│       └── worldcup_2026_data.py   # 22.403 B — Dados embutidos da Copa
│
├── data/
│   ├── state/                      # Estado ativo da aplicação
│   │   ├── config.json             # Configurações (pontuação, flags)
│   │   ├── matches_2026.json       # Partidas da Copa
│   │   ├── official_result.json    # Resultado oficial (clássico)
│   │   ├── live_predictions.json   # Palpites jogo a jogo
│   │   ├── events.json             # Eventos/feed de atividades
│   │   ├── migrations.json         # Estado das migrações
│   │   ├── registered_participants.json  # Participantes registrados
│   │   ├── archived_participants.json    # Participantes arquivados
│   │   ├── brasil_palpites_goleadores.json       # Palpites goleadores BR
│   │   ├── brasil_resultados_goleadores.json     # Resultados goleadores BR
│   │   ├── brasil_palpites_classicos.json        # Palpites clássicos BR
│   │   ├── brasil_palpites_classicos.json        # Palpites clássicos BR
│   │   ├── ranking_snapshots.json  # Snapshots de ranking
│   │   ├── comentarios_jogo.json   # Comentários de partidas
│   │   ├── submissions/           # Palpites clássicos (individuais)
│   │   └── uploads/               # Uploads de arquivos
│   ├── backups/                   # Backups automáticos
│   ├── demo_state/                # Dados de demonstração
│   └── examples/                  # Exemplos para OCR
│
├── supabase_migrations/
│   ├── 2026_live_mode.sql          # Criação: bolao_matches, bolao_live_predictions, bolao_events
│   └── 2026_brasil_module.sql      # Criação: brasil_palpites_goleadores, etc.
│
├── tests/
│   ├── test_admin_overrides.py     # 8.540 B — Testes de override admin
│   ├── test_backup_restore.py      # 2.805 B — Backup/restore
│   ├── test_bolao.py               # 6.357 B — Testes unitários base
│   ├── test_bolao_v2.py            # 2.314 B — Testes modo V2
│   ├── test_live_mode.py           # 11.364 B — Testes modo ao vivo
│   ├── test_parser_scoring.py      # 10.763 B — Testes parser + pontuação
│   ├── test_simulator.py           # 30.884 B — Testes do simulador
│   ├── test_text_cleanup.py        # 1.658 B — Limpeza de texto
│   └── test_ui_robustness.py       # 16.898 B — Mocks e testes de UI
│
├── tools/
│   ├── apply_predictions.py        # CLI: aplicar palpites de arquivo
│   ├── extract_simulator_html.py   # CLI: extrair dados do simulador
│   ├── make_backup.py              # CLI: criar backup
│   └── restore_backup.py           # CLI: restaurar backup
│
├── assets/
│   └── icon.png                    # Ícone do app (1.7 MB)
│
├── backup/                         # Backups manuais (pódios, rankings)
├── docs/                           # Documentação técnica
├── .streamlit/
│   ├── config.toml                 # Tema e configuração do Streamlit
│   ├── secrets.toml                # Credenciais (NÃO COMMITAR)
│   └── secrets.toml.example        # Template de secrets
│
├── .devcontainer/
│   └── devcontainer.json           # Configuração de dev container
│
├── Simulador da Copa do Mundo 2026.html  # Página do simulador GE baixada
└── Simulador da Copa do Mundo 2026_files/  # Assets do simulador GE (CSS, JS, img)
```

---

## 4. STACK TECNOLÓGICA

### Python e dependências (requirements.txt)

| Pacote | Versão | Finalidade |
|--------|--------|------------|
| `streamlit` | 1.58.0 | Framework web principal |
| `pandas` | 3.0.3 | Manipulação de dados, DataFrames |
| `requests` | 2.33.1 | HTTP client (API-Football) |
| `pillow` | 12.2.0 | Processamento de imagens (OCR) |
| `pytesseract` | 0.3.13 | OCR Tesseract (grupos GE) |
| `supabase` | 2.30.1 | Cliente Supabase (PostgreSQL) |
| `streamlit-autorefresh` | 0.0.1 | Auto refresh para relógio/temporizador |

### Dependências de sistema (packages.txt)

| Pacote | Finalidade |
|--------|------------|
| `tesseract-ocr` | OCR para extração de grupos de imagens |
| `tesseract-ocr-por` | Idioma português para OCR |
| `tesseract-ocr-eng` | Idioma inglês para OCR |

### Runtime

| Config | Valor |
|--------|-------|
| `runtime.txt` | python-3.11 |
| Ambiente virtual | .venv (Python 3.12 local, mas deploy usa 3.11) |

### Dependências adicionais (instaladas no .venv local)

- `pyarrow` 24.0.0 — usado internamente por Streamlit/pandas
- `pydantic` 2.13.4 — validação (não usado diretamente no código do app)
- `altair` 6.2.1 — gráficos Streamlit
- `httpx` 0.28.1 — HTTP alternativo
- `pytest` 9.0.3 — testes
- `gitpython` 3.1.50 — info de versão nas migrações

### Variáveis de Ambiente (necessárias para produção)

| Variável | Obrigatória? | Descrição |
|----------|-------------|-----------|
| `SUPABASE_URL` | Sim (produção) | URL do projeto Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | Sim (produção) | Chave service role do Supabase |
| `ADMIN_PASSWORD` | Sim (produção) | Senha da área administrativa |
| `APIFOOTBALL_KEY` | Não | Chave da API-Football para resultados automáticos |

Essas variáveis podem ser configuradas via:
- `.env` (desenvolvimento local)
- `.streamlit/secrets.toml` (desenvolvimento local)
- Streamlit Cloud Secrets (produção)

---

## 5. BANCO DE DADOS — SUPABASE

O sistema utiliza até **9 tabelas** no Supabase PostgreSQL, criadas automaticamente via `_ensure_supabase_tables()` em `storage.py`:

### Tabela: `bolao_matches`
| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `match_id` | TEXT | PK | | ID único da partida |
| `phase` | TEXT | NOT NULL | | Fase (grupos, fase_32, oitavas...) |
| `group` | TEXT | YES | | Grupo (A-L) |
| `round_label` | TEXT | YES | | Rótulo da rodada |
| `home_team` | TEXT | NOT NULL | | Time mandante |
| `away_team` | TEXT | NOT NULL | | Time visitante |
| `starts_at` | TEXT | NOT NULL | | Data/hora ISO |
| `starts_at_timezone` | TEXT | YES | 'America/Sao_Paulo' | Fuso horário |
| `lock_at` | TEXT | YES | | Fechamento dos palpites |
| `status` | TEXT | YES | 'scheduled' | scheduled/locked/live/finished/result_approved |
| `official_home_goals` | INT | YES | | Placar oficial mandante |
| `official_away_goals` | INT | YES | | Placar oficial visitante |
| `winner` | TEXT | YES | | Vencedor ou 'draw' |
| `source` | TEXT | YES | 'manual' | Origem do resultado |
| `sort_order` | INT | YES | 0 | Ordem de exibição |
| `has_custom_lock` | BOOLEAN | YES | FALSE | Lock customizado |
| `stadium` | TEXT | YES | | Estádio |
| `modo_relampago_ativo` | BOOLEAN | YES | FALSE | Modo relâmpago (2º tempo) |
| `placar_intervalo_mandante` | INT | YES | | Placar do intervalo mandante |
| `placar_intervalo_visitante` | INT | YES | | Placar do intervalo visitante |
| `bets_manual_closed` | BOOLEAN | YES | | Override manual de abertura |
| `created_at` | TIMESTAMPTZ | YES | NOW() | |
| `updated_at` | TIMESTAMPTZ | YES | NOW() | |

**Índices:** `idx_bolao_matches_starts_at`, `idx_bolao_matches_status`
**Quem lê:** `load_matches()`, `admin_matches_agenda()`, todas as UIs
**Quem escreve:** `save_matches()`, `admin_matches_agenda()`

---

### Tabela: `bolao_live_predictions`
| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | TEXT | PK | | `{participant_key}_{match_id}` |
| `participant_name` | TEXT | NOT NULL | | Nome do participante |
| `participant_key` | TEXT | NOT NULL | | Chave normalizada |
| `match_id` | TEXT | NOT NULL | | ID da partida |
| `predicted_home_goals` | INT | NOT NULL | | Gols mandante previstos |
| `predicted_away_goals` | INT | NOT NULL | | Gols visitante previstos |
| `submitted_at` | TEXT | YES | | ISO timestamp |
| `updated_at` | TEXT | YES | | ISO timestamp |
| `confirmation_code` | TEXT | YES | | Código de confirmação |
| `locked_at` | TEXT | YES | | Quando foi bloqueado |
| `is_locked` | BOOLEAN | YES | FALSE | |
| `is_late` | BOOLEAN | YES | FALSE | Palpite atrasado |
| `points` | INT | YES | | Pontos ganhos |
| `scoring_breakdown` | JSONB | YES | '[]' | Detalhamento |
| `schema_version` | TEXT | YES | 'live-v1' | |
| `predicted_second_half_home_goals` | INT | YES | | Modo relâmpago |
| `predicted_second_half_away_goals` | INT | YES | | Modo relâmpago |
| `contador_edicoes` | INT | YES | 0 | Nº de edições |
| `active` | BOOLEAN | YES | TRUE | Para soft delete |
| `archived_reason` | TEXT | YES | | Motivo do arquivamento |
| `created_at` | TIMESTAMPTZ | YES | NOW() | |

**Índices:** `idx_live_preds_participant_key`, `idx_live_preds_match_id`, `idx_live_preds_submitted_at`
**Constraint:** `unique_participant_match` (participant_key, match_id)
**Quem lê:** `load_live_predictions()`, `calculate_live_ranking()`, todas as UIs
**Quem escreve:** `upsert_live_prediction()`, `save_live_predictions()`, `sync_official_results_to_matches()`

---

### Tabela: `bolao_submissions`
| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | TEXT | PK | | `submission_id` |
| `participant` | TEXT | NOT NULL | | Nome do participante |
| `groups` | JSONB | NOT NULL | | Palpites dos grupos |
| `best_thirds` | JSONB | YES | | Melhores terceiros |
| `knockout` | JSONB | YES | | Chaveamento mata-mata |
| `champion` | TEXT | YES | | Campeão |
| `submission_id` | TEXT | NOT NULL | | ID duplicado (redundante) |
| `submitted_at` | TEXT | YES | | ISO timestamp |
| `status` | TEXT | YES | 'confirmado' | |
| `meta` | JSONB | YES | | Metadados (group_matches, etc.) |
| `mode` | TEXT | YES | | 'classic' |
| `schema_version` | TEXT | YES | 'classic-v1' | |
| `active` | BOOLEAN | YES | TRUE | Soft delete |
| `archived_reason` | TEXT | YES | | |
| `created_at` | TIMESTAMPTZ | YES | NOW() | |

**Quem lê:** `load_submissions()`, `rank_predictions()`, admin
**Quem escreve:** `save_submission()`, `delete_submission()`

---

### Tabela: `bolao_official`
| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | TEXT | PK | 'official' | ID fixo 'official' |
| `participant` | TEXT | NOT NULL | | 'Resultado oficial' |
| `groups` | JSONB | NOT NULL | | Resultado oficial dos grupos |
| `best_thirds` | JSONB | YES | | Terceiros oficiais |
| `knockout` | JSONB | YES | | Mata-mata oficial |
| `champion` | TEXT | YES | | Campeão oficial |
| `submission_id` | TEXT | YES | | |
| `submitted_at` | TEXT | YES | | |
| `status` | TEXT | YES | 'aprovado' | |
| `meta` | JSONB | YES | | group_matches com placares |
| `mode` | TEXT | YES | | |
| `schema_version` | TEXT | YES | | |
| `updated_at` | TIMESTAMPTZ | YES | NOW() | |

**Quem lê:** `load_official()`, `rank_predictions()`
**Quem escreve:** `save_official()`, admin

---

### Tabela: `bolao_config`
| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `key` | TEXT | PK | | 'main' para config geral |
| `value` | JSONB | NOT NULL | | Config completa em JSON |
| `updated_at` | TIMESTAMPTZ | YES | NOW() | |

**Quem lê:** `load_config()`
**Quem escreve:** `save_config()`

---

### Tabela: `bolao_events`
| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | TEXT | PK | | UUID curto (8 chars) |
| `timestamp` | TEXT | NOT NULL | | ISO timestamp |
| `kind` | TEXT | NOT NULL | | Tipo do evento |
| `message` | TEXT | NOT NULL | | Mensagem descritiva |
| `visibility` | TEXT | YES | 'public' | public/admin |
| `metadata` | JSONB | YES | | |
| `created_at` | TIMESTAMPTZ | YES | NOW() | |

**Índices:** `idx_bolao_events_timestamp`, `idx_bolao_events_visibility`
**Quem lê:** `load_events()`, feed de atividades, admin
**Quem escreve:** `append_event()`

---

### Tabela: `brasil_palpites_goleadores`
| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | UUID | PK | gen_random_uuid() | |
| `participante_nome` | TEXT | NOT NULL | | |
| `jogo_id` | TEXT | NOT NULL | | |
| `gols_brasil_apostados` | INT | NOT NULL | 0 | |
| `goleadores` | JSONB | NOT NULL | '[]' | |
| `assistentes` | JSONB | NOT NULL | '[]' | |
| `pontos_ganhos` | INT | YES | | |
| `reservas` | JSONB | YES | '[]' | |
| `created_at` | TIMESTAMPTZ | YES | NOW() | |
| `updated_at` | TIMESTAMPTZ | YES | NOW() | |

**Constraint:** UNIQUE(participante_nome, jogo_id)
**Quem lê:** `load_brasil_palpites_goleadores()`, módulo Brasil UI
**Quem escreve:** `save_brasil_palpite_goleadores()`

---

### Tabela: `brasil_resultados_goleadores`
| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `jogo_id` | TEXT | PK | | |
| `goleadores_reais` | JSONB | YES | '[]' | |
| `assistentes_reais` | JSONB | YES | '[]' | |
| `primeiro_gol_copa` | TEXT | YES | | Gol de ouro |
| `encerrado` | BOOLEAN | YES | FALSE | |
| `updated_at` | TIMESTAMPTZ | YES | NOW() | |

**Quem lê:** `load_brasil_resultados_goleadores()`
**Quem escreve:** `save_brasil_resultado_goleadores()`

---

### Tabela: `brasil_palpites_classicos`
| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `participante_nome` | TEXT | PK | | |
| `artilheiro_brasil_copa` | TEXT | YES | | |
| `artilheiro_geral_copa` | TEXT | YES | | |
| `gol_de_ouro` | TEXT | YES | | |
| `pontos_artilheiro_brasil` | INT | YES | 0 | |
| `pontos_artilheiro_geral` | INT | YES | 0 | |
| `pontos_gol_de_ouro` | INT | YES | 0 | |
| `created_at` | TIMESTAMPTZ | YES | NOW() | |
| `updated_at` | TIMESTAMPTZ | YES | NOW() | |

**Quem lê:** `load_brasil_palpites_classicos()`, integração com scoring
**Quem escreve:** `save_brasil_palpite_classico()`

---

### Tabelas auxiliares (sem suporte completo a Supabase no storage.py)

| Tabela | Criada em storage.py? | Notas |
|--------|----------------------|-------|
| `ranking_snapshots` | Sim | Snapshots de ranking por rodada |
| `comentarios_jogo` | Sim | Comentários em partidas (max 140 chars) |

---

## 6. MÓDULOS PYTHON — SRC/

### `src/bolao/__init__.py`
- **Propósito:** Package init (vazio)

### `src/bolao/achievements.py` (17.587 B)
- **Propósito:** Sistema de badges/conquistas para participantes
- **Funções públicas:**
  - `calculate_achievements(ctx: AppDataContext) -> dict[str, list[dict]]` — Calcula todas as conquistas de todos os participantes
- **Badges implementados:**
  - 🔥 Sequência Quente (pontuar em 5+ jogos seguidos)
  - 🦓 Caçador de Zebras (3+ resultados que <30% acertou)
  - 👑 Rei dos Exatos (5+ placares exatos)
  - 🐐 GOAT (3+ rodadas consecutivas na liderança)
  - 💯 Aproveitamento Máximo (80%+ acerto)
  - 🎰 Sortudo (3+ resultados onde favorito tinha >70%)
  - 🧹 Não Perde um (palpitar em todos os jogos da rodada)
  - 🧠 Mestre dos Palpites (liderar ranking combinado)
- **Dependências internas:** storage (AppDataContext), utils, live_scoring, scoring
- **Dependências externas:** nenhuma

---

### `src/bolao/api_service.py` (4.289 B)
- **Propósito:** Integração com API-Football para sincronização automática de resultados
- **Classes:**
  - `APIResponse` — dataclass com ok/message/raw/prediction
  - `APIFootballService` — serviço de integração
    - `__init__(api_key: str | None = None)` — Construtor
    - `enabled() -> bool` — Verifica se API key está configurada
    - `fetch_world_cup_2026() -> APIResponse` — Busca fixtures e standings
    - `_adapt_raw_to_prediction(raw: dict) -> Prediction` — Converte resposta bruta
- **Dependências internas:** models (Prediction), utils (now_iso)
- **Dependências externas:** requests

---

### `src/bolao/constants.py` (13.499 B)
- **Propósito:** Constantes do sistema
- **Conteúdo:**
  - `APP_NAME`, `APP_SUBTITLE` — Nome do app
  - `GROUPS` = lista A-L
  - `PHASES` = ["fase_32", "oitavas", "quartas", "semifinais", "final"]
  - `PHASE_LABELS`, `PHASE_ALIASES` — Mapas de nomes
  - `GE_GROUP_ROW_ORDER` — Ordem fixa dos times nos cards do simulador GE
  - `TEAM_ALIASES` — 48 times com ~200 alias
  - `ALL_TEAMS` — Lista de 48 times canônicos
  - Regras de pontuação padrão: `DEFAULT_WEIGHTED_RULES`, `DEFAULT_UNIFORM_RULES`, `DEFAULT_V2_RULES`
  - `ACTIVE_PARTICIPANT_NAMES` — Lista de participantes ativos
  - `ELENCO_BRASIL_2026` — 26 jogadores da seleção brasileira
  - `VENUES_COPA_2026` — 16 estádios
  - `JOGADORES_COPA_2026` — Jogadores por seleção

---

### `src/bolao/events.py` (3.381 B)
- **Propósito:** Sistema de eventos/feed de atividades
- **Funções públicas:**
  - `append_event(kind: str, message: str, metadata: dict | None = None, visibility: str = "public")` — Adiciona evento
  - `load_events(limit: int = 20, visibility: str | None = None, include_archived: bool = False) -> list[dict]` — Carrega eventos
- **Dependências internas:** storage (get_storage_backend, etc.), utils
- **Dependências externas:** streamlit

---

### `src/bolao/exporters.py` (14.077 B)
- **Propósito:** Exportação de dados em CSV, JSON, HTML (pódio)
- **Funções públicas:**
  - `ranking_to_dataframe(scores: list[ScoreBreakdown]) -> pd.DataFrame`
  - `ranking_csv(scores: list[ScoreBreakdown]) -> str`
  - `ranking_json(scores: list[ScoreBreakdown]) -> str`
  - `discord_ranking(scores: list[ScoreBreakdown], title: str) -> str`
  - `podium_html(scores: list[ScoreBreakdown], status_label: str, date_label: str | None) -> str`
  - `details_dataframe(score: ScoreBreakdown) -> pd.DataFrame`
  - `live_podium_html(live_scores: list[dict], status_label: str, date_label: str | None) -> str`
- **Dependências internas:** models (ScoreBreakdown), utils
- **Dependências externas:** pandas

---

### `src/bolao/live_scoring.py` (11.938 B)
- **Propósito:** Motor de pontuação para o Modo Jogo a Jogo e Módulo Brasil
- **Funções públicas:**
  - `calculate_live_prediction_points(prediction: LivePrediction, match: LiveMatch, config: dict) -> dict` — Calcula pontos de um palpite jogo a jogo
  - `calculate_live_ranking(live_predictions: list, matches: list, config: dict) -> list[dict]` — Ranking jogo a jogo completo
  - `calcular_pontos_goleadores(...) -> dict` — Pontos do Módulo Brasil (goleadores/assistentes)
  - `calcular_pontos_artilheiro_classico(palpitado: str, artilheiros_reais: list, config: dict, is_geral: bool) -> int` — Pontos de artilheiro clássico
- **Regras de pontuação (Modo Jogo a Jogo):**
  - Placar exato: 5 pts (isolated_max: não acumula)
  - Resultado correto: 3 pts
  - Acertar gols de um time: 1 pt
  - Acertar saldo de gols: 1 pt
  - Modo Relâmpago (2º tempo): 4 pts exato, 2 pts resultado
- **Dependências internas:** models, utils
- **Dependências externas:** collections.Counter

---

### `src/bolao/migrations.py` (21.265 B)
- **Propósito:** Migrações de dados e upgrades do sistema
- **Funções públicas:**
  - `get_git_info() -> tuple[str, str]` — Branch e commit atuais
  - `migrate_to_parallel_modes() -> dict` — Migração principal (backup + atualização)
  - `migrate_existing_submissions_to_classic_schema() -> dict` — Alias para compatibilidade
  - `sync_classic_to_live_predictions() -> int` — Copia palpites clássicos para jogo a jogo
  - `perform_pre_cleanup_backup() -> tuple[Path, Path]` — Backup antes de limpeza
  - `cleanup_active_participants(allowed_names: set) -> dict` — Remove participantes não autorizados
  - `load_archived_participants() -> dict` — Carrega backup de participantes arquivados
  - `restore_archived_participant(pkey: str) -> bool` — Restaura participante
  - `run_participant_cleanup_migration() -> dict` — Migração de limpeza
- **Dependências internas:** storage, utils
- **Dependências externas:** streamlit, shutil, subprocess, json, os

---

### `src/bolao/models.py` (13.498 B)
- **Propósito:** Modelos de dados (dataclasses)
- **Classes:**
  - `ParseIssue` — level, message, context
  - `Match` — a, b, winner (para mata-mata)
  - `Prediction` — Palpite clássico completo
    - Campos: participant, groups, best_thirds, knockout, champion, submission_id, submitted_at, status, meta, mode, schema_version
    - `to_dict()`, `from_dict()`
  - `ScoreBreakdown` — Resultado de pontuação
    - Campos: participant, total, group_points, best_third_points, knockout_points, champion_points, champion_hit, group_hits, best_third_hits, knockout_hits, exact_scores, submitted_at, details, tie_breaker
    - `to_row(position: int | None) -> dict`
  - `LiveMatch` — Partida no modo jogo a jogo
    - 20+ campos incluindo match_id, times, status, resultado, estádio, modo relâmpago
    - `to_dict()`, `from_dict()`
  - `LivePrediction` — Palpite de partida individual
    - Campos: id, participant_name, participant_key, match_id, predicted_home/away_goals, submitted_at, updated_at, confirmation_code, locked_at, is_locked, is_late, points, scoring_breakdown, schema_version, predicted_second_half_*, contador_edicoes
    - `to_dict()`, `from_dict()
  - `ActivityEvent` — Evento de auditoria
    - Campos: id, timestamp, kind, message, visibility, metadata
    - `to_dict()`, `from_dict()`
- **Dependências internas:** constants
- **Dependências externas:** dataclasses

---

### `src/bolao/navigation.py` (809 B)
- **Propósito:** Navegação centralizada entre páginas
- **Funções públicas:**
  - `navigate_to(page: str, *, admin_mode: bool | None = None)` — Atualiza nav_page e rerun
- **Dependências externas:** streamlit

---

### `src/bolao/ocr_groups.py` (16.716 B)
- **Propósito:** OCR para extração de classificação de grupos a partir de prints do simulador GE
- **Funções públicas:**
  - `extract_groups_from_screenshot(image_path: str) -> dict` — Extrai grupos A-F e G-L
  - `detect_card_positions(image) -> list[tuple]` — Detecta cards na imagem
  - `read_color_at_position(image, x, y) -> str` — Lê cor da linha (roxo=1º, rosa=2º, ocre=3º)
- **Dependências internas:** constants (GE_GROUP_ROW_ORDER)
- **Dependências externas:** pillow (Image), pytesseract

---

### `src/bolao/parser_ge.py` (7.093 B)
- **Propósito:** Parse de texto colado do Globo Esporte (simulador de grupos)
- **Funções públicas:**
  - `parse_ge_knockout_text(text: str) -> dict` — Parse de texto do mata-mata
  - `knockout_to_rows(knockout: dict) -> list[dict]` — Converte knockout para linhas
  - `rows_to_knockout(rows: list[dict]) -> dict` — Converte linhas de volta para knockout

---

### `src/bolao/scoring.py` (20.541 B)
- **Propósito:** Motor de pontuação para Modo Clássico (3 modos)
- **Classes:**
  - `ScoreConfig` — Configuração de pontuação (mode, weighted_rules, uniform_rules, v2_rules)
- **Funções públicas:**
  - `score_prediction(pred: Prediction, official: Prediction, config: ScoreConfig) -> ScoreBreakdown` — Pontua um palpite
  - `rank_predictions(predictions: list, official: Prediction | None, config: ScoreConfig) -> list[ScoreBreakdown]` — Ranking completo com cache hash
  - `ranking_rows(scores: list[ScoreBreakdown]) -> list[dict]`
- **Modos de pontuação:**
  - **V2 (padrão):** Placar exato (5), resultado+saldo (3), resultado (2), gols de 1 time (1), bônus cumulativos
  - **Ponderado:** Pontos por posição no grupo (1º=5, 2º=3, 3º=2 se melhor terceiro), mata-mata por fase
  - **Uniforme:** 1 ponto por decisão correta
- **Critérios de desempate V2:** Total > Campeão > Knockout > Exatos > Grupo > Timestamp > Alfabético
- **Integração com Módulo Brasil:** Soma pontos de artilheiros e gol de ouro
- **Dependências internas:** constants, models, utils, worldcup_2026_data, storage, live_scoring
- **Dependências externas:** streamlit (cache_data), hashlib, json

---

### `src/bolao/simulator_engine.py` (18.892 B)
- **Propósito:** Motor de simulação — calcula classificação de grupos, melhores terceiros, bracket do mata-mata
- **Funções públicas:**
  - `calculate_group_standings(group_letter: str, matches: list[GroupMatch]) -> list[GroupStanding]` — Classificação do grupo com critérios FIFA
  - `calculate_best_thirds(all_standings: dict[str, list[GroupStanding]]) -> list[GroupStanding]` — Melhores terceiros
  - `build_bracket(pred: Prediction, groups_result: dict, thirds_result: list) -> dict` — Monta chaveamento
  - `validate_prediction_complete(pred: Prediction) -> tuple[bool, list]` — Validação completa
  - `normalize_slots(raw_slots) -> dict[int, str]`
  - `serialize_slots_to_prediction(slots: dict, pred: Prediction)` — Serializa slots
- **Critérios de desempate FIFA 2026:** Pontos > Confronto direto > Saldo > Gols marcados > Ordem visual
- **Dependências internas:** worldcup_2026_data, simulator_models, models, constants
- **Dependências externas:** functools

---

### `src/bolao/simulator_models.py` (1.665 B)
- **Propósito:** Modelos de dados do simulador
- **Classes:**
  - `GroupStanding` — team_id, name, abbr, points, played, wins, draws, losses, gf, ga, gd
  - `GroupMatch` — id, group, round, home_id, away_id, home_score, away_score

---

### `src/bolao/social.py` (7.887 B)
- **Propósito:** Funções de compartilhamento social e textos para WhatsApp
- **Funções públicas:**
  - `build_classic_share_text(...)` — Texto pós-palpite clássico
  - `build_live_match_share_text(...)` — Texto de palpite individual
  - `build_daily_games_text(matches: list)` — Jogos do dia
  - `build_live_daily_share_text(matches: list)` — Alias compatibilidade
  - `build_ranking_share_text(...)` — Resumo dos rankings
  - `build_zoacao_text(nome1, nome2, ...)` — Texto de provocação automática
- **Dependências internas:** nenhuma (usa tipagem Any para matches)
- **Dependências externas:** random

---

### `src/bolao/storage.py` (62.033 B)
- **Propósito:** **Camada de persistência mais importante do sistema.** Gerencia leitura/escrita no Supabase e arquivos JSON locais.
- **Funções públicas (parcial):**
  - `get_storage_backend() -> str` — 'supabase' ou 'local'
  - `ensure_state()` — Cria diretórios e arquivos iniciais
  - `load_config() -> dict` / `save_config(config: dict)`
  - `load_submissions(include_archived: bool) -> list[Prediction]`
  - `save_submission(prediction: Prediction, overwrite: bool) -> Path`
  - `delete_submission(submission_id: str) -> bool`
  - `load_official() -> Prediction | None` / `save_official(prediction: Prediction) -> Path`
  - `load_app_data_cached() -> AppDataContext` — Factory cacheada (TTL 15s)
  - `load_matches() -> list[LiveMatch]` / `save_matches(matches: list)`
  - `load_live_predictions(include_archived: bool) -> list[LivePrediction]`
  - `save_live_predictions(predictions: list)`
  - `upsert_live_prediction(...) -> LivePrediction`
  - `export_all_state() -> dict` / `import_all_state(data: dict)`
  - `reset_state()` / `load_demo_state()`
  - `sync_official_results_to_matches() -> int`
  - `load_registered_participants(...) -> list[str]`
  - `register_participant(name: str)` / `delete_registered_participant(name: str)`
  - `archive_participant(name, reason, backup_ref) -> bool`
  - `restore_participant(pkey: str) -> bool`
  - Módulo Brasil: `load_brasil_palpites_goleadores()`, `save_brasil_palpite_goleadores()`, etc.
  - `load_comentarios_jogo(jogo_id: str)`, `save_comentario_jogo()`, `delete_comentario_jogo()`
  - `recalcular_pontos_modulo_brasil(jogo_id: str)`
- **Dependências internas:** constants, models, utils, events
- **Dependências externas:** streamlit, os, shutil, supabase (create_client)

---

### `src/bolao/styles.py` (19.774 B)
- **Propósito:** CSS customizado com tema claro/escuro/sistema
- **Funções públicas:**
  - `get_theme_css(theme_mode: str) -> str` — Gera CSS completo baseado no tema
  - `inject_css()` — Injeta CSS no Streamlit
- **Dependências externas:** streamlit

---

### `src/bolao/ui_admin_brasil.py` (9.253 B)
- **Propósito:** Painel admin para gerenciar seleção brasileira
- **Funções públicas:**
  - `admin_selecao_brasileira()` — UI completa (elenco, suspensões, goleadores reais)
- **Abas:** Elenco e Status | Goleadores Reais por Jogo
- **Dependências internas:** constants, storage, utils, navigation

---

### `src/bolao/ui_admin_matches.py` (35.665 B)
- **Propósito:** Painel admin para gerenciar jogos e agenda
- **Funções públicas:**
  - `admin_matches_agenda()` — UI completa
  - `admin_palpites_jogo_a_jogo()` — Visualização admin dos palpites jogo a jogo
- **Abas:** Lista de Jogos | Cadastrar/Editar | Importar/Exportar CSV | Aprovar Resultados
- **Dependências internas:** models, storage, utils, navigation

---

### `src/bolao/ui_cartela.py` (31.829 B)
- **Propósito:** Página "Minha Cartela" — perfil do participante
- **Funções públicas:**
  - `render_minha_cartela()` — UI completa da cartela pessoal
- **Seções:** Palpites clássicos, palpites jogo a jogo, conquistas/badges, compartilhar
- **Dependências internas:** models, storage, utils, achievements, scoring, live_scoring

---

### `src/bolao/ui_components.py` (11.096 B)
- **Propósito:** Componentes de UI reutilizáveis
- **Funções públicas:**
  - `inject_css()` — Carrega estilos
  - `render_theme_selector()` — Seletor de tema na sidebar
  - `hero(title, subtitle, description)` — Cabeçalho estilizado
  - `kpi_grid(items: list[tuple])` — Grid de KPIs
  - `step_cards()` — Cards de passo a passo
  - `card_start(title)`, `card_end()` — Cards container
  - `podium(top3: list, avatar_url_fn)` — Pódio visual
  - `dataframe_to_groups(df) -> dict`
  - `groups_dataframe(groups: dict) -> pd.DataFrame`
  - `badges(badges_list: list)`
  - `issues_box(issues: list)`
  - `render_page_header(...)`
  - `render_empty_state(...)`
  - `render_badge(...)`
- **Dependências internas:** constants, styles
- **Dependências externas:** streamlit, pandas

---

### `src/bolao/ui_live_matches.py` (94.100 B — MAIOR MÓDULO)
- **Propósito:** Interface do modo Jogo a Jogo — palpite, match center, jogos do Brasil
- **Funções públicas:**
  - `is_match_open_for_prediction(match, now) -> bool` — Verifica se jogo está aberto para palpites
  - `jogo_esta_ao_vivo(m) -> bool` — Verifica se jogo está ao vivo
  - `render_jogos_de_hoje()` — Página principal de palpites
  - `render_jogos_do_brasil()` — Jogos do Brasil
  - `render_match_center()` — Match Center completo
- **Dependências internas:** models, storage, utils, live_scoring, ui_simulator, social, ui_components
- **Dependências externas:** streamlit, pandas, streamlit_autorefresh

---

### `src/bolao/ui_ranking.py` (43.073 B)
- **Propósito:** Páginas de ranking/classificação
- **Funções públicas:**
  - `render_rankings_tabs()` — Abas de ranking (combinado, clássico, jogo a jogo)
  - `verificar_mudanca_posicao(user_name) -> dict | None` — Verifica mudança de posição
- **Dependências internas:** models, storage, scoring, live_scoring, exporters

---

### `src/bolao/ui_simulator.py` (32.426 B)
- **Propósito:** Simulador interativo de palpites (usado em várias páginas)
- **Funções públicas:**
  - `render_simulator(pred: Prediction) -> Prediction` — Renderiza o simulador completo
  - `init_simulator_state(pred: Prediction, force_reset: bool)` — Inicializa estado da sessão
  - `get_guess_completion_state(pred: Prediction) -> dict`
  - `get_team_badge_path(team_name: str) -> str`
- **Dependências internas:** worldcup_2026_data, simulator_engine, simulator_models, models, constants, storage, validation, utils

---

### `src/bolao/ui_social_pages.py` (38.654 B)
- **Propósito:** Páginas sociais (Central do Bolão, Palpites do Grupo, Análise, Duelo, Regras)
- **Funções públicas:**
  - `render_central_do_bolao()` — Feed social
  - `render_palpites_do_grupo()` — Palpites de outros participantes
  - `render_analise_dos_palpites()` — Estatísticas detalhadas
  - `render_duelo_de_palpites()` — Comparação 1v1 entre participantes
  - `render_regras_do_bolao()` — Regras do bolão
- **Dependências internas:** storage, models, live_scoring, scoring, achievements, social, utils

---

### `src/bolao/utils.py` (6.905 B)
- **Propósito:** Utilitários gerais
- **Funções públicas:**
  - `render_countdown(horario_jogo: datetime, minutos_antes: int) -> str`
  - `now_iso() -> str`
  - `strip_accents(value: str) -> str`
  - `norm_text(value: str) -> str`
  - `norm_team(value: str | None) -> str`
  - `safe_filename(value: str) -> str`
  - `stable_id(*parts: str) -> str`
  - `read_json(path: Path, default: Any) -> Any`
  - `write_json(path: Path, data: Any)` — Atomic write com retry
  - `normalize_participant_key(name: str) -> str` — Gera chave estável
  - `format_display_name(name: str) -> str`
  - `decode_uploaded_file(file) -> str`
  - `short(value: str, size: int) -> str`
  - `canonical_team(value: str | None) -> str | None`
  - `is_debug_mode() -> bool`
  - `buscar_jogador_copa(query: str, limite: int) -> list[dict]`
  - `avatar_url(nome: str) -> str` — DiceBear avatar
  - `foto_jogador(camisa: int, nome: str) -> str`

---

### `src/bolao/validation.py` (1.922 B)
- **Propósito:** Validação de palpites
- **Funções públicas:**
  - `validate_prediction(pred: Prediction, strict: bool) -> list[ParseIssue]`
  - `has_blocking_errors(issues: list[ParseIssue]) -> bool`
- **Dependências internas:** constants, models

---

### `src/bolao/worldcup_2026_data.py` (22.403 B)
- **Propósito:** Dados estáticos da Copa 2026 extraídos do simulador GE
- **Conteúdo:**
  - `TEAMS` — 48 times com id, nome, abbr, badge path
  - `GROUPS_TEAMS` — 12 grupos com 4 times cada (mapeamento ID)
  - `GROUP_MATCHES` — 72 partidas da fase de grupos (id, rodada, grupo, times, data, hora, estádio)
  - `BRACKET_SLOTS` — Slots do chaveamento do mata-mata (fase_32 → final)

---

## 7. ARQUIVO PRINCIPAL — APP.PY

- **Total de linhas:** 2.863
- **Propósito:** Entry point da aplicação Streamlit. Contém todo o roteamento de páginas, inicialização e funções de renderização.

### Fluxo de inicialização

```
1. Importações (topo) — todos os módulos
2. st.set_page_config() — configuração global
3. inject_css() — estilos customizados
4. main() chamada no final do arquivo:
   a. migrate_existing_submissions_to_classic_schema() — migrações
   b. sync_classic_to_live_predictions() — sync
   c. run_participant_cleanup_migration() — limpeza
   d. Auto-login via query params
   e. Inicializa nav_page e admin_mode no session_state
   f. Se não logado e não admin → render_login_screen()
   g. Se logado → sidebar + navegação
```

### Páginas e Abas (ordem de navegação)

**Páginas Públicas (12):**
1. Início — `public_home()`
2. Jogos de Hoje — `render_jogos_de_hoje()`
3. 🇧🇷 Jogos do Brasil — `render_jogos_do_brasil()`
4. Palpite Clássico — `public_submission()`
5. Minha Cartela — `render_minha_cartela()`
6. Ranking — `public_ranking()`
7. Central do Bolão — `render_central_do_bolao()`
8. Palpites do Grupo — `render_palpites_do_grupo()`
9. Análise dos Palpites — `render_analise_dos_palpites()`
10. Duelo de Palpites — `render_duelo_de_palpites()`
11. Match Center — `render_match_center()`
12. Regras — `render_regras_do_bolao()`

**Páginas Admin (10):**
1. Dashboard — `admin_dashboard()`
2. Participantes — `admin_participants()`
3. Palpites Jogo a Jogo — `admin_palpites_jogo_a_jogo()`
4. Jogos e Agenda — `admin_matches_agenda()`
5. Resultados Oficiais — `admin_official_results()`
6. Ranking — `admin_ranking()`
7. Exportações — `admin_exports()`
8. Configurações — `admin_settings()`
9. Auditoria — `admin_auditoria()`
10. Ajuda — `admin_help()`

### Session State Keys

| Key | Tipo | Propósito |
|-----|------|-----------|
| `nav_page` | str | Página atual |
| `admin_mode` | bool | Modo admin ativo? |
| `admin_authenticated` | bool | Admin autenticado? |
| `live_user_name` | str | Nome do usuário logado |
| `live_user_key` | str | Chave normalizada |
| `live_confirmation_code` | str | Código do palpite clássico |
| `public_sim_name` | str | Nome no simulador público |
| `sim_prediction` | Prediction | Palpite sendo editado |
| `edit_mode` | str | new/edit/view |
| `theme_mode` | str | light/dark/system |
| `match_center_selected_match_id` | str | Match center |
| `admin_editing_classic_prediction` | Prediction | Admin editando palpite |
| +30 keys específicas dos componentes |

### Lógica de autenticação/autorização

- **Login público:** Qualquer um pode se identificar com nome (sem senha)
- **Login admin:** Senha única via `ADMIN_PASSWORD` (st.secrets ou env var)
  - Desenvolvimento: senha hardcoded `"brasilhexa"` se `DEBUG_MODE` ou `APP_ENV=development`
  - Produção: senha configurada nos Streamlit Secrets
- **Permissões:** Todos os usuários logados podem ver todas as páginas públicas. Admin tem menu separado.

---

## 8. FUNCIONALIDADES IMPLEMENTADAS

### ✅ Núcleo
- [x] Simulador interativo de grupos (placar → classificação → terceiros → mata-mata → campeão)
- [x] Cálculo automático de classificação de grupos (critérios FIFA 2026)
- [x] Cálculo automático dos melhores terceiros colocados (guloso, 8 slots)
- [x] Chaveamento do mata-mata automático (72 grupos → fase_32 → oitavas → quartas → semi → final)
- [x] Validação completa de palpites antes do envio
- [x] Palpites do Modo Clássico (cartela única pré-Copa)
- [x] Palpites do Modo Jogo a Jogo (por partida)
- [x] Ranking Clássico (3 modos: V2, ponderado, uniforme)
- [x] Ranking Jogo a Jogo (ao vivo)
- [x] Ranking Combinado (clássico + jogo a jogo com pesos)

### ✅ Interface
- [x] Página inicial com herói, CTAs, banner dinâmico, feed de atividades
- [x] Tema claro/escuro/sistema
- [x] Relógio oficial BR e countdown para próximo bloqueio
- [x] Design responsivo (CSS customizado, media queries)
- [x] Sidebar com menu agrupado e acesso rápido
- [x] Pódio animado com confetes pós-Copa
- [x] Match Center (termômetro de palpites, simulação de impacto)
- [x] Minha Cartela (perfil pessoal com badges)
- [x] Central do Bolão (feed social)
- [x] Palpites do Grupo (ver palpites alheios)
- [x] Análise dos Palpites (estatísticas, zebras)
- [x] Duelo de Palpites (comparação 1v1 com texto de zoação)
- [x] Páginas de Regras

### ✅ Admin
- [x] Dashboard com KPIs
- [x] Gerenciamento de participantes (cadastro, arquivamento)
- [x] Gerenciamento de jogos (CRUD completo)
- [x] Inserção de resultados oficiais (manual e via simulador)
- [x] Importação/Exportação CSV de agenda
- [x] Exportações: CSV, JSON, HTML (pódio), Discord
- [x] Backup e restauração completa do estado
- [x] Configurações: pontuação (todos os modos), prazos, flags
- [x] Auditoria: eventos do sistema
- [x] Moderação de comentários
- [x] Restauração de dados de demonstração
- [x] Zona de perigo (reset total, limpeza)

### ✅ Módulo Brasil
- [x] Elenco da seleção brasileira (26 jogadores)
- [x] Palpites de goleadores/assistentes por jogo do Brasil
- [x] Resultados reais de goleadores (admin)
- [x] Cálculo de pontos com regras de suspensão
- [x] Palpites clássicos: artilheiro Brasil, artilheiro geral, gol de ouro
- [x] Ranking Canarinho

### ✅ Conquistas/Badges
- [x] 8 badges automáticos (Sequência Quente, Caçador de Zebras, Rei dos Exatos, etc.)
- [x] Exibição no perfil e cartela

### ✅ OCR e Importação
- [x] OCR de prints do simulador GE (detecção por cor das linhas)
- [x] Parser de texto colado do mata-mata GE
- [x] Integração com API-Football (rascunho, necessita revisão manual)

### ✅ Persistência
- [x] Dual backend: Supabase (produção) e JSON local (desenvolvimento)
- [x] Sincronização automática local → Supabase no startup
- [x] Migrações idempotentes
- [x] Backup/restore completo

### ✅ Social
- [x] Compartilhamento no WhatsApp (palpite, ranking, resumo do dia, zoação)
- [x] Comentários em partidas (max 140 chars)
- [x] Avatares gerados por DiceBear

---

## 9. BUGS CONHECIDOS E PROBLEMAS IDENTIFICADOS

### 🔴 BUG #1 — ArrowInvalid / PyArrow (CRÍTICO)

| Campo | Valor |
|-------|-------|
| **Descrição** | Erro `ArrowInvalid` ao tentar renderizar DataFrames com colunas de tipos mistos |
| **Arquivos afetados** | `ui_cartela.py:362`, `ui_ranking.py:232`, `models.py:105`, `app.py:1760`, `ui_social_pages.py:203` |
| **Causa raiz** | A coluna `"Pontos"` recebe valores `int` em alguns locais (`models.py:105`, `ui_ranking.py:122`) e `str` em outros (`ui_cartela.py:362`, `ui_ranking.py:232`). A coluna `"Pontos Ganhos"` em `ui_social_pages.py:203` também recebe valor `int` que vira texto. Quando o Streamlit tenta converter para PyArrow, o tipo misto causa exceção. |
| **Impacto** | Crash na renderização de páginas que têm DataFrames com essas colunas. Visível nos logs como `ArrowInvalid: Could not convert ...` |
| **Trecho problemático (ui_cartela.py:362)** | `"Pontos": str(res["points"]) if m.status == "result_approved" else "Pendente"` — coluna como string |
| **Trecho problemático (ui_ranking.py:232)** | `"Pontos Ganhos": str(res["points"]) if m.status == "result_approved" else "—"` — coluna como string |
| **Trecho consistente (models.py:105)** | `"Pontos": self.total` — coluna como int |
| **Solução recomendada** | Padronizar tipo: converter TODAS as colunas "Pontos" e "Pontos Ganhos" para string consistentemente via `str()`, ou garantir que sejam sempre `int` usando `int(res["points"]) if res["points"] is not None else 0`. A abordagem mais segura é usar string padronizada em colunas de exibição. |

---

### 🔴 BUG #2 — Funções Duplicadas em app.py (MÉDIO)

| Campo | Valor |
|-------|-------|
| **Descrição** | As funções `public_submission()` e `render_player_single_select()` estão definidas **duas vezes** em app.py |
| **Arquivo** | `app.py` (primeira definição ~linha 235, segunda ~linha 472) |
| **Causa raiz** | Refatoração mal concluída: o código antigo não foi removido quando a nova versão foi adicionada |
| **Impacto** | A segunda definição sobrescreve a primeira (Python resolve dinamicamente), então o bug não é funcionalmente ativo. Porém, o código duplicado (~200 linhas extras) polui o arquivo e pode causar confusão. |
| **Solução recomendada** | Remover as definições duplicadas de `public_submission()` e `render_player_single_select()` (manter apenas a primeira ocorrência que aparece após a seção de comentário `# Removed unused OCR/GE parsing functions`). |

---

### 🔴 BUG #3 — Dual Storage Split-Brain (ALTO)

| Campo | Valor |
|-------|-------|
| **Descrição** | O sistema usa dois backends de armazenamento (Supabase e JSON local) sem sincronização bidirecional |
| **Arquivo** | `storage.py` (funções: `get_storage_backend()`, `save_submission()`, `save_live_predictions()`, etc.) |
| **Causa raiz** | `get_storage_backend()` decide qual backend usar baseado na disponibilidade do Supabase. Se o Supabase está configurado, **todas** as operações vão para ele. Se falha (timeout, erro), o código tenta fallback para local. Dados locais anteriores que não foram migrados para o Supabase ficam invisíveis. |
| **Impacto** | Dados podem ficar inconsistentes. Participantes podem sumir do ranking se seus dados estão em um backend mas o sistema lê do outro. A função `_sync_local_to_supabase()` só roda **uma vez** no startup (`_submissions_synced` flag global). |
| **Solução recomendada** | Implementar sync bidirecional periódico, ou remover o backend local em produção e forçar exclusividade do Supabase. Adicionar um comando admin para forçar re-sync. |

---

### 🟡 BUG #4 — Config Key Inconsistente (MÉDIO)

| Campo | Valor |
|-------|-------|
| **Descrição** | `live_scoring.py:27` usa `goal_one_team` mas o `config.json` salva como `one_team_goals` |
| **Arquivo** | `live_scoring.py:27` vs `storage.py:479` (default_config) |
| **Trecho** | `goal_one_team_points = int(scoring_rules.get("goal_one_team", 1))` |
| **Problema** | A chave no `default_config()` é `"one_team_goals"` mas o código lê `"goal_one_team"`. O fallback para 1 mascara o bug, mas se admin configurar via UI o valor pode ser ignorado. |
| **Impacto** | Configuração de pontos para "acertar gols de um time" pode não ser respeitada se o admin alterar na UI. |
| **Solução** | Unificar a nomenclatura da chave. Alterar `live_scoring.py` para ler `scoring_rules.get("one_team_goals", 1)` ou alterar `storage.py` e a UI para usar `goal_one_team`. |

---

### 🟡 BUG #5 — Conversão Int Forçada (MÉDIO)

| Campo | Valor |
|-------|-------|
| **Descrição** | `models.py:177-178` faz conversão forçada `int()` sem validação |
| **Arquivo** | `models.py:177` (LiveMatch.from_dict) |
| **Trecho** | `official_home_goals=d.get("official_home_goals") if d.get("official_home_goals") is None else int(d.get("official_home_goals"))` |
| **Problema** | Se `official_home_goals` for `0` (zero), a condição `is None` não captura, mas `int(0)` funciona. No entanto, se o valor for `"None"` (string), `int()` falha. |
| **Impacto** | Potencial crash ao carregar partidas com dados corrompidos. |
| **Solução** | Usar `try/except` ou `int(d.get(...)) if d.get(...) is not None else None`. |

---

### 🟡 BUG #6 — TTL de Cache Pode Causar Dados Obsoletos (MÉDIO)

| Campo | Valor |
|-------|-------|
| **Descrição** | `@st.cache_data(ttl=15)` em todas as funções de leitura |
| **Arquivo** | `storage.py` — `load_config()`, `load_submissions()`, `load_live_predictions()`, `load_app_data_cached()` |
| **Problema** | TTL de 15 segundos significa que após escrever dados, o sistema pode ler dados obsoletos por até 15s. As funções de escrita chamam `st.cache_data.clear()`, que limpa **todo** o cache, não apenas a entrada relevante. Isso é ineficiente. |
| **Impacto** | Performance sub-ótima. Cada operação de escrita invalida o cache global. |
| **Solução** | Usar chaves de cache mais granulares (`@st.cache_data(ttl=15, hash_funcs=...)`) em vez de limpar tudo. |

---

### 🟢 BUG #7 — Sem Tratamento de Timezone Consistente (BAIXO)

| Campo | Valor |
|-------|-------|
| **Descrição** | Times zones são tratadas de forma inconsistente entre `utils.py` e `ui_live_matches.py` |
| **Arquivo** | `utils.py:13-42` vs `ui_live_matches.py:26-85` |
| **Problema** | `utils.render_countdown()` usa `timezone(timedelta(hours=-3))` constante, enquanto `is_match_open_for_prediction()` também converte para UTC-3. Mas partidas podem estar em outros fusos (Canadá UTC-4, México UTC-6). |
| **Impacto** | Relógios de countdown podem estar incorretos para jogos em estádios fora do horário de Brasília. |
| **Solução** | Usar o fuso configurado na partida (`starts_at_timezone`) em vez de fixar UTC-3. |

---

## 10. FLUXO DE DADOS — LEITURA E ESCRITA

| Dado | Lido de | Escrito em | Cache | Funções |
|------|---------|-----------|-------|---------|
| **Config** | Supabase `bolao_config` ou `data/state/config.json` | Mesmo local | TTL 15s | `load_config()`, `save_config()` |
| **Palpites clássicos** | Supabase `bolao_submissions` ou `data/state/submissions/*.json` | Mesmo local | TTL 15s | `load_submissions()`, `save_submission()`, `delete_submission()` |
| **Resultado oficial** | Supabase `bolao_official` ou `data/state/official_result.json` | Mesmo local | TTL 15s | `load_official()`, `save_official()` |
| **Partidas** | Supabase `bolao_matches` ou `data/state/matches_2026.json` | Mesmo local | TTL 15s | `load_matches()`, `save_matches()` |
| **Palpites jogo a jogo** | Supabase `bolao_live_predictions` ou `data/state/live_predictions.json` | Mesmo local | TTL 15s | `load_live_predictions()`, `save_live_predictions()`, `upsert_live_prediction()` |
| **Eventos** | Supabase `bolao_events` ou `data/state/events.json` | Mesmo local | TTL 15s | `load_events()`, `append_event()` |
| **Participantes registrados** | Supabase `bolao_config` (key='registered_participants') ou `data/state/registered_participants.json` | Mesmo local | TTL 15s | `load_registered_participants()`, `save_registered_participants()` |
| **Participantes arquivados** | `data/state/archived_participants.json` | Mesmo local | — | `load_archived_participants()`, `save_archived_participants()` |
| **Módulo Brasil (goleadores)** | Supabase `brasil_palpites_goleadores` ou `data/state/brasil_palpites_goleadores.json` | Mesmo local | TTL 15s | `load_brasil_palpites_goleadores()`, `save_brasil_palpite_goleadores()` |
| **Módulo Brasil (resultados)** | Supabase `brasil_resultados_goleadores` ou `data/state/brasil_resultados_goleadores.json` | Mesmo local | TTL 15s | `load_brasil_resultados_goleadores()`, `save_brasil_resultado_goleadores()` |
| **Módulo Brasil (clássicos)** | Supabase `brasil_palpites_classicos` ou `data/state/brasil_palpites_classicos.json` | Mesmo local | TTL 15s | `load_brasil_palpites_classicos()`, `save_brasil_palpite_classico()` |
| **Comentários** | Supabase `comentarios_jogo` ou `data/state/comentarios_jogo.json` | Mesmo local | — | `load_comentarios_jogo()`, `save_comentario_jogo()`, `delete_comentario_jogo()` |

### Fluxo de Pontuação

```
1. Modo Clássico:
   a. load_submissions() → lista de Prediction
   b. load_official() → Prediction oficial
   c. load_config() → ScoreConfig
   d. rank_predictions(submissions, official, config) → list[ScoreBreakdown]
   e. Resultado é efêmero (calculado sob demanda, NÃO persistido)
   
2. Modo Jogo a Jogo:
   a. load_live_predictions() → lista de LivePrediction
   b. load_matches() → lista de LiveMatch
   c. load_config() → config
   d. calculate_live_ranking(predictions, matches, config) → list[dict]
   e. sync_official_results_to_matches() → persiste pontos em LivePrediction.points
   f. Pontos são persistidos no banco (calculados no sync)

3. Ranking Combinado:
   a. Combina classic_scores + live_scores com pesos configuráveis
   b. Clássico: classic_weight * total
   c. Jogo a Jogo: live_weight * total
```

### Backups

- **Automáticos:** Via migrações (`migrate_to_parallel_modes()`, `perform_pre_cleanup_backup()`) criam snapshots em `data/backups/`
- **Manuais:** Via admin (Exportações → Baixar Backup Geral Completo) ou CLI (`tools/make_backup.py`)
- **Restauração:** Via admin (upload de JSON) ou CLI (`tools/restore_backup.py`)
- **Formato:** JSON completo com config, submissions, live_predictions, matches, events, etc.

---

## 11. SISTEMA DE PONTUAÇÃO

### Modo V2 (Padrão — Modo Clássico) — `scoring.py`

**Fase de Grupos (placares):**
| Critério | Pontos | Descrição |
|----------|--------|-----------|
| Placar exato | 5 | Palpite e oficial idênticos |
| Resultado + saldo | 3 | Acertou vencedor/empate E saldo de gols |
| Apenas resultado | 2 | Acertou só o vencedor ou empate |
| Gols de um time | 1 | Acertou gols de pelo menos um time |
| Soma de gols | 0 | Bônus cumulativo (configurável) |
| Ambas marcam | 0 | Bônus cumulativo (configurável) |
| Over 2.5 | 0 | Bônus cumulativo (configurável) |

**Mata-mata (classificação):**
| Fase | Pontos por time |
|------|----------------|
| Oitavas | 3 |
| Quartas | 5 |
| Semi | 8 |
| Final | 12 |
| Campeão | 20 |

**Critérios de desempate:**
1. Total de pontos (maior vence)
2. Acertou campeão?
3. Pontos no mata-mata
4. Nº de placares exatos
5. Pontos na fase de grupos
6. Timestamp de submissão (mais antigo vence)
7. Ordem alfabética

### Modo Jogo a Jogo — `live_scoring.py`

| Critério | Pontos (padrão) | Descrição |
|----------|-----------------|-----------|
| Placar exato | 5 | Modo isolated_max: só leva esses 5pts |
| Resultado | 3 | Vencedor/empate |
| Gols de 1 time | 1 | Acertar gols do mandante OU visitante |
| Saldo de gols | 1 | Acertar diferença |
| Modo Relâmpago (exato) | 4 | Placar exato do 2º tempo |
| Modo Relâmpago (resultado) | 2 | Resultado do 2º tempo |

### Modos Legados (ajustáveis via admin):
- **Ponderado:** Pontos variáveis por posição no grupo (1º=5, 2º=3, melhor 3º=2, etc.)
- **Uniforme:** 1 ponto por qualquer acerto

### Módulo Brasil:
- Artilheiro Brasil: 15 pts (exato) / 5 pts (top 3)
- Artilheiro Geral: 20 pts (exato) / 7 pts (top 3)
- Gol de Ouro: 10 pts
- Goleador por jogo: 4 pts por jogador
- Assistente por jogo: 2 pts por jogador
- Bônus todos os goleadores: 5 pts
- Suspensão: reserva vale metade dos pontos

---

## 12. DIFERENÇAS DESTA VERSÃO VS. VERSÃO EM PRODUÇÃO

Esta seção documenta as diferenças entre o repositório local (`C:\dev\BolaoCopaSanca`) e a versão antiga em produção (`github.com/BarujaFe1/BolaoCopa2026` — com base no contexto do código e documentação).

### O que mudou (funcionalidades novas nesta versão):

| Funcionalidade | Status na versão antiga | Status nesta versão |
|----------------|------------------------|---------------------|
| Simulador interativo de placares | ❌ (usava OCR de prints) | ✅ Simulador completo embutido |
| Modo Jogo a Jogo | ❌ | ✅ Completo, com match center |
| Módulo Brasil | ❌ | ✅ Goleadores, assistentes, artilheiros |
| Conquistas/Badges | ❌ | ✅ 8 badges automáticos |
| Ranking Combinado | ❌ | ✅ Clássico + Jogo a Jogo |
| Dual Backend (Supabase + JSON) | ❌ (só JSON local) | ✅ Supabase + fallback local |
| Temas Claro/Escuro | ❌ | ✅ 3 modos (light, dark, system) |
| Comentários em partidas | ❌ | ✅ Mural com moderação |
| Match Center | ❌ | ✅ Termômetro, simulação |
| Duelo de Palpites | ❌ | ✅ Comparação 1v1 com zoação |
| Análise de Palpites | ❌ | ✅ Estatísticas e zebras |
| Feed de Atividades | ❌ | ✅ Eventos públicos |
| Auto-refresh (relógio) | ❌ | ✅ st_autorefresh a cada 10s |
| Modo Relâmpago (2º tempo) | ❌ | ✅ Palpites do 2º tempo |
| Pódio pós-Copa com confetes | ❌ | ✅ canvas-confetti |

### Refatorações feitas:

| Item | Mudança |
|------|---------|
| `storage.py` | De puramente local para dual backend com Supabase |
| `scoring.py` | Modo V2 como padrão (era ponderado) |
| `app.py` | De ~500 linhas para 2.863 (cresceu muito) |
| Navegação | Adicionado menu agrupado, mobile nav |
| Models | Adicionados LiveMatch, LivePrediction, ActivityEvent |
| Constantes | Adicionado ELENCO_BRASIL, VENUES, JOGADORES_COPA |
| Simulador | Engine separada (simulator_engine.py) com lógica FIFA |
| Migrations | Sistema completo de migrações idempotentes |
| Testes | De nenhum para 9 arquivos de teste |

### Bugs corrigidos (em relação à versão antiga):

- OCR impreciso → substituído por simulador interativo
- Dados em arquivos soltos → centralizados em data/state/
- Sem backup automático → migrações com backup
- Sem testes → 9 suites de teste

### Bugs ainda pendentes (desta versão):

1. ArrowInvalid / PyArrow (tipos mistos)
2. Funções duplicadas em app.py
3. Dual storage split-brain
4. Config key inconsistente (goal_one_team vs one_team_goals)
5. Conversão int forçada sem validação
6. Cache global ineficiente
7. Timezone fixo em UTC-3

---

## 13. PLANO DE MIGRAÇÃO PARA PRODUÇÃO

### Checklist pré-deploy

- [ ] **Todos os dados são lidos/escritos exclusivamente no Supabase**
  - Atualmente: depende de `get_storage_backend()`. Em produção com Supabase configurado, funciona.
  - Risco: se Supabase ficar offline, fallback para JSON local. Dados podem divergir.
  - **Ação:** Remover fallback local em produção, ou implementar sync bidirecional.

- [ ] **Nenhum arquivo local é necessário para funcionamento**
  - O sistema cria `data/state/` diretórios automaticamente (via `ensure_state()`).
  - Esses diretórios precisam existir mesmo que não usados (para o seed inicial).
  - No Streamlit Cloud, o filesystem é efêmero — dados locais NÃO persistem entre restarts.
  - **Ação:** Garantir que `ensure_state()` é sempre chamado antes de qualquer operação.

- [ ] **Variáveis de ambiente configuradas no Streamlit Cloud Secrets**
  - Necessário configurar:
    ```
    SUPABASE_URL = "https://seu-projeto.supabase.co"
    SUPABASE_SERVICE_ROLE_KEY = "sua-chave"
    ADMIN_PASSWORD = "sua-senha"
    ```
  - Opcional: `APIFOOTBALL_KEY`
  - **Verificar:** Secrets estão em `Settings > Secrets` no Streamlit Cloud.

- [ ] **Bugs críticos corrigidos**
  - Bug #1 (ArrowInvalid) — **CRÍTICO** — precisa ser corrigido antes do deploy
  - Bug #3 (funções duplicadas) — causa ineficiência mas não quebra funcionalmente
  - Bug #4 (config key inconsistente) — pode afetar pontuação

- [ ] **Dados perdidos recuperados ou reimportados**
  - Verificar se os dados atuais no Supabase estão completos
  - Executar backup via admin (Exportações → Baixar Backup Geral)
  - Verificar que `sync_classic_to_live_predictions()` sincronizou dados clássicos para jogo a jogo

### Passos para substituir o app atual

```
1. Fazer backup completo do estado atual (admin → Exportações)
2. Corrigir bugs críticos (ArrowInvalid, etc.)
3. Commit e push para o repositório
4. No Streamlit Cloud:
   a. Conectar repositório
   b. Configurar Secrets (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ADMIN_PASSWORD)
   c. Verificar que runtime.txt aponta para python-3.11
   d. Deploy
5. Verificar funcionamento:
   a. Login funciona?
   b. Dados do Supabase estão sendo lidos?
   c. Ranking está correto?
   d. Admin consegue acessar?
6. Se necessário, importar backup via admin
```

---

## 14. GUIA DE DESENVOLVIMENTO LOCAL

### Pré-requisitos

- Python 3.11+
- Git
- Windows (start.bat) ou Linux/Mac

### Configuração

```bash
# 1. Clonar
git clone <repo>
cd C:\dev\BolaoCopaSanca

# 2. Criar ambiente virtual
python -m venv .venv

# 3. Ativar (Windows)
.venv\Scripts\activate

# 4. Instalar dependências
pip install -r requirements.txt

# 5. Configurar variáveis
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/Mac
# Editar .env com suas credenciais

copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# Editar secrets.toml com credenciais do Supabase

# 6. Executar
start.bat                     # Windows
# streamlit run app.py        # Linux/Mac
```

### Acessar

- App: http://localhost:8501
- Login admin: senha em desenvolvimento = `"brasilhexa"`

### Testes

```bash
pytest tests/ -v
```

Para executar um teste específico:
```bash
pytest tests/test_bolao.py -v
pytest tests/test_live_mode.py::test_is_match_open_for_prediction -v
```

### Notas Importantes

- **Não commitar** `.env`, `.streamlit/secrets.toml`, `data/state/*.json`
- O `.gitignore` já protege esses arquivos
- Em desenvolvimento, o sistema usa **arquivos JSON locais** em `data/state/`
- Para testar com Supabase, configure as credenciais em `.streamlit/secrets.toml`
- O cache do Streamlit pode mascarar bugs — use `st.cache_data.clear()` se necessário

---

## 15. CONTEXTO DE NEGÓCIO

### O Bolão da Cabine do Glória

É um bolão (bolão de apostas) entre amigos do bairro **Cabine do Glória** em **São Carlos (SP)**. Cada participante:

1. **Modo Clássico:** Antes da Copa começar, faz UMA cartela completa (placares dos 72 jogos de grupos, classificação dos 12 grupos, 8 melhores terceiros, chaveamento completo do mata-mata e campeão).
2. **Modo Jogo a Jogo:** Para cada partida, pode palpitar o placar até 10 minutos antes do jogo. Pode editar quantas vezes quiser antes do fechamento.
3. **Ranking:** Dois rankings independentes + um combinado. O ranking clássico é calculado após resultados oficiais. O jogo a jogo é atualizado em tempo real.

### Sistema de Pontos

- **Modo Clássico (V2):** Placar exato (5pts), resultado+saldo (3pts), resultado (2pts), gol de time (1pt). Mata-mata: classificar times certos em cada fase (oitavas 3pts, quartas 5pts, semi 8pts, final 12pts, campeão 20pts). Bônus cumulativos: soma, ambas marcam, over 2.5 (0pts por padrão, configurável).
- **Modo Jogo a Jogo:** Placar exato (5pts, isolado), resultado (3pts), gol de 1 time (1pt), saldo (1pt).
- **Módulo Brasil:** Artilheiro do Brasil (15pts), Artilheiro geral (20pts), Gol de Ouro (10pts). Goleador por jogo (4pts), Assistente (2pts), Bônus todos (5pts).
- **Badges:** 8 badges por achievements (sequência, zebras, exatos, GOAT, etc.)

### Participantes Ativos

Baruja, Fantato, Henrique (O Terrível), Murilov, Lucão, Mantovas, Jonaldo o Fenômeno, Nikolas

### Copa do Mundo 2026 — Formato

- **Sede:** EUA, Canadá, México (48 seleções)
- **Fase de grupos:** 12 grupos (A-L) de 4 times cada → 72 partidas
- **Mata-mata:** Fase de 32 → Oitavas → Quartas → Semi → Final
- **Formato inovador:** Top 2 de cada grupo + 8 melhores terceiros avançam para fase de 32
- **Data:** Início em 11 de junho de 2026

### Fase Atual (junho 2026)

A Copa já começou. Jogos da fase de grupos estão em andamento. Participantes já enviaram palpites clássicos e estão palpitan do no jogo a jogo diariamente.

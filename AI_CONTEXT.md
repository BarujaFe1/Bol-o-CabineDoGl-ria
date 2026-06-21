# Bolão Copa Sanca — Contexto Completo para IA

> **Data da última auditoria:** 2026-06-21
> **App:** https://bolaodogloria.streamlit.app
> **Repos:** `BarujaFe1/BolaoCopa2026` (origin) · `BarujaFe1/Bol-o-CabineDoGl-ria` (old-origin, deploy)
> **Branch ativo:** `refactor/uniformizacao-jogo-a-jogo`
> **Python:** Local 3.12.10 · Cloud 3.14.6 (forçado, bug do Streamlit)
> **app.py:** ~2886 linhas · **src/bolao/:** 29 módulos · **Banco:** Supabase PostgreSQL + JSON fallback

---

## 1. VISÃO GERAL

**Bolão da Cabine do Glória** — Sistema web de bolão (apostas esportivas) para a Copa do Mundo 2026. Criado por **BarujaFe** para ~10 amigos de São Carlos/SP.

**Stack:** Streamlit 1.58.0 · Python 3.12+ · Supabase 2.30.1 · Tesseract OCR · Pandas 3.0.3

### Funcionalidades principais
- Simulador interativo de grupos (placar → classificação → melhores terceiros → bracket → campeão)
- Palpites **Modo Clássico** (cartela única pré-Copa com 72 jogos de grupos + mata-mata completo)
- Palpites **Modo Jogo a Jogo** (por partida, editável até 10min antes)
- **Ranking** com 6 abas: Jogo a Jogo, Clássico, Combinado, Pódio, Estatísticas (radar), Evolução
- **Match Center** (termômetro de palpites, simulação de impacto)
- **Módulo Brasil** (goleadores/assistentes por jogo, artilheiro Brasil/geral, gol de ouro)
- **8 badges** automáticos (Sequência Quente, Caçador de Zebras, Rei dos Exatos, GOAT, etc.)
- **OCR** de prints do simulador GE (legado, apenas grupos A-F)
- **Parser** de texto colado do GE (mata-mata)
- **Tema** claro/escuro/sistema · **Compartilhamento** WhatsApp · **Comentários** em partidas
- Painel **admin** (13 páginas): Dashboard, Participantes, Jogos, Resultados, Ranking, Exportações, Config, Auditoria, etc.

### 13 páginas públicas
Início, Jogos de Hoje, 🇧🇷 Jogos do Brasil, Palpite Clássico, Minha Cartela, Ranking, Central do Bolão, Palpites do Grupo, Análise dos Palpites, Duelo de Palpites, Match Center, Regras, Artilheiro

### 13 páginas admin
Dashboard, Participantes, Palpites Jogo a Jogo, Editar Palpite Clássico, Jogos e Agenda, Resultados Oficiais, Ranking, Exportações, Artilheiro, Configurações, Auditoria, Seleção Brasileira, Ajuda

---

## 2. ARQUITETURA — app.py

**Total:** 2886 linhas, 25 funções (23 globais + 2 aninhadas), 41 chamadas `st.rerun()`, 6 chamadas `st.cache_data.clear()`

### Funções globais em app.py (com linha)

| Linha | Função | Propósito |
|-------|--------|-----------|
| 108 | `get_score_config()` | Cria ScoreConfig do config carregado |
| 118 | `apply_review_form(prefix, pred)` | Form de revisão de palpite |
| 180 | `public_home()` | Página inicial (hero, banner, feed, jogos, zebra do dia) |
| 623 | `public_submission()` | Fluxo de palpite clássico (simulador, artilheiros, revisão) |
| 979 | `public_ranking()` | Wrapper que chama `render_rankings_tabs()` |
| 985 | `admin_dashboard()` | KPIs, demo data, reset |
| 1095 | `admin_participants()` | CRUD participantes, palpites clássicos, arquivamento |
| 1372 | `make_prediction_from_text(name, text)` | Parser de texto para palpite |
| 1379 | `admin_official_results()` | Simulador oficial, texto, API sync |
| 1550 | `admin_ranking()` | Wrapper ranking admin |
| 1557 | `admin_exports()` | CSV/JSON/HTML/Discord, backup, import/export |
| 1783 | `admin_artilheiro_results()` | Admin artilheiro do dia/rodada |
| 1910 | `admin_settings()` | Config, reset, limpeza de dados |
| 2220 | `admin_edit_classic_page()` | Admin editando palpite de participante |
| 2266 | `admin_help()` | Página de ajuda |
| 2290 | `admin_auditoria()` | Eventos, comentários |
| 2338 | `render_login_screen()` | Tela de login público |
| 2424 | `on_public_nav_change()` | Callback navegação pública |
| 2429 | `on_admin_nav_change()` | Callback navegação admin |
| 2434 | `on_mobile_nav_change()` | Callback navegação mobile |
| 2440 | `render_global_countdown()` | Relógio e countdown na sidebar |
| 2553 | `main()` | Entry point: init, sidebar, router |

### Todas as chaves `st.session_state` (26 chaves únicas)

| Chave | Tipo | Onde é usada |
|-------|------|-------------|
| `nav_page` | str | Router principal |
| `admin_mode` | bool | Alterna menu admin/público |
| `admin_authenticated` | bool | Autenticação admin |
| `live_user_name` | str | Nome do usuário logado |
| `live_user_key` | str | Chave normalizada |
| `live_confirmation_code` | str | Código do palpite clássico |
| `public_sim_name` | str | Nome no simulador público |
| `sim_prediction` | Prediction | Palpite sendo editado |
| `sim_public` | bool | Modo público do simulador |
| `edit_mode` | str | new/edit/view |
| `show_delete_confirm` | bool | Confirmação de exclusão |
| `match_center_selected_match_id` | str | Match center |
| `last_submitted_prediction` | Prediction | Último palpite enviado |
| `selected_artilheiro_brasil` | str | Artilheiro Brasil selecionado |
| `selected_artilheiro_geral` | str | Artilheiro geral selecionado |
| `selected_gol_de_ouro` | str | Gol de ouro selecionado |
| `last_checked_participant_name` | str | Último nome verificado |
| `official_save_msg` | str | Mensagem de save oficial |
| `official_draft` | Prediction | Rascunho oficial |
| `admin_editing_classic_prediction` | Prediction | Admin editando |
| `public_nav_radio_key` | str | Radio navegação pública |
| `admin_nav_radio_key` | str | Radio navegação admin |
| `mobile_nav_selectbox_key` | str | Selectbox navegação mobile |
| `active_navigation_group_selectbox` | str | Grupo ativo navegação |
| `last_nav_page` | str | Última página antes de mudar grupo |
| `admin_login_attempts` | int | Rate limiting admin (max 5) |

### Todas as chamadas `st.cache_data.clear()` (6 locais)
- `admin_participants`: linhas 1132, 1175, 1272, 1288, 1365
- `admin_edit_classic_page`: linha 2262

---

## 3. MÓDULOS `src/bolao/` — CATÁLOGO COMPLETO

### constants.py (284 linhas)
- Dados puros: APP_NAME, GROUPS (A-L), PHASES, TEAM_ALIASES (~200 aliases para 48 times), ALL_TEAMS, ACTIVE_PARTICIPANT_NAMES, ELENCO_BRASIL_2026 (26 jogadores), VENUES_COPA_2026 (16 estádios), JOGADORES_COPA_2026, DEFAULT_V2_RULES, DEFAULT_WEIGHTED_RULES, DEFAULT_UNIFORM_RULES
- ⚠️ "Noruega" aparece 2x em JOGADORES_COPA_2026 (linhas 233 e 276)

### models.py (356 linhas) — 7 dataclasses
- `ParseIssue`(18) · `Match`(25) · `Prediction`(36) com `to_dict()`/`from_dict()` · `ScoreBreakdown`(92) com `to_row()` · `LiveMatch`(123) com `to_dict()`/`from_dict()` · `LivePrediction`(203) com `to_dict()`/`from_dict()` · `ActivityEvent`(321) com `to_dict()`/`from_dict()`
- ⚠️ Todas têm `__module__ = "src.bolao.models"` para pickle (corrigido 2026-06-21)
- ⚠️ Alias de módulo registrados no topo (linhas 4-10) para evitar `PicklingError`

### storage.py (2455 linhas) — O MAIOR MÓDULO
- **62+ funções** de persistência híbrida Supabase + JSON local
- **7 funções com `@st.cache_data(ttl=15, show_spinner=False)`**: load_config, load_submissions, load_official, load_app_data_cached, load_matches, load_live_predictions
- **1 função com `@st.cache_resource`**: _get_supabase_client
- Alias de módulo registrados no topo (linhas 3-9)
- `_sync_local_to_supabase()` roda UMA vez no startup (flag `_sync_done`)

#### Funções principais em storage.py
| Função | Linha | Cache |
|--------|-------|-------|
| `_resolve_data_dir()` | 25 | - |
| `get_storage_backend()` | 64 | - |
| `_get_supabase_client()` | 88 | `@st.cache_resource` |
| `_ensure_supabase_tables()` | 126 | - |
| `_sync_local_to_supabase()` | 411 | - |
| `ensure_state()` | 508 | - |
| `default_config()` | 676 | - |
| `load_config()` | 725 | `@st.cache_data` |
| `save_config()` | 762 | limpa cache |
| `load_submissions()` | 777 | `@st.cache_data` |
| `save_submission()` | 861 | limpa cache |
| `delete_submission()` | 902 | limpa cache |
| `load_official()` | 942 | `@st.cache_data` |
| `save_official()` | 1006 | limpa cache |
| `export_all_state()` | 1041 | - |
| `import_all_state()` | 1066 | limpa cache |
| `reset_state()` | 1314 | limpa cache |
| `load_demo_state()` | 1344 | limpa cache |
| `load_app_data_cached()` | 1393 | `@st.cache_data` |
| `load_matches()` | 1418 | `@st.cache_data` |
| `save_matches()` | 1473 | limpa cache |
| `load_live_predictions()` | 1500 | `@st.cache_data` |
| `save_live_predictions()` | 1578 | limpa cache |
| `upsert_live_prediction()` | 1621 | - |
| `load_registered_participants()` | 1718 | - |
| `register_participant()` | 1825 | - |
| `sync_official_results_to_matches()` | 1844 | - |
| `archive_participant()` | 1907 | - |
| `restore_participant()` | 1947 | - |
| `recalcular_pontos_modulo_brasil()` | 2257 | - |

### scoring.py (473 linhas) — Motor de pontuação (Modo Clássico)
- `ScoreConfig`(21) `@dataclass` · `_eq()`(37) · `get_phase_teams()`(41) · `score_prediction()`(51) · `rank_predictions()`(418) · `_rank_predictions_cached()`(442) `@st.cache_data` · `ranking_rows()`(472)

### live_scoring.py (431 linhas) — Motor de pontuação (Modo Jogo a Jogo)
- `calculate_live_prediction_points()`(6) · `calculate_live_ranking()`(118) · `calcular_pontos_goleadores()`(249) · `calcular_pontos_artilheiro_classico()`(324) · `calculate_artilheiro_dia_points()`(351) · `calculate_artilheiro_rodada_points()`(393)

### utils.py (223 linhas)
- `render_countdown()`(13) · `now_iso()`(45) · `strip_accents()`(49) · `norm_team()`(61) · `normalize_participant_key()`(114) · `format_display_name()`(126) · `write_json()`(82) atomic · `read_json()`(76) · `canonical_team()`(155) · `is_debug_mode()`(178) · `avatar_url()`(205) DiceBear

### validation.py (42 linhas)
- `validate_prediction()`(8) · `has_blocking_errors()`(41)

### navigation.py (18 linhas)
- `navigate_to(page, admin_mode)`(5) — seta `st.session_state["nav_page"]` e chama `st.rerun()`

### events.py (95 linhas)
- `append_event()`(12) · `load_events()`(49) `@st.cache_data(ttl=15)`

### exporters.py (564 linhas)
- `ranking_to_dataframe()`(14) · `ranking_csv()`(37) · `ranking_json()`(42) · `discord_ranking()`(46) · `podium_html()`(57) · `details_dataframe()`(311) · `live_podium_html()`(315)

### achievements.py (373 linhas)
- `Badge`(10) · `calculate_achievements()`(23) — 8 badges

### simulator_engine.py (508 linhas)
- `calculate_group_standings()`(34) · `get_best_third_placed_teams()`(199) · `assign_3rd_place_slots()`(225) · `build_initial_bracket_slots()`(267) · `propagate_winner()`(311) · `normalize_slots()`(371) · `validate_prediction_complete()`(404) · `serialize_slots_to_prediction()`(431) · `deserialize_prediction_to_slots()`(466)

### simulator_models.py (71 linhas)
- `Team`(6) · `GroupMatch`(13) · `GroupStanding`(40)

### social.py (189 linhas)
- 9 funções de build de texto: `build_classic_share_text`, `build_live_match_share_text`, `build_daily_games_text`, `build_ranking_share_text`, `build_round_summary_text`, `build_duel_share_text`, `build_my_card_share_text`, `build_taunt_text`

### styles.py (834 linhas) — CSS
- `get_theme_css(theme_mode)`(3) · `inject_css()`(830)

### worldcup_2026_data.py (212 linhas)
- `TEAMS`(8) 48 times · `GROUPS_TEAMS`(61) 12 grupos · `GROUP_MATCHES`(73) 72 partidas · `BRACKET_SLOTS`(148) 63 slots

### api_service.py (205 linhas)
- `APIResponse`(14) · `APIFootballService`(22) `fetch_world_cup_2026()`(48) · `sync_matches_scores_with_api()`(110)

### migrations.py (619 linhas)
- 9 funções de migração incluindo `sync_classic_to_live_predictions()`, `cleanup_active_participants()`, `run_participant_cleanup_migration()`

### ocr_groups.py (389 linhas)
- OCR para prints do simulador GE. Processa apenas grupos A-F (6 de 12).

### parser_ge.py (200 linhas)
- Parse de texto colado do GE. `parse_ge_knockout_text()`, `knockout_to_rows()`, `rows_to_knockout()`

### ui_artilheiro.py (321 linhas)
- `render_page_artilheiro()` — 3 abas: Artilheiro do Dia, da Rodada, da Copa

### ui_components.py (323 linhas)
- 20+ funções: `inject_css`, `render_theme_selector`, `hero`, `kpi_grid`, `step_cards`, `podium`, `badges`, `groups_dataframe`, `render_responsive_table`, `render_player_single_select`, etc.

### score_updater.py (162 linhas) — fora de src/bolao/
- `run_score_sync()` — sincroniza placares via football-data.org API

### src/bolao/__init__.py (1 linha) e src/__init__.py (1 linha)
- Pacotes vazios

---

## 4. BANCO DE DADOS — SUPABASE (11+ tabelas)

### `bolao_config`
| Coluna | Tipo | Notas |
|--------|------|-------|
| key | TEXT PK | 'main' |
| value | JSONB | Config completa |
| updated_at | TIMESTAMPTZ | NOW() |
**RLS:** ❌ Nenhum · **Operações:** SELECT/INSERT/UPSERT

### `bolao_submissions`
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | TEXT PK | submission_id |
| participant | TEXT NOT NULL | |
| groups | JSONB NOT NULL | |
| best_thirds | JSONB | |
| knockout | JSONB | |
| champion | TEXT | |
| status | TEXT | DEFAULT 'confirmado' |
| active | BOOLEAN | DEFAULT TRUE |
**RLS:** ❌ Nenhum · **Índices:** idx_submissions_participant, idx_submissions_active
**Operações:** SELECT/INSERT (via save_submission), UPDATE (via soft delete), DELETE (via delete_submission)

### `bolao_official`
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | TEXT PK | DEFAULT 'official' |
| groups | JSONB NOT NULL | |
| knockout | JSONB | |
| champion | TEXT | |
**RLS:** ❌ Nenhum · **Operações:** SELECT/INSERT/UPSERT

### `bolao_matches`
| Coluna | Tipo | Notas |
|--------|------|-------|
| match_id | TEXT PK | |
| phase | TEXT NOT NULL | grupos, fase_32, oitavas... |
| group | TEXT | A-L |
| round_label | TEXT | |
| home_team | TEXT NOT NULL | |
| away_team | TEXT NOT NULL | |
| starts_at | TEXT NOT NULL | ISO timestamp |
| lock_at | TEXT | Fechamento dos palpites |
| status | TEXT | scheduled/locked/live/finished/result_approved |
| official_home_goals | INT | |
| official_away_goals | INT | |
| winner | TEXT | 'draw' ou time vencedor |
| api_match_id | INT UNIQUE | Para sync football-data.org |
| modo_relampago_ativo | BOOLEAN | |
**RLS:** ✅ com política `anon_read_matches` (SELECT público)
**Índices:** idx_bolao_matches_starts_at, idx_bolao_matches_status
**Operações:** SELECT/INSERT/UPDATE

### `bolao_live_predictions`
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | TEXT PK | participant_key_match_id |
| participant_name | TEXT NOT NULL | |
| participant_key | TEXT NOT NULL | |
| match_id | TEXT NOT NULL | |
| predicted_home_goals | INT NOT NULL | |
| predicted_away_goals | INT NOT NULL | |
| points | INT | |
| scoring_breakdown | JSONB | |
| is_locked | BOOLEAN | |
| is_late | BOOLEAN | |
| active | BOOLEAN | Soft delete |
**RLS:** ✅ ativado (sem política — protegido por service_role_key)
**Constraint:** UNIQUE(participant_key, match_id)
**Índices:** idx_live_preds_participant_key, idx_live_preds_match_id, idx_live_preds_submitted_at
**Operações:** SELECT/INSERT/UPSERT/DELETE (soft)

### `bolao_events`
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | TEXT PK | UUID 8 chars |
| kind | TEXT NOT NULL | |
| message | TEXT NOT NULL | |
| visibility | TEXT | public/admin |
**RLS:** ✅ com política `anon_read_events` (SELECT só public)
**Índices:** idx_bolao_events_timestamp, idx_bolao_events_visibility
**Operações:** INSERT/SELECT

### `brasil_palpites_goleadores`
| Coluna | Tipo | Notas |
|--------|------|-------|
| id | UUID PK | gen_random_uuid() |
| participante_nome | TEXT NOT NULL | |
| jogo_id | TEXT NOT NULL | |
| goleadores | JSONB | |
| assistentes | JSONB | |
| pontos_ganhos | INT | |
**RLS:** ✅ ativado (sem política)
**Constraint:** UNIQUE(participante_nome, jogo_id)

### `brasil_resultados_goleadores`
| Coluna | Tipo | Notas |
|--------|------|-------|
| jogo_id | TEXT PK | |
| goleadores_reais | JSONB | |
| assistentes_reais | JSONB | |
| encerrado | BOOLEAN | |
**RLS:** ✅ ativado

### `brasil_palpites_classicos`
| Coluna | Tipo | Notas |
|--------|------|-------|
| participante_nome | TEXT PK | |
| artilheiro_brasil_copa | TEXT | |
| artilheiro_geral_copa | TEXT | |
| gol_de_ouro | TEXT | |
**RLS:** ✅ ativado

### `ranking_snapshots` e `comentarios_jogo`
- `ranking_snapshots`: PK composta (rodada, participante_nome)
- `comentarios_jogo`: CHECK text <= 140 chars, soft delete via `deletado` flag
**RLS:** ✅ ativado em ambas

### Resumo RLS
- **SEM RLS:** bolao_config, bolao_submissions, bolao_official
- **RLS ativado (sem políticas explicitas — protegido apenas via service_role_key):** bolao_live_predictions, brasil_*, ranking_snapshots, comentarios_jogo
- **RLS com políticas SELECT anônimas:** bolao_matches (tudo), bolao_events (só public)

---

## 5. SISTEMA DE PONTUAÇÃO

### Modo V2 (padrão — Clássico, em scoring.py)

**Fase de Grupos:**
| Critério | Pontos |
|----------|--------|
| Placar exato | 5 |
| Resultado + saldo | 3 |
| Apenas resultado | 2 |
| Gols de um time | 1 |

**Mata-mata (classificar times certos):**
| Fase | Pontos |
|------|--------|
| Oitavas | 3 |
| Quartas | 5 |
| Semi | 8 |
| Final | 12 |
| Campeão | 20 |

**Critérios de desempate (ordem):**
1. Total de pontos
2. Acertou campeão?
3. Pontos no mata-mata
4. Nº de placares exatos
5. Pontos na fase de grupos
6. Timestamp de submissão (mais antigo vence)
7. Ordem alfabética

### Modo Jogo a Jogo (live_scoring.py)
| Critério | Pontos |
|----------|--------|
| Placar exato | 5 (isolado, se `isolated_max`) |
| Resultado | 3 |
| Gols de 1 time | 1 |
| Saldo de gols | 1 |
| Relâmpago exato | 4 |
| Relâmpago resultado | 2 |

### Módulo Brasil
| Item | Pontos |
|------|--------|
| Artilheiro Brasil (exato) | 15 |
| Artilheiro Brasil (top 3) | 5 |
| Artilheiro Geral (exato) | 20 |
| Artilheiro Geral (top 3) | 7 |
| Gol de Ouro | 10 |
| Goleador por jogo | 4 |
| Assistente por jogo | 2 |
| Bônus todos goleadores | 5 |
| Suspensão (reserva) | Metade dos pontos |

### Config keys da pontuação (⚠️ inconsistências conhecidas)
- `live_scoring.py:27` lê `"one_team_goals"` (corrigido) — `storage.py:479` salva como `"one_team_goals"`
- `live_scoring.py:39` lê `config.get("live_scoring", {}).get("exact_score_mode")` (corrigido)
- `config.get("live_lock_minutes_before_match", 10)` em `storage.py:1477` — sem validação try/except

---

## 6. BUGS CONHECIDOS — STATUS ATUAL

### 🔴 Críticos (0 pendentes — 1 depende de deploy)

| ID | Status | Bug | Arquivo | Fix |
|----|--------|-----|---------|-----|
| #1 | ⏳ Deploy | Módulos não encontrados (main branch desatualizada) | GitHub main branch | `git push old-origin refactor/uniformizacao-jogo-a-jogo:main --force` |
| #2 | ✅ Corrigido | LiveMatch não picklizable | models.py | `__module__` adicionado a todas dataclasses |
| #3 | ✅ Local OK | `UnboundLocalError: st` | ui_admin_matches.py | `import streamlit as st` já existe localmente |
| #4 | ✅ Corrigido | ArrowInvalid tipos mistos "Pontos" | ui_cartela.py:362,367 | `str()` + verificação segura |

### 🟡 Médios (4 corrigidos, 6 conhecidos não corrigidos)

**Corrigidos:**
| ID | Bug | Arquivo |
|----|-----|---------|
| #5 | Config key goal_one_team vs one_team_goals | live_scoring.py:27 |
| #6 | Config key exact_score_mode aninhada vs plana | live_scoring.py:39 |
| #8 | st.rerun() dentro de loop | ui_simulator.py:239 |
| #9 | None subscriptable [0] | ui_simulator.py:152 |
| #10 | Pontos > 0 com None | ui_cartela.py:367 |
| #20 | Pontos Ganhos tipo misto | ui_social_pages.py:204 |

**Não corrigidos (conhecidos da AUDITORIA.md, pendentes):**
| ID | Bug | Impacto |
|----|-----|---------|
| P-001 | Split-brain Supabase/JSON | Perda de dados no restart |
| P-008 | ArrowInvalid coluna "Pontos" (AUDITORIA) | Crash ranking |
| P-012 | st.rerun() em for loop (ui_live_matches.py) | Loop potencial |
| P-013 | KeyError em dicionários aninhados API | Crash live scoring |
| P-014 | IndexError array vazio API | Crash |
| P-016 | ZeroDivisionError percentuais | Crash estatísticas |
| P-017 | Ordenação lexicográfica ranking | Ordem errada |

### 🟢 Baixos (3 corrigidos, vários pendentes)

**Corrigidos:**
| ID | Bug | Arquivo |
|----|-----|---------|
| #11 | next() sem default | simulator_engine.py:218-219, ui_simulator.py:99 |
| #12 | Divisão por zero (já existia else) | simulator_engine.py:86-89 |

**Pendentes relevantes:**
- Timezone fixo UTC-3 (não usa `starts_at_timezone`)
- `int()` forçado sem try/except em models.py
- CSS f-string mal escapado em styles.py
- `canonical_team` pode retornar None
- Avatar expõe nomes via DiceBear URL
- Senha admin hardcoded "brasilhexa"

---

## 7. HISTÓRICO DE CORREÇÕES (2026-06-21)

| Arquivo | Mudanças |
|---------|----------|
| `src/bolao/models.py` | Adicionado `__module__ = "src.bolao.models"` a todas as 7 dataclasses para pickling |
| `src/bolao/ui_cartela.py` | `"Pontos"` convertido p/ string + verificação segura em badge_points |
| `src/bolao/live_scoring.py` | `"goal_one_team"` → `"one_team_goals"`; `exact_score_mode` acessado via `config.get("live_scoring", {})` |
| `src/bolao/ui_simulator.py` | `break` após `st.rerun()` em loop; default `[None, None]` em `.get()`; default `"?"` em `next()` |
| `src/bolao/ui_social_pages.py` | `"Pontos Ganhos"` convertido p/ string com fallback `"—"` |
| `src/bolao/simulator_engine.py` | Default `"Z"` em `next()` para evitar StopIteration |

---

## 8. SEGURANÇA — PROBLEMAS CONHECIDOS

### 🔴 Críticos
1. `SUPABASE_SERVICE_ROLE_KEY` é usada como cliente ÚNICO — **bypassa RLS** completamente
2. Service role key transmitida em headers HTTP REST
3. Tabelas `bolao_config`, `bolao_submissions`, `bolao_official` **sem RLS**

### 🟠 Altos
1. Senha admin hardcoded "brasilhexa" como fallback (`app.py:2772`)
2. Rate limiting: máximo 5 tentativas (resetável via session_state)
3. Nomes de participantes expostos em query params via DiceBear

### 🟡 Médios
1. Senha admin em texto plano (sem hash)
2. Sessão admin verificada apenas por flag booleana

---

## 9. GIT — TWO REMOTES

```powershell
origin      → https://github.com/BarujaFe1/BolaoCopa2026.git
old-origin  → https://github.com/BarujaFe1/Bol-o-CabineDoGl-ria.git
```

- **origin**: Repositório de trabalho
- **old-origin**: Conectado ao Streamlit Cloud (deploy)

### Deploy no Cloud
```powershell
git push old-origin refactor/uniformizacao-jogo-a-jogo:main --force
```

### Arquivos force-tracked (.gitignore porém essenciais)
```
data/state/*.json  →  git add -f
```

---

## 10. STREAMLIT CLOUD — PROBLEMAS

1. **Python 3.14 forçado** — `runtime.txt` é ignorado. Bug da plataforma (issue #15326)
2. **Filesystem efêmero** — `data/state/*` NÃO persiste entre restarts
3. **Ciclo de deploy:** Push → Cloud detecta (~3min) → "Pulling code changes" → "Updated app!" (~30s)
4. **Logs:** https://share.streamlit.io → app → Manage → Logs

---

## 11. ARQUIVOS DE ESTADO (data/state/)

| Arquivo | Conteúdo |
|---------|----------|
| `config.json` | Configuração do bolão (modo, pesos, flags) |
| `matches_2026.json` | 72+ partidas da Copa |
| `live_predictions.json` | Palpites jogo-a-jogo |
| `official_result.json` | Resultado oficial (modo clássico) |
| `events.json` | Feed de atividades |
| `registered_participants.json` | Participantes registrados |
| `archived_participants.json` | Participantes arquivados |
| `migrations.json` | Estado das migrações |
| `submissions/` | Palpites clássicos (1 JSON por participante) |
| `brasil_palpites_goleadores.json` | Palpites goleadores BR |
| `brasil_resultados_goleadores.json` | Resultados goleadores BR |
| `brasil_palpites_classicos.json` | Artilheiros clássicos BR |
| `ranking_snapshots.json` | Snapshots de ranking |
| `comentarios_jogo.json` | Comentários em partidas |
| `artilheiro_palpites_dia.json` | Palpites artilheiro do dia |
| `artilheiro_palpites_rodada.json` | Palpites artilheiro da rodada |
| `artilheiro_resultado_dia.json` | Resultados artilheiro do dia |
| `artilheiro_resultado_rodada.json` | Resultados artilheiro da rodada |

---

## 12. TESTES

```powershell
python -m pytest tests/ -v
python -m pytest tests/ -x --tb=short   # Parar no primeiro erro
```

| Arquivo | Testes | Escopo |
|---------|--------|--------|
| `test_bolao.py` | ~15 | Funções básicas |
| `test_bolao_v2.py` | ~8 | Countdown, avatar |
| `test_live_mode.py` | ~20 | Palpites jogo-a-jogo |
| `test_comprehensive.py` | ~20 | Squad lists, goleadores |
| `test_parser_scoring.py` | ~10 | Parser GE, scoring |
| `test_simulator.py` | ~15 | Simulador, grupos |
| `test_ui_robustness.py` | ~10 | UI edge cases |
| `test_admin_overrides.py` | ~5 | Admin |
| `test_backup_restore.py` | ~2 | Backup |
| `test_text_cleanup.py` | ~2 | Limpeza |

---

## 13. PARTICIPANTES ATIVOS

| Nome | Key |
|------|-----|
| Baruja | `baruja` |
| Fantato | `fantato` |
| Henrique (O Terrível) | `henrique-90727079dcad` |
| Murilov | `murilov` |
| Lucão | `lucao-3fcb4388301a` |
| Mantovas | `mantovas` |
| Jonaldo | `jonaldo` |
| Nikolas | `nikolas` |

---

## 14. REGRAS DE OURO (NUNCA ESQUECER)

1. `LiveMatch` usa `starts_at`, NUNCA `match_date`
2. `LivePrediction.scoring_breakdown` é `list`, NUNCA `dict`
3. Variáveis usadas fora de `if _HAS_PLOTLY:` precisam ser inicializadas ANTES
4. `except Exception: pass` em chamadas Supabase é INTENCIONAL — não remover
5. `data/state/*.json` precisa `git add -f`
6. Dois remotes: `origin` (trabalho) e `old-origin` (deploy Cloud)
7. `normalize_participant_key()` centraliza identificação
8. Não adicionar comentários no código a menos que explicitamente pedido
9. NUNCA refatorar código funcionando — só corrigir o que está quebrado
10. Preservar lógica de pontuação existente mesmo que pareça estranha

---

## 15. PARTICIPANTES E SENHA ADMIN

**Login público:** Qualquer nome (sem senha)
**Login admin:** Senha única (verifica nesta ordem):
1. `st.secrets["ADMIN_PASSWORD"]` (produção)
2. `"brasilhexa"` (fallback desenvolvimento, hardcoded em app.py:2772)

---

## 16. COMANDOS ÚTEIS

```powershell
# Rodar app
streamlit run app.py

# Testes
python -m pytest tests/ -v
python -m pytest tests/ -x --tb=short

# Verificar import
python -c "from src.bolao.ui_ranking import render_rankings_tabs; print('OK')"

# Deploy
git push old-origin refactor/uniformizacao-jogo-a-jogo:main --force

# Backup
python tools/make_backup.py
```

---

## 17. ARQUIVOS CRÍTICOS

| Arquivo | Tamanho | Função |
|---------|---------|--------|
| `app.py` | 2886 linhas | Entry point |
| `src/bolao/storage.py` | 2455 linhas | Persistência híbrida |
| `src/bolao/ui_live_matches.py` | 1699 linhas | UI jogos ao vivo (MAIOR UI) |
| `src/bolao/ui_ranking.py` | 1257 linhas | Ranking (6 abas) |
| `src/bolao/ui_simulator.py` | 715 linhas | Simulador |
| `src/bolao/ui_admin_matches.py` | 692 linhas | Admin jogos |
| `src/bolao/ui_cartela.py` | 579 linhas | Minha Cartela |
| `src/bolao/simulator_engine.py` | 508 linhas | Motor simulador |
| `src/bolao/scoring.py` | 473 linhas | Pontuação clássico |
| `src/bolao/live_scoring.py` | 431 linhas | Pontuação jogo-a-jogo |
| `src/bolao/models.py` | 356 linhas | Modelos de dados |
| `src/bolao/migrations.py` | 319 linhas | Migrações |

---

## 18. ARQUITETURA — PROBLEMAS ESTRUTURAIS (PENDENTES)

### P-001: Split-brain Supabase/JSON
Escritas vão primariamente para JSON local. Sync para Supabase só ocorre no startup. Dados no Streamlit Cloud (filesystem efêmero) são perdidos no restart.
**Solução:** Implementar sync bidirecional ou remover backend local em produção.

### P-024: app.py god file (2886 linhas)
Mistura roteamento, autenticação, menu, lógica de página.
**Solução:** Mover funções de página para módulos ui_* (parcialmente feito).

### P-025: Duas abstrações de banco concorrentes
`storage.py` vs acesso direto ao Supabase. Módulos usam um ou outro inconsistentemente.

### P-031: Sem cache_data nas queries Supabase
Cada rerun dispara queries completas ao Supabase. Com 10+ usuários simultâneos, pode exceder limite free tier.

---

## 19. ERROS DE LOG DO STREAMLIT CLOUD (21/06/2026)

Os logs de produção mostraram estes erros (já endereçados no código local):

| Erro | Causa | Status |
|------|-------|--------|
| `KeyError: 'src.bolao.storage'` | main branch desatualizada | ⏳ Deploy |
| `KeyError: 'src.bolao.worldcup_2026_data'` | main branch desatualizada | ⏳ Deploy |
| `KeyError: 'src.bolao.validation'` | main branch desatualizada | ⏳ Deploy |
| `KeyError: 'src.bolao.ui_admin_matches'` | main branch desatualizada | ⏳ Deploy |
| `AttributeError: 'NoneType' object has no attribute '__dict__'` | @dataclass sem module alias | ✅ models.py |
| `UnserializableReturnValueError` | LiveMatch não picklizable | ✅ models.py |
| `UnboundLocalError: st` | ui_admin_matches.py sem import | ✅ Local OK |
| `PicklingError: Can't pickle LiveMatch` | Import duplicado | ✅ models.py |
| `use_container_width` deprecation | API antiga | ⏳ Cosmético |

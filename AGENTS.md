# AGENTS.md — Bolão Copa Sanca

## Contexto do projeto

App Streamlit para bolão da Copa do Mundo 2026.

- **Entry point:** `app.py` (raiz, não `src/bolao/app.py`)
- **Branch ativa:** `refactor/uniformizacao-jogo-a-jogo`
- **Deploy Cloud:** `git push old-origin refactor/uniformizacao-jogo-a-jogo:main --force`
- **Python:** Local 3.12.10 · Cloud 3.14.6 (runtime.txt ignorado)

## Regras de ouro

1. `LiveMatch` usa `starts_at`, NUNCA `match_date`
2. `LivePrediction.scoring_breakdown` é `list`, NUNCA `dict`
3. Variáveis usadas fora de `if _HAS_PLOTLY:` precisam ser inicializadas antes
4. `except Exception: pass` em chamadas Supabase é intencional — não remover sem substituto seguro
5. `data/state/*.json` força `git add -f` (no `.gitignore`)
6. Dois remotes: `origin` (trabalho) e `old-origin` (deploy Cloud)
7. Sempre rodar `python -m pytest tests/ -x --tb=short` antes de commit

## Camada de logging

`storage.py` tem helper `_warn()` que escreve em stderr. Útil para debug de falhas Supabase sem quebrar o app.

## Arquivos críticos

| Arquivo | Função |
|---------|--------|
| `app.py` | Entry point (~2650 linhas) |
| `src/bolao/storage.py` | Persistência híbrida Supabase + JSON |
| `src/bolao/models.py` | Modelos de dados (Match, LiveMatch, Prediction, LivePrediction) |
| `src/bolao/ui_ranking.py` | Ranking (6 abas, ~1213 linhas) |
| `src/bolao/utils.py` | `normalize_participant_key()` — centraliza identificação |
| `src/bolao/live_scoring.py` | `calculate_artilheiro_dia_points()`, `calculate_artilheiro_rodada_points()` — scoring artilheiro do dia/rodada |
| `src/bolao/ui_artilheiro.py` | Página pública de palpites de artilheiro do dia/rodada/copa |
| `data/state/artilheiro_palpites_dia.json` | Palpites dos participantes — artilheiro do dia |
| `data/state/artilheiro_palpites_rodada.json` | Palpites dos participantes — artilheiro da rodada |
| `data/state/artilheiro_resultado_dia.json` | Resultados oficiais (admin) — artilheiro do dia |
| `data/state/artilheiro_resultado_rodada.json` | Resultados oficiais (admin) — artilheiro da rodada |

## Seção Admin → "Artilheiro"

Nova página admin (`admin_artilheiro_results` em `app.py`) com 3 abas:
1. **📅 Artilheiro do Dia** — cadastro de resultado real por data
2. **📆 Artilheiro da Rodada** — cadastro de resultado real por rodada
3. **🏆 Scoring & Acertos** — visualização de acertos e configuração de pesos (`pts_artilheiro_dia`, `pts_artilheiro_rodada`)

Os pontos são integrados automaticamente ao `calculate_live_ranking()`.

## Comandos úteis

```powershell
streamlit run app.py
python -m pytest tests/ -v
python -m pytest tests/ -x --tb=short
python -c "from src.bolao.ui_ranking import render_rankings_tabs; print('OK')"
```

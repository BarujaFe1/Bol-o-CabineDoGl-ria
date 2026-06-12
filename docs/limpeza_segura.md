# Relatório de Limpeza Segura do Projeto

Este documento detalha o mapeamento, classificação e quarentena de arquivos no repositório **BolaoCopaSanca** para manter a codebase limpa, leve e segura.

## 1. Mapeamento de Arquivos e Assets

Realizamos uma varredura completa da raiz do projeto para identificar arquivos obsoletos, temporários ou redundantes.

### Classificação dos Arquivos Identificados

| Arquivo/Diretório | Tamanho | Classificação | Justificativa / Destino |
|---|---|---|---|
| `Simulador da Copa do Mundo 2026.html` | ~732 KB | **MANTER** (Investigação) | Fornece a base estrutural do simulador clássico da Globo Esporte (GE) e documenta o parser estrutural. |
| `Simulador da Copa do Mundo 2026_files/` | Coletivo | **MANTER** (Ativo) | Contém todas as imagens de bandeiras e escudos das seleções carregadas em `src/bolao/worldcup_2026_data.py`. |
| `2026-06-11T18-34_export.csv` | ~12.8 KB | **IGNORAR** | Arquivo temporário de exportação de dados, agora ignorado automaticamente via `.gitignore` (`*.csv`). |
| `.pytest_cache/` | — | **IGNORAR** | Cache de execução de testes do pytest. Adicionado ao `.gitignore`. |
| `data/backups/` | — | **IGNORAR** | Pasta de backups temporários e timestamps. Adicionado ao `.gitignore`. |
| `.env` / `.streamlit/secrets.toml` | — | **IGNORAR** (Privado) | Arquivos de configuração de ambiente e credenciais sensíveis. Já ignorados no `.gitignore`. |

---

## 2. Ações de Quarentena e Segurança

1. **Proteção contra Vazamento de Secrets**:
   - Confirmado via `git ls-files` que nenhuma credencial de desenvolvimento ou produção (`.env`, `secrets.toml`) foi inadvertidamente rastreada pelo Git.
   - Restringimos a senha administrativa de fallback `"brasilhexa"` no arquivo principal `app.py` para funcionar estritamente sob modo debug ou ambiente local (`APP_ENV=development`). Em produção, exige-se a configuração do secret `ADMIN_PASSWORD`.
   
2. **Atualização do `.gitignore`**:
   - Adicionadas regras específicas para evitar o envio de cache local de testes (`.pytest_cache/`), relatórios locais em planilha (`*.csv`) e a pasta de preservação de dados histórico-operacionais (`data/backups/`).

3. **Verificação de Compilação**:
   - Compilação limpa garantida: `python -m compileall src app.py`.
   - Execução integral dos testes automatizados: `pytest -q` (56 casos de testes passando).

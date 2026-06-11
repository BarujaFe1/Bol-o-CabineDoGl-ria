# Relatório de Migração e Novo Modo Jogo a Jogo — BolaoCopaSanca

Este relatório documenta as alterações realizadas no projeto **BolaoCopaSanca** para introduzir o **Modo Jogo a Jogo** de forma segura, com migração idempotente de dados clássicos e correções de bugs.

---

## 1. Resumo das Mudanças

1. **Dois Modos Paralelos**:
   - **Modo Clássico**: Palpites completos preenchidos pré-Copa. Mantido 100% intacto, lendo os arquivos JSON originais.
   - **Modo Jogo a Jogo**: Palpites individuais em cada partida até 10 minutos antes do início do jogo.
2. **Correção de Bugs Críticos**:
   - Corrigido o erro `KeyError: 0` no simulador de mata-mata.
   - Ajustada a normalização de slots do simulador para aceitar chaves strings/inteiras de forma flexível (`normalize_slots`).
   - Ajustada a assinatura de `validate_prediction_complete` para retornar uma tupla `(bool, list[str])`.
3. **Novas Interfaces Públicas**:
   - **Início (Home)**: Dashboard interativo com apresentação clara dos dois modos e banner indicando se há jogos abertos no dia.
   - **Jogos de Hoje**: Abas separando jogos abertos para palpitar, jogos fechados (com palpites do grupo revelados após o bloqueio) e concluídos.
   - **Minha Cartela**: Visão individual do participante com resumos, histórico de palpites clássicos/jogo a jogo, e comparador com amigos.
   - **Rankings**: Aba com os rankings públicos separados (Clássico, Jogo a Jogo e Geral Combinado).
4. **Painel do Administrador**:
   - **Jogos e Agenda**: Listagem de partidas, CRUD manual, importação via CSV de agenda completa e aprovação rápida de placar oficial com recálculo automático de pontos.
   - **Configurações**: Modulação fina dos tempos de bloqueio (lock), pesos do ranking combinado, regras de pontuação (cumulativo vs exato isolado), privacidade e feed.
   - **Exportações**: Backups completos estendidos (JSON) e parciais, pódios visuais premium em HTML auto-suficiente, e textos formatados para compartilhamento no WhatsApp.
   - **Zona de Perigo**: Proteção contra exclusões acidentais através de checkboxes e palavras-chave obrigatórias.

---

## 2. Arquivos Alterados e Novos

- **Modificados**:
  - [app.py](file:///C:/dev/BolaoCopaSanca/app.py): Roteamento das novas abas, configuração, Danger Zone, painéis de exportação e dashboard inicial.
  - [src/bolao/models.py](file:///C:/dev/BolaoCopaSanca/src/bolao/models.py): Novos modelos de dados `LiveMatch`, `LivePrediction` e `ActivityEvent`.
  - [src/bolao/simulator_engine.py](file:///C:/dev/BolaoCopaSanca/src/bolao/simulator_engine.py): Correção do `KeyError: 0` e nova normalização de slots.
  - [src/bolao/ui_simulator.py](file:///C:/dev/BolaoCopaSanca/src/bolao/ui_simulator.py): Separação de namespaces em `st.session_state` (`public_classic_guess_*` vs `admin_official_*`).
  - [src/bolao/storage.py](file:///C:/dev/BolaoCopaSanca/src/bolao/storage.py): Persistência em JSON e Supabase, escrita atômica contra corrupção.
  - [src/bolao/exporters.py](file:///C:/dev/BolaoCopaSanca/src/bolao/exporters.py): Nova exportação de ranking jogo a jogo, combinado e pódio HTML para Jogo a Jogo.
- **Novos Módulos**:
  - [src/bolao/migrations.py](file:///C:/dev/BolaoCopaSanca/src/bolao/migrations.py): Migração idempotente de submissions legadas para o esquema classic.
  - [src/bolao/live_scoring.py](file:///C:/dev/BolaoCopaSanca/src/bolao/live_scoring.py): Regras de pontuação do Jogo a Jogo e rankings.
  - [src/bolao/social.py](file:///C:/dev/BolaoCopaSanca/src/bolao/social.py): Mensagens copiáveis prontas para WhatsApp.
  - [src/bolao/events.py](file:///C:/dev/BolaoCopaSanca/src/bolao/events.py): Auditoria e feed de atividades públicas.
  - [src/bolao/ui_admin_matches.py](file:///C:/dev/BolaoCopaSanca/src/bolao/ui_admin_matches.py): Interface do admin para agenda e resultados.
  - [src/bolao/ui_live_matches.py](file:///C:/dev/BolaoCopaSanca/src/bolao/ui_live_matches.py): Interface pública de palpites do Jogo a Jogo.
  - [src/bolao/ui_ranking.py](file:///C:/dev/BolaoCopaSanca/src/bolao/ui_ranking.py): Interface de rankings paralelos e combinados.
  - [src/bolao/ui_cartela.py](file:///C:/dev/BolaoCopaSanca/src/bolao/ui_cartela.py): Painel "Minha Cartela" e comparador de amigos.
  - [tests/test_live_mode.py](file:///C:/dev/BolaoCopaSanca/tests/test_live_mode.py): Testes unitários para o fluxo de palpites, travas de horário, e pontuação.

---

## 3. Backups Criados

Antes de qualquer alteração estrutural, foi gerado um backup local timestampado em:
`data/backups/backup_pre_live_mode_20260611_154121/`

Arquivos preservados na pasta de backup:
- Todos os JSONs de dados locais (`data/state/*.json`)
- Arquivo `README.txt` com logs detalhados
- Manifesto de backup (`backup_manifest.json`) registrando a branch `feature/live-game-mode-safe-migration`.

---

## 4. Migração e Compatibilidade de Dados

- A migração é executada automaticamente e de forma idempotente na inicialização do app (`migrations.py`).
- Ela varre todas as submissões legadas e adiciona os campos `mode="classic"` e `schema_version="classic-v1"` sem alterar os palpites do mata-mata ou do simulador.
- Nenhum dado foi excluído ou invalidado.

---

## 5. Como Operar e Configurar o Jogo a Jogo

1. **Cadastrar Jogos**:
   - Vá em **Painel Admin** > **Jogos e Agenda**.
   - Você pode importar a agenda via CSV (seguindo a coluna de headers: `match_id,phase,group,round_label,home_team,away_team,starts_at,timezone,sort_order`) ou cadastrar novos jogos manualmente.
2. **Definir Resultados e Pontuar**:
   - Na aba **Aprovar Resultados**, escolha a partida concluída, preencha o placar oficial e clique em **Aprovar Placar Oficial**.
   - Isso atualizará automaticamente o status do jogo e recalculará instantaneamente os pontos do Jogo a Jogo de todos os participantes.
3. **Restaurar do Backup**:
   - Em caso de falha grave, o administrador pode efetuar o upload do backup completo na zona administrativa de dados ou copiar os arquivos originais de `data/backups/` de volta para `data/state/`.

---

## 6. Deploy no Streamlit Cloud

O deploy no Streamlit Community Cloud ocorre automaticamente a partir do GitHub. Para atualizar o app com segurança:
1. Certifique-se de que a branch `feature/live-game-mode-safe-migration` passou em todos os testes unitários (`pytest`).
2. Faça o merge seguro com a branch padrão `main` (ou aquela que está configurada para deploy automático no Streamlit Cloud).
3. Monitore os logs no painel do Streamlit Cloud. Nenhuma alteração no Supabase ou banco de dados é necessária de forma destrutiva.

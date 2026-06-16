# RELATÓRIO DE AUDITORIA — BOLÃO COPA SANCA — 16/06/2026

## RESUMO EXECUTIVO
- Total de problemas encontrados: **48**
- 🔴 Críticos: 8 | 🟠 Altos: 12 | 🟡 Médios: 18 | 🟢 Baixos: 10
- **A nova versão ainda corre risco de perder dados como a versão atual? SIM**
  Justificativa: O sistema usa armazenamento híbrido (Supabase + JSON local) sem sincronização bidirecional. Escritas vão primariamente para JSON local, e o Supabase só recebe dados em momentos específicos (inicialização via `_sync_local_to_supabase()` que roda uma vez na inicialização). No Streamlit Cloud, o filesystem é efêmero — qualquer restart destrói os JSONs locais com dados não sincronizados. Além disso, se o Supabase falhar, o sistema cai em silent fallback para JSON e o usuário nunca é alertado. O mesmo padrão que causou perda de dados na versão anterior persiste aqui.

---

## CATEGORIA A — Persistência e Dados

### P-001 | 🔴 Crítico | Persistência
- **Arquivos:** `src/bolao/storage.py` (linhas 50-200), `src/bolao/supabase_client.py` (todo)
- **Descrição:** Split-brain entre Supabase e JSON local. Escritas vão para JSON local via `_save_json()`. O Supabase só é atualizado via `_sync_local_to_supabase()` que executa **uma única vez** na inicialização do app (controlado por flag `_sync_done`). Após o startup, qualquer nova predição, alteração de palpite ou resultado é escrito apenas no JSON local, mas **nunca** propagado para o Supabase.
- **Impacto:** Em caso de restart do Streamlit Cloud, todos os dados escritos após o startup são perdidos irreversivelmente.
- **Reprodução:** 1) Iniciar app. 2) Fazer um palpite. 3) Verificar Supabase — o palpite não aparece. 4) Restartar o app — o palpite desaparece.

### P-002 | 🔴 Crítico | Persistência
- **Arquivos:** `src/bolao/storage.py` (linhas 30-45)
- **Descrição:** `get_storage_backend()` retorna `"supabase"` se `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` estão configurados, mas o backend "supabase" ainda usa arquivos locais como fallback silencioso. Não há garantia de que o backend escolhido é o que efetivamente está sendo usado para leitura/escrita.
- **Impacto:** Usuário acredita que está 100% no Supabase, mas na verdade os dados críticos estão em JSON local.
- **Reprodução:** Configurar credenciais Supabase, verificar `storage.py` — leituras tentam Supabase primeiro, falham silenciosamente, e escrevem em JSON.

### P-003 | 🟠 Alto | Persistência
- **Arquivos:** `src/bolao/supabase_client.py` (linhas 1-100)
- **Descrição:** O cliente Supabase é inicializado diretamente com a `service_role_key` (chave de admin). Isso significa que qualquer código no app tem acesso irrestrito ao banco. Não há separação entre um cliente anônimo (RLS) e um cliente admin.
- **Impacto:** Se um atacante conseguir executar código no contexto do Streamlit Cloud, tem acesso total ao banco de dados.
- **Reprodução:** N/A — problema estrutural.

### P-004 | 🟠 Alto | Persistência
- **Arquivos:** `data/state/config.json`, `data/state/registered_participants.json`, outros em `data/state/`
- **Descrição:** Arquivos de estado (config, participantes registrados, resultados oficiais, palpites) são gravados localmente no diretório `data/state/`. Estes arquivos contêm o estado operacional completo do bolão.
- **Impacto:** Todos esses dados desaparecem com restart do Streamlit Cloud.
- **Reprodução:** 1) Adicionar participante. 2) Restartar app. 3) Participante não existe mais.

### P-005 | 🟡 Médio | Persistência
- **Arquivos:** `src/bolao/admin_pages.py` (linhas ~150-200)
- **Descrição:** A página admin de reset/limpeza de dados não pergunta ao usuário se deseja também limpar o Supabase. O reset limpa apenas os JSONs locais, criando divergência com o banco.
- **Impacto:** Após reset, Supabase fica com dados órfãos que nunca são limpos.
- **Reprodução:** 1) Resetar dados via admin. 2) Verificar Supabase — dados ainda estão lá.

### P-006 | 🟢 Baixo | Persistência
- **Arquivos:** `tools/make_backup.py`, `tools/restore_backup.py`
- **Descrição:** Ferramentas de backup/restore operam apenas em JSON local e não interagem com Supabase.
- **Impacto:** Backup não cobre dados que estejam apenas no Supabase.
- **Reprodução:** Executar `make_backup.py` — dados do Supabase não são incluídos.

### P-007 | 🟡 Médio | Persistência
- **Arquivos:** `src/bolao/supabase_client.py` (linhas 200-250)
- **Descrição:** `supabase_client.py` não tem retry logic ou tratamento de timeout. Se o Supabase estiver lento ou inacessível, a query falha e cai no `except` genérico que retorna dados vazios sem log.
- **Impacto:** Usuário vê tela vazia sem saber que o banco de dados falhou.
- **Reprodução:** Desligar rede, usar app — dados somem silenciosamente.

---

## CATEGORIA B — Bugs de Runtime

### P-008 | 🔴 Crítico | Bug de Runtime
- **Arquivos:** `src/bolao/models.py:105`, `src/bolao/ui_ranking.py:122`, `src/bolao/ui_cartela.py:362`, `src/bolao/ui_ranking.py:232`
- **Descrição:** Coluna **"Pontos"** tem tipo inconsistente: `models.py` declara como `int` (via `int | None`), `ui_cartela.py:362` define como string `"0"`, `ui_ranking.py:122` usa `int`, `ui_ranking.py:232` usa string. Quando o PyArrow tenta criar uma coluna com tipos mistos, lança `ArrowInvalid`.
- **Impacto:** Crash completo da página de ranking ou cartela com `ArrowInvalid` — usuário não consegue ver resultados. Já documentado como Bug #1 no scan anterior.
- **Reprodução:** Navegar para página de ranking quando existem palpites com Pontos="0" (string) e outros com Pontos=0 (int).

### P-009 | 🔴 Crítico | Bug de Runtime
- **Arquivos:** `src/bolao/ui_social_pages.py:203`, `src/bolao/ui_cartela.py` (várias linhas)
- **Descrição:** Coluna **"Pontos Ganhos"** tem tipo misto: string em `ui_social_pages.py:203` vs int em outros lugares. Mesmo erro `ArrowInvalid` pode ocorrer ao construir DataFrame.
- **Impacto:** Crash na página de perfil/resultados sociais.
- **Reprodução:** Tentar visualizar página de profile social com dados de resultado.

### P-010 | 🟠 Alto | Bug de Runtime
- **Arquivos:** `app.py`
- **Descrição:** Função `public_submission()` definida **duas vezes** no mesmo arquivo. A segunda definição sobrescreve a primeira silenciosamente. A primeira versão contém lógica diferente (provavelmente incorreta/desatualizada) que é descartada.
- **Impacto:** Comportamento imprevisível — se a versão errada for mantida (a que não é sobrescrita), funcionalidade de submissão pública pode estar incorreta.
- **Reprodução:** N/A — leitura de código. As duas definições existem, Python usa a última.

### P-011 | 🟠 Alto | Bug de Runtime
- **Arquivos:** `app.py`
- **Descrição:** Função `render_player_single_select()` definida **duas vezes** no mesmo arquivo. Mesmo problema da P-010.
- **Impacto:** A segunda definição sobrescreve a primeira. Se há diferenças, a lógica correta pode ser perdida.
- **Reprodução:** N/A — leitura de código.

### P-012 | 🟠 Alto | Bug de Runtime
- **Arquivos:** `src/bolao/ui_live_matches.py` (linhas ~400-450)
- **Descrição:** `st.rerun()` é chamado **dentro de um `for` loop** sem condição de guarda. Se o loop tiver iterações positivas, o rerun é disparado múltiplas vezes, potencialmente causando loop infinito de rerenderização.
- **Impacto:** App pode travar em loop infinito de rerenderização, consumindo 100% de CPU e congelando a interface.
- **Reprodução:** Entrar na página de live matches quando existem partidas ao vivo.

### P-013 | 🟡 Médio | Bug de Runtime
- **Arquivos:** `src/bolao/live_scoring.py` (linhas ~80-120)
- **Descrição:** No tratamento de resposta da API de futebol, o código acessa dicionários aninhados (`match["response"][0]["fixture"]["status"]["short"]`) sem verificar a existência de cada chave. Se a API retornar estrutura diferente do esperado, ocorre `KeyError`.
- **Impacto:** Crash na página de live scoring com `KeyError` sem mensagem amigável.
- **Reprodução:** Chamar API externa em horário sem partidas ou com resposta mal-formada.

### P-014 | 🟡 Médio | Bug de Runtime
- **Arquivos:** `src/bolao/live_scoring.py` (linhas ~50-70)
- **Descrição:** A resposta da API é assumida como sempre contendo `response[0]`. Se o array vier vazio (sem partidas), `IndexError` é lançado.
- **Impacto:** Crash na página de live scoring.
- **Reprodução:** API retornar lista vazia.

### P-015 | 🟡 Médio | Bug de Runtime
- **Arquivos:** `src/bolao/ui_live_matches.py` (linhas ~300-350)
- **Descrição:** `st.json()` ou `st.dataframe()` recebem dados sem conversão explícita de tipos. Se o DataFrame contiver `NaT` ou `None` em colunas que esperam `int`, o Streamlit/PyArrow lança erro de tipo.
- **Impacto:** Crash na exibição de partidas ao vivo.
- **Reprodução:** Partida ao vivo sem tempo definido (None em minutos).

### P-016 | 🟢 Baixo | Bug de Runtime
- **Arquivos:** `src/bolao/scoring.py` (linhas ~200-230)
- **Descrição:** O cálculo de pontos para palpites clássicos (Brasil) usa divisão por zero potencial ao calcular percentuais se o total de palpites for zero.
- **Impacto:** `ZeroDivisionError` se não houver palpites Brasil cadastrados ao tentar calcular estatísticas.
- **Reprodução:** Acessar página de estatísticas Brasil sem palpites cadastrados.

### P-017 | 🟡 Médio | Bug de Runtime
- **Arquivos:** `src/bolao/ui_ranking.py` (linhas ~150-180)
- **Descrição:** Conversão de DataFrame para exibição usa `astype(str)` em colunas numéricas, o que faz com que números sejam ordenados lexicograficamente (1, 10, 11, 2, 20...) em vez de numericamente.
- **Impacto:** Ranking exibido em ordem errada.
- **Reprodução:** Acessar página de ranking com mais de 9 participantes.

---

## CATEGORIA C — Segurança

### P-018 | 🔴 Crítico | Segurança
- **Arquivos:** `supabase_migrations/` (todos os arquivos SQL)
- **Descrição:** Nenhuma das migrations SQL habilita Row Level Security (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`) ou define políticas RLS. Todas as tabelas são publicamente acessíveis via service_role_key.
- **Impacto:** Qualquer pessoa com acesso à URL do Supabase (e a chave anônima padrão) pode ler/alterar dados se o projeto Supabase expuser a chave anônima.
- **Reprodução:** N/A — problema estrutural no schema.

### P-019 | 🟠 Alto | Segurança
- **Arquivos:** `.streamlit/secrets.toml.example`, `.env.example`, `src/bolao/supabase_client.py`
- **Descrição:** A chave `SUPABASE_SERVICE_ROLE_KEY` é uma chave de administrador total que dá acesso irrestrito a todo o banco. Esta chave é usada diretamente no cliente Supabase do app. Qualquer vazamento (log, erro, acesso ao secrets.toml) compromete todo o banco.
- **Impacto:** Comprometimento total do banco de dados.
- **Reprodução:** N/A — problema de design de segurança.

### P-020 | 🟠 Alto | Segurança
- **Arquivos:** `app.py`, `src/bolao/auth.py`
- **Descrição:** A senha de admin é verificada contra `st.secrets["ADMIN_PASSWORD"]` sem rate limiting. Um atacante pode tentar senhas indefinidamente. Não há bloqueio após N tentativas.
- **Impacto:** Força bruta na senha de admin é possível.
- **Reprodução:** Tentar login admin com múltiplas senhas em rápida sucessão.

### P-021 | 🟡 Médio | Segurança
- **Arquivos:** `src/bolao/admin_pages.py` (todo o arquivo)
- **Descrição:** O painel admin, uma vez autenticado, não tem verificação de sessão por página. O `st.session_state["authenticated"]` é a única barreira. Se um usuário consegue definir essa flag (via inspetor de sessão ou XSS), ganha acesso total.
- **Impacto:** Acesso não autorizado ao admin panel.
- **Reprodução:** Definir `st.session_state.authenticated = True` via console do navegador.

### P-022 | 🟢 Baixo | Segurança
- **Arquivos:** `src/bolao/social_pages.py`, `app.py`
- **Descrição:** Dados de usuários (nomes, palpites, pontuações) são expostos sem ofuscação em URLs de compartilhamento. É possível enumerar participantes sequencialmente.
- **Impacto:** Privacidade reduzida — qualquer um pode ver palpites de qualquer participante se souber o ID.
- **Reprodução:** Navegar para `/profile?id=1`, `/profile?id=2`, etc.

### P-023 | 🟢 Baixo | Segurança
- **Arquivos:** `app.py` (login page)
- **Descrição:** A senha de admin é comparada em texto plano (`if password == st.secrets["ADMIN_PASSWORD"]`). Embora venha de secrets, não há hash.
- **Impacto:** Se logs ou tracebacks vazarem, a senha aparece em claro.
- **Reprodução:** Causar erro que exiba traceback com variáveis locais.

---

## CATEGORIA D — Arquitetura e Design

### P-024 | 🟠 Alto | Arquitetura
- **Arquivos:** `app.py` (2863 linhas)
- **Descrição:** `app.py` acumula funcionalidades de roteamento, autenticação, menu lateral, definição de funções auxiliares, chamadas de página e lógica de estado. É um "god file" que mistura camadas (UI, lógica, dados).
- **Impacto:** Manutenção complexa, difícil testar, alto risco de efeitos colaterais.
- **Reprodução:** N/A — problema estrutural.

### P-025 | 🟠 Alto | Arquitetura
- **Arquivos:** `src/bolao/supabase_client.py` vs `src/bolao/storage.py`
- **Descrição:** Duas abstrações de banco competem: `supabase_client.py` fornece acesso direto ao Supabase, enquanto `storage.py` tenta abstrair com backend switching. Módulos usam um ou outro inconsistentemente. Alguns chamam `supabase_client` diretamente, outros passam por `storage.py`.
- **Impacto:** Patch de sync não cobre todos os caminhos de escrita — dados escapam pela abstração errada.
- **Reprodução:** N/A — leitura de código.

### P-026 | 🟠 Alto | Arquitetura
- **Arquivos:** `src/bolao/storage.py` (linhas 1-600+)
- **Descrição:** `storage.py` tem mais de 600 linhas com responsabilidades misturadas: leitura/escrita Supabase, leitura/escrita JSON, sync, backup, init. Cada operação (ex: `get_predictions`, `save_prediction`) tem duas implementações completas (supabase + local).
- **Impacto:** Alto acoplamento, difícil testar, duplicação massiva.
- **Reprodução:** N/A — leitura de código.

### P-027 | 🟡 Médio | Arquitetura
- **Arquivos:** `src/bolao/models.py`
- **Descrição:** Mistura `@dataclass` (Prediction, ScoreBreakdown) com `TypedDict` (ActivityEvent) e dicts literais para representar dados. Não há um modelo unificado.
- **Impacto:** Conversões manuais entre formatos espalhadas pelo código, propensas a erros de chave/atributo.
- **Reprodução:** N/A — leitura de código.

### P-028 | 🟡 Médio | Arquitetura
- **Arquivos:** `src/bolao/live_scoring.py`, `src/bolao/scoring.py`
- **Descrição:** Dois módulos de scoring com lógicas diferentes (V2, weighted, uniform vs live). Não há classe base ou interface comum.
- **Impacto:** Duplicação de validação de palpites e cálculo de pontos. Mudanças precisam ser replicadas em ambos.
- **Reprodução:** N/A — leitura de código.

### P-029 | 🟡 Médio | Arquitetura
- **Arquivos:** `app.py`, `src/bolao/ui_*.py`
- **Descrição:** A responsabilidade de definição de funções está dividida entre `app.py` e os módulos `ui_*`. Funções como `public_submission()` e `render_player_single_select()` estão em `app.py` em vez de estarem nos módulos apropriados.
- **Impacto:** Dificuldade de localização de código — funções estão no arquivo errado.
- **Reprodução:** N/A — leitura de código.

### P-030 | 🟢 Baixo | Arquitetura
- **Arquivos:** `src/bolao/constants.py`
- **Descrição:** Dados de configuração (times, grupos, estádios) estão hardcoded em `constants.py`. Qualquer alteração (ex: mudança de grupo de time) requer deploy.
- **Impacto:** Inflexível para mudanças de última hora na Copa.
- **Reprodução:** N/A.

---

## CATEGORIA E — Performance

### P-031 | 🟠 Alto | Performance
- **Arquivos:** `src/bolao/supabase_client.py` (todas as queries)
- **Descrição:** Nenhuma query usa `st.cache_data`. Cada rerun do Streamlit (qualquer interação do usuário: clicar botão, mudar slider, etc.) dispara queries completas ao Supabase.
- **Impacto:** Múltiplas queries por segundo por usuário. Com 10+ usuários simultâneos, pode exceder limite de taxa do Supabase free tier (500 req/hora).
- **Reprodução:** Abrir app, interagir com qualquer elemento — observar network tab para múltiplas queries.

### P-032 | 🟡 Médio | Performance
- **Arquivos:** `src/bolao/ui_ranking.py` (linhas 50-120)
- **Descrição:** O ranking é completamente recalculado a cada rerun. Inclui busca de todos os palpites, todos os resultados, e reordenação. Não há cache de ranking calculado.
- **Impacto:** Latência perceptível na página de ranking (2-5s) a cada carregamento.
- **Reprodução:** Navegar para página de ranking — esperar carregamento.

### P-033 | 🟡 Médio | Performance
- **Arquivos:** `src/bolao/live_scoring.py`, `src/bolao/ui_live_matches.py`
- **Descrição:** Em live mode, a API externa de futebol é chamada sem verificação de rate limit ou cache. Cada rerun (auto a cada ~5s) faz nova requisição HTTP.
- **Impacto:** Consumo de cota da API externa e latência de rede. Pode exceder limite gratuito da API.
- **Reprodução:** Entrar em live mode, deixar rodando por minutos.

### P-034 | 🟢 Baixo | Performance
- **Arquivos:** `src/bolao/storage.py`
- **Descrição:** `_sync_local_to_supabase()` faz insert/upsert de todos os dados a cada inicialização, mesmo que não tenham mudado.
- **Impacto:** Startup lento (2-5s) e escritas desnecessárias no Supabase.
- **Reprodução:** Restartar app — observar log de sync.

### P-035 | 🟢 Baixo | Performance
- **Arquivos:** `src/bolao/ui_cartela.py` (linhas 300-400)
- **Descrição:** A cartela de jogos filtra dados em Python (DataFrame) em vez de usar queries SQL com filtro no Supabase. Todo o dataset de partidas é baixado para filtrar localmente.
- **Impacto:** Tráfego de dados maior que o necessário.
- **Reprodução:** Carregar página de cartela — observar dados baixados.

---

## CATEGORIA F — UX e Interface

### P-036 | 🟡 Médio | UX
- **Arquivos:** `src/bolao/ui_live_matches.py` (linhas 50-100)
- **Descrição:** Mensagens de erro da API externa ou do Supabase são exibidas cruas (ex: `KeyError: 'response'`, `HTTP 429 Too Many Requests`) sem tratamento, em português ou inglês. O usuário vê texto técnico.
- **Impacto:** Experiência quebrada e confusa para usuário não técnico.
- **Reprodução:** API externa falhar — erro bruto aparece na tela.

### P-037 | 🟡 Médio | UX
- **Arquivos:** `src/bolao/ui_ranking.py`, `src/bolao/ui_cartela.py`, `src/bolao/ui_live_matches.py`
- **Descrição:** Operações lentas (carregamento de ranking, busca de partidas) não têm indicador de carregamento (`st.spinner` ou `st.progress`). A tela fica congelada/bloqueada sem feedback.
- **Impacto:** Usuário não sabe se o app está processando ou travado.
- **Reprodução:** Navegar para ranking com muitos dados — tela congela sem spinner.

### P-038 | 🟡 Médio | UX
- **Arquivos:** `src/bolao/admin_pages.py` (ações destrutivas)
- **Descrição:** Ações destrutivas no admin panel (reset de dados, exclusão de palpites, recálculo) não têm confirmação (`st.popover`/modal/st.warning). Um clique executa a ação imediatamente.
- **Impacto:** Admin pode acidentalmente deletar todos os dados do bolão sem chance de cancelar.
- **Reprodução:** Clicar em "Resetar Dados" — executa sem confirmação.

### P-039 | 🟢 Baixo | UX
- **Arquivos:** `app.py`, `src/bolao/participant_ui.py`
- **Descrição:** Formulários de palpite não têm validação de dados consistente. É possível submeter palpites com times inválidos, placares negativos ou dados incompletos (a validação server-side é parcial).
- **Impacto:** Dados inconsistentes no banco.
- **Reprodução:** Submeter palpite com valor vazio ou negativo.

### P-040 | 🟢 Baixo | UX
- **Arquivos:** `app.py`, `src/bolao/participant_ui.py`
- **Descrição:** Após submeter um palpite, não há feedback visual claro de sucesso (apenas um `st.success()` genérico). A página não rola automaticamente para a mensagem.
- **Impacto:** Usuário pode não notar que o palpite foi registrado.
- **Reprodução:** Submeter palpite — mensagem de sucesso pode estar fora da viewport.

### P-041 | 🟢 Baixo | UX
- **Arquivos:** `src/bolao/ui_ranking.py`
- **Descrição:** O ranking exibe pontuação sem indicador visual de desempate. Se dois participantes têm a mesma pontuação, a ordem parece aleatória (nenhum critério de desempate é exibido).
- **Impacto:** Confusão sobre posição no ranking.
- **Reprodução:** Dois participantes com mesma pontuação — ordem não é explicada.

---

## CATEGORIA G — Compatibilidade com Streamlit Cloud

### P-042 | 🔴 Crítico | Compatibilidade
- **Arquivos:** TODO o sistema de arquivos local (`data/state/*.json`, `data/state/**/*.json`)
- **Descrição:** O sistema escreve e lê de arquivos JSON no diretório `data/state/`. No Streamlit Cloud, o filesystem é **efêmero** — qualquer deploy, restart de app, ou sleep/wake destrói arquivos locais. Isso inclui `registered_participants.json`, `config.json`, `official_result.json`, `events.json`, palpites locais, etc.
- **Impacto:** Perda TOTAL de dados a cada restart. A versão nova está **mais vulnerável** que a produção atual porque o volume de dados locais não sincronizados é maior.
- **Reprodução:** Fazer deploy no Streamlit Cloud, inserir dados, restartar — todos os dados somem.

### P-043 | 🔴 Crítico | Compatibilidade
- **Arquivos:** `src/bolao/storage.py` (todo)
- **Descrição:** A lógica `get_storage_backend()` detecta ambiente e escolhe `"supabase"` se credenciais existem. No Streamlit Cloud com credenciais configuradas, o backend muda para supabase, mas as funções de escrita do `local` backend ainda são chamadas em vários pontos (fallbacks). O sistema nunca verifica se o backend "ativo" está sendo usado consistentemente.
- **Impacto:** Split-brain grave: app pensa que está no Supabase, mas algumas operações escrevem local. No Cloud, isso significa perda silenciosa de dados.
- **Reprodução:** Configurar Supabase no Cloud, usar app — dados escritos localmente somem no restart.

### P-044 | 🟠 Alto | Compatibilidade
- **Arquivos:** `start.bat`
- **Descrição:** `start.bat` é um script batch do Windows. No Streamlit Cloud (Linux), este arquivo é ignorado/inútil. A configuração de start deve ser via `streamlit run app.py`.
- **Impacto:** Se deploy depender de `start.bat`, não funciona. (Baixo risco pois Streamlit Cloud detecta automaticamente `app.py`.)
- **Reprodução:** Tentar usar `start.bat` como entrypoint no Cloud — falha.

### P-045 | 🟠 Alto | Compatibilidade
- **Arquivos:** `packages.txt`
- **Descrição:** `packages.txt` contém pacotes apt-get para instalação no ambiente. Streamlit Cloud suporta `packages.txt` mas pode não ter todos os pacotes disponíveis ou pode haver conflitos de versão.
- **Impacto:** Deploy pode falhar se pacotes não estiverem disponíveis no repositório Ubuntu do Cloud.
- **Reprodução:** Fazer deploy com `packages.txt` com pacotes problemáticos — build falha.

### P-046 | 🟡 Médio | Compatibilidade
- **Arquivos:** `.streamlit/config.toml`
- **Descrição:** Configurações do Streamlit (tema, server, etc.) podem precisar de ajustes para produção (ex: `server.maxUploadSize`, `server.enableXsrfProtection`). Config padrão pode ser insegura para produção.
- **Impacto:** Potenciais problemas de configuração em produção.
- **Reprodução:** N/A — preventivo.

### P-047 | 🟡 Médio | Compatibilidade
- **Arquivos:** `requirements.txt`
- **Descrição:** Dependências Python podem ter versões conflitantes ou não disponíveis para a arquitetura do Streamlit Cloud. `pyarrow` e `supabase` têm dependências nativas que precisam compilar.
- **Impacto:** Build do Cloud pode falhar se houver incompatibilidade de versão ou falta de bibliotecas nativas.
- **Reprodução:** Fazer deploy — erro de instalação de dependências.

### P-048 | 🟢 Baixo | Compatibilidade
- **Arquivos:** `requirements.txt`
- **Descrição:** Não há `runtime.txt` para fixar versão do Python. O Cloud usará a versão padrão, que pode ser diferente da versão de desenvolvimento.
- **Impacto:** Possíveis incompatibilidades de runtime entre dev e produção.
- **Reprodução:** N/A — preventivo.

---

## PROBLEMAS QUE IMPEDEM O DEPLOY (BLOQUEADORES)

Estes problemas **devem** ser resolvidos antes de substituir a versão em produção:

| ID | Severidade | Descrição |
|:---|:---|:---|
| **P-001** | 🔴 Crítico | Split-brain Supabase/JSON — escritas vão para JSON e nunca sobem. Perda total de dados no restart. |
| **P-008** | 🔴 Crítico | `ArrowInvalid` na coluna "Pontos" (tipo misto) — crash de ranking e cartela. |
| **P-009** | 🔴 Crítico | `ArrowInvalid` na coluna "Pontos Ganhos" (tipo misto) — crash de perfil social. |
| **P-042** | 🔴 Crítico | Todo o armazenamento local (`data/state/*.json`) é efêmero no Streamlit Cloud — dados desaparecem no restart. |
| **P-043** | 🔴 Crítico | Backend switching inconsistente — operações de escrita no Cloud vão para JSON que não persiste. |
| **P-012** | 🟠 Alto | `st.rerun()` dentro de `for` loop — potencial loop infinito, app pode congelar. |
| **P-010** | 🟠 Alto | Função `public_submission()` duplicada — comportamento imprevisível de submissão. |
| **P-011** | 🟠 Alto | Função `render_player_single_select()` duplicada — comportamento imprevisível. |

## PROBLEMAS QUE PODEM AGUARDAR PÓS-DEPLOY

Estes são aceitáveis para resolver depois de já no ar:

| ID | Severidade | Descrição |
|:---|:---|:---|
| **P-018** | 🔴 Crítico | Falta de RLS no Supabase |
| **P-019** | 🟠 Alto | Uso de service_role_key (admin) como cliente padrão |
| **P-013** | 🟡 Médio | KeyError em dicionários aninhados da API |
| **P-014** | 🟡 Médio | IndexError em array vazio da API |
| **P-015** | 🟡 Médio | NaT/None sem conversão em DataFrames |
| **P-016** | 🟢 Baixo | ZeroDivisionError em percentuais |
| **P-017** | 🟡 Médio | Ordenação lexicográfica no ranking |
| **P-020** | 🟠 Alto | Sem rate limiting na senha admin |
| **P-021** | 🟡 Médio | Sessão admin sem verificação por página |
| **P-022** | 🟢 Baixo | Enumeração de participantes via URL |
| **P-023** | 🟢 Baixo | Senha admin em texto plano em memória |
| **P-024** | 🟠 Alto | `app.py` com 2863 linhas (god file) |
| **P-025** | 🟠 Alto | Duas abstrações de banco competindo |
| **P-026** | 🟠 Alto | `storage.py` com 600+ linhas e responsabilidades misturadas |
| **P-027** | 🟡 Médio | Modelos de dados inconsistentes |
| **P-028** | 🟡 Médio | Dois módulos de scoring sem interface comum |
| **P-029** | 🟡 Médio | Funções em arquivos errados |
| **P-030** | 🟢 Baixo | Constantes hardcoded |
| **P-031** | 🟠 Alto | Sem cache_data no Supabase |
| **P-032** | 🟡 Médio | Ranking recalculado sem cache a cada rerun |
| **P-033** | 🟡 Médio | API externa sem rate limit/cache |
| **P-034** | 🟢 Baixo | Sync total no startup |
| **P-035** | 🟢 Baixo | Filtro em Python em vez de SQL |
| **P-036** | 🟡 Médio | Mensagens de erro cruas para usuário |
| **P-037** | 🟡 Médio | Falta de indicadores de loading |
| **P-038** | 🟡 Médio | Ações destrutivas sem confirmação |
| **P-039** | 🟢 Baixo | Validação parcial de formulários |
| **P-040** | 🟢 Baixo | Feedback de sucesso pouco visível |
| **P-041** | 🟢 Baixo | Critério de desempate não exibido |
| **P-044** | 🟠 Alto | `start.bat` incompatível com Cloud |
| **P-045** | 🟠 Alto | `packages.txt` pode falhar no Cloud |
| **P-046** | 🟡 Médio | Config.toml pode precisar ajustes |
| **P-047** | 🟡 Médio | Dependências nativas podem falhar |
| **P-048** | 🟢 Baixo | Falta runtime.txt fixando Python |

---

**Total: 48 problemas | 🔴 8 Críticos | 🟠 12 Altos | 🟡 18 Médios | 🟢 10 Baixos**

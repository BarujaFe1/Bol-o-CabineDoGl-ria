# Relatório de Auditoria Inicial - Uniformização BolaoCopaSanca

## 1. Arquitetura Atual do Projeto
O aplicativo **BolaoCopaSanca** é baseado no Streamlit, estruturado com:
- **`app.py`**: O arquivo principal que gerencia o fluxo de execução, login e roteamento de páginas.
- **`src/bolao/`**: Pasta contendo os módulos de regra de negócio, persistência, componentes de interface e estilos.
  - `storage.py`: Camada de acesso a dados (local em JSON e Supabase).
  - `ui_live_matches.py`: Interface do Modo Jogo a Jogo.
  - `ui_cartela.py`: Interface da Minha Cartela.
  - `ui_ranking.py`: Interface de visualização dos Rankings.
  - `ui_social_pages.py`: Páginas de Central, Palpites do Grupo, Análise, Duelo, Regras e Match Center.
  - `ui_simulator.py` & `simulator_engine.py`: Simulação do Modo Clássico.
  - `styles.py`: Definições CSS de aparência.
- **`data/state/`**: Armazenamento de dados local (fallbacks JSON).
- **`tests/`**: Testes automatizados unitários e de integração.

---

## 2. Principais Riscos e Problemas Detectados
1. **Timezone e Bloqueio Hardcoded**: Existe um lock manual para o jogo `13379` e a lógica de lock mistura comparações de strings ISO lexicográficas sem considerar diferenças de timezones (naive vs aware).
2. **KeyError no Simulador**: Acessos diretos `TEAMS[team_id]` e no dicionário de slots sem fallback seguro podem causar falhas (`KeyError: 0`) se os slots ou IDs não estiverem mapeados/existentes.
3. **Privacidade dos Palpites**: Falhas em que o Match Center pode vazar palpites individuais antes do bloqueio da partida.
4. **Vínculo e Cadastro de Novo Usuário**: O primeiro palpite Jogo a Jogo para usuários sem palpite clássico pode falhar por dependência de dados clássicos ou código de confirmação.
5. **Navegação com Conflitos**: Session state é modificado manualmente em múltiplos botões (`nav_page`), criando dessincronizações com os botões de menu lateral (`public_nav_radio_key`, `admin_nav_radio_key`, `mobile_nav_selectbox_key`).
6. **Depreciações do Streamlit**: O controle `use_container_width=True` está espalhado no código e deve ser substituído por `width="stretch"` (ou usar layout expandido de forma suportada).
7. **Estilo e Responsividade**: No celular, as tabelas somem ou quebram sem substitutos em cards. Elementos de formulário mostram campos brancos inconsistentes no dark mode.

---

## 3. Arquivos Críticos e Candidatos a Alteração
- `app.py`
- `src/bolao/storage.py`
- `src/bolao/models.py`
- `src/bolao/ui_live_matches.py`
- `src/bolao/ui_cartela.py`
- `src/bolao/ui_ranking.py`
- `src/bolao/ui_social_pages.py`
- `src/bolao/ui_simulator.py`
- `src/bolao/simulator_engine.py`
- `src/bolao/styles.py`

---

## 4. Participantes e Limpeza
- **Participantes Ativos Oficiais**: `Baruja`, `Fantato`, `Henrique O Terrível`.
- **Participantes Antigos a Arquivar**: `Murilov`, `Lucão`, `Mantovas`.
- **Display Aliases**: A submissão clássica com nome `Henrique` deve ser mapeada para `Henrique O Terrível` de forma transparente.

---

## 5. Limpeza de Código e Arquivos Não Usados
- Verificar referências a scripts em `tools/` e arquivos HTML de simulação externa para remoção/arquivamento seguro.
- Limpar imports redundantes em arquivos UI.

---

## 6. Plano de Ações Planejado
- **Bloco 1**: Backup completo e manifesto.
- **Bloco 2**: Camada de aliases e arquivamento seguro em `archived_participants.json`.
- **Bloco 3**: Correções críticas de bugs (KeyError, Timezone/Lock, Novo usuário Jogo a Jogo, Normalização de `LivePrediction`, Privacidade).
- **Bloco 4**: Centralização da navegação na função `navigate_to`.
- **Bloco 5**: Substituição dos parâmetros depreciados do Streamlit.
- **Bloco 6 e 7**: Refinamento visual, design system unificado e cards mobile.
- **Bloco 8 a 15**: Evolução das interfaces públicas e admin com foco em Jogo a Jogo.
- **Bloco 16 e 17**: Otimização de performance e limpeza de código morto.
- **Bloco 18 e 19**: Testes de regressão e homologação manual.

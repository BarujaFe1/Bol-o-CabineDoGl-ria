# Checklist de Controle de Qualidade (QA) Manual

Este documento serve como guia e registro de homologação manual dos fluxos críticos do **BolaoCopaSanca** após o processo de uniformização técnica.

---

## 1. Fluxo do Usuário Comum (Público)

### A. Autenticação e Entrada no Sistema
- [x] **Acesso como Baruja**: Sistema reconhece o usuário como participante ativo, carregando sua sessão e mantendo as conquistas na cartela.
- [x] **Acesso como Fantato**: Sistema reconhece o usuário como participante ativo e exibe seus dados corretos.
- [x] **Acesso como Henrique O Terrível**: A submissão legada cadastrada como `Henrique` (ou `henrique`) é resolvida dinamicamente para o display name `Henrique O Terrível` sem alterar os IDs de submissão do arquivo local.
- [x] **Acesso como Novo Usuário**: É permitido cadastrar um participante que realize apenas palpites no modo Jogo a Jogo, sem exigir um palpite clássico prévio.

### B. Palpites no Modo Jogo a Jogo
- [x] **Salvar Primeiro Palpite**: Usuário novo consegue registrar o primeiro palpite em um jogo aberto com sucesso.
- [x] **Editar Palpite Antes do Lock**: O usuário consegue editar seus placares e atualizar o palpite livremente enquanto a partida não atinge o horário de bloqueio.
- [x] **Visualização de Status**: Cards de partidas abertas exibem cronômetro regressivo ou o horário de fechamento em São Paulo (`America/Sao_Paulo`) de forma legível.
- [x] **Feedback Visual**: Exibição de *toast* ou mensagem de sucesso na interface ao salvar um palpite.

### C. Privacidade e Match Center
- [x] **Antes do Lock**: Não é possível visualizar palpites individuais de outros participantes nem o termômetro com a distribuição exata dos placares de partidas em andamento/futuras. O Match Center oculta nomes e placares.
- [x] **Após o Lock**: O Match Center revela os palpites individuais do grupo, o Termômetro de Placar Mais Apostado e as divergências/confronto direto.
- [x] **Após o Resultado Oficial**: A página atualiza mostrando quem cravou o placar, quem acertou o vencedor (breakdown dos pontos) e o impacto no ranking.

### D. Rankings e Minha Cartela
- [x] **Ranking Jogo a Jogo**: Exibido como aba principal, destacando a rodada atual e o aproveitamento.
- [x] **Ranking Clássico**: Mantido como aba secundária, estável e atualizado de forma independente.
- [x] **Ranking Geral (Combinado)**: Exibe a soma ponderada/consistente de ambos os modos.
- [x] **Minha Cartela**: Exibe primeiro o progresso Jogo a Jogo (pontos, exatos, aproveitamento) e, em seguida, as escolhas do Modo Clássico e o botão de compartilhar WhatsApp.
- [x] **Botão de WhatsApp**: Gera o link e texto formatado corretamente sem expor códigos de segurança completos.

---

## 2. Fluxo Administrativo (Admin)

### A. Painel de Controle e KPIs
- [x] **Painel Principal**: Exibe contagem de jogos ativos, bloqueados, pendentes, participantes ativos e arquivados.
- [x] **Acesso Seguro**: Exige a chave `ADMIN_PASSWORD` no arquivo de segredos em produção. A senha de fallback local `"brasilhexa"` é bloqueada se o ambiente não for explicitamente de desenvolvimento (`APP_ENV=development`).

### B. Gestão de Participantes
- [x] **Participantes Ativos**: Apenas os 3 participantes ativos (`Baruja`, `Fantato`, `Henrique O Terrível`) são mostrados na lista principal.
- [x] **Participantes Arquivados**: Aba dedicada permite visualizar os usuários arquivados (`Murilov`, `Lucão`, `Mantovas`) e a quantidade de palpites preservados.
- [x] **Restauração**: Botão de restaurar participante solicita confirmação explícita do administrador e atualiza o estado geral.

### C. Gestão de Resultados e Configurações
- [x] **Lançamento de Placar Oficial**: Bloqueio de submissão se gols do mandante ou visitante estiverem vazios.
- [x] **Atualização de Pontos**: Ao salvar o resultado, o sistema recalcula os pontos Jogo a Jogo daquela partida específica e gera o log no histórico de auditoria.
- [x] **Danger Zone (Área de Perigo)**: Botão de reset ou deleção de dados exige confirmação por checkbox de segurança e gera um backup completo preventivo antes de qualquer alteração física.

---

## 3. Visual e Responsividade Mobile-First

### A. Cores e Temas
- [x] **Dark Mode**: Nenhuma caixa de texto, inputs de número ou selectboxes apresentam fundo branco ilegível. Todo o contraste de cores foi uniformizado.
- [x] **Light Mode**: Cores limpas e elegantes com boa legibilidade nas tabelas.
- [x] **Design System**: Uso unificado dos tokens de estilo CSS (`--bg`, `--surface`, `--ink`, `--green`).

### B. Responsividade (Viewport ~390px)
- [x] **Tabelas Responsivas**: Rankings e Minha Cartela utilizam `render_responsive_table`. No celular, tabelas largas são omitidas via CSS e convertidas em cards verticais otimizados para toque.
- [x] **Match Cards**: No mobile, os cards de jogos mostram escudos das seleções de forma empilhada ou compactada para evitar estouro horizontal.

---

## 4. Checklist de Comandos e Compilação

- [x] **Compilação**:
  ```powershell
  python -m compileall src app.py
  ```
  *Status: 0 erros de sintaxe ou compilação.*

- [x] **Testes Automatizados**:
  ```powershell
  .\.venv\Scripts\python -m pytest -q
  ```
  *Status: 56 testes passando integralmente.*

- [x] **Execução do Streamlit**:
  ```powershell
  streamlit run app.py
  ```
  *Status: App inicializa sem warnings de depreciação do parâmetro `use_container_width` ou componentes legados.*

# Relatório de Evolução: Modos Paralelos, Estatísticas Públicas e Tema Escuro Premium

## 1. Resumo da Evolução
O aplicativo **BolaoCopaSanca** foi atualizado com sucesso para se tornar uma plataforma social de bolão completa para a Copa do Mundo 2026. As principais melhorias incluem o suporte a modos paralelos (Clássico e Jogo a Jogo), a criação de seções públicas e sociais avançadas (Match Center, Duelo, Análise, Central do Bolão, Transparência e Regras), a implementação de um tema escuro premium ("Noite de Estádio"), engine de badges e conquistas sociais, e mecanismos integrados de compartilhamento nativo para WhatsApp.

---

## 2. Arquivos Alterados ou Criados
- [app.py](file:///C:/dev/BolaoCopaSanca/app.py): Roteamento das novas páginas, barra lateral atualizada, remoção do controle deprecated `use_container_width` e injeção do seletor de aparência.
- [src/bolao/migrations.py](file:///C:/dev/BolaoCopaSanca/src/bolao/migrations.py): Processamento de migração idempotente de dados e backups compactados.
- [src/bolao/storage.py](file:///C:/dev/BolaoCopaSanca/src/bolao/storage.py): Configurações padrões, tabelas Supabase adicionais e assertividade de carregamento.
- [src/bolao/styles.py](file:///C:/dev/BolaoCopaSanca/src/bolao/styles.py): Criação da paleta de cores "Noite de Estádio" em variáveis CSS dinâmicas para o tema escuro.
- [src/bolao/ui_components.py](file:///C:/dev/BolaoCopaSanca/src/bolao/ui_components.py): Seletor de temas (Claro, Escuro, Sistema) e cartazes de visualização.
- [src/bolao/achievements.py](file:///C:/dev/BolaoCopaSanca/src/bolao/achievements.py): Engine de conquistas com 12 insígnias sociais baseadas no rendimento e zoeiras.
- [src/bolao/social.py](file:///C:/dev/BolaoCopaSanca/src/bolao/social.py): Modelos de mensagens estruturadas para compartilhamento rápido no WhatsApp.
- [src/bolao/ui_ranking.py](file:///C:/dev/BolaoCopaSanca/src/bolao/ui_ranking.py): Abas unificadas para Ranking Clássico, Ranking Jogo a Jogo, Ranking Geral (Combinado) e Estatísticas detalhadas.
- [src/bolao/ui_live_matches.py](file:///C:/dev/BolaoCopaSanca/src/bolao/ui_live_matches.py): Dashboard do Jogo a Jogo com contagem regressiva, Match Center integrado, simulador de impacto de placares no ranking e termômetro do grupo.
- [src/bolao/ui_cartela.py](file:///C:/dev/BolaoCopaSanca/src/bolao/ui_cartela.py): Minha Cartela expandida para agrupar ambos os modos e comparação direta com amigos.
- [src/bolao/ui_social_pages.py](file:///C:/dev/BolaoCopaSanca/src/bolao/ui_social_pages.py): Controle modular de páginas sociais estáticas e analíticas.
- [src/bolao/simulator_engine.py](file:///C:/dev/BolaoCopaSanca/src/bolao/simulator_engine.py): Ajuste no `normalize_slots` e tratamento seguro de leitura com `.get()` para prevenir o erro `KeyError: 0`.

---

## 3. Backups Criados e Histórico
Antes de qualquer alteração de dados, a migração inicial aciona automaticamente a geração de um backup local estruturado.
- **Localização dos Backups**: `data/backups/`
- **Exemplo de Pasta**: `data/backups/backup_before_public_analytics_live_parallel_YYYYMMDD_HHMMSS/`
- **Conteúdo**: Arquivos JSON clonados de persistência (`submissions`, `official`, `config`, `events`, `matches`, `live_predictions`) e um `backup_manifest.json` com estatísticas do bolão, branch do git, hash de commit e o tipo de storage ativo.

---

## 4. Como Jogar em Cada Modo

### A. Participante só Clássico
1. O usuário entra no menu lateral e escolhe **Palpite Clássico**.
2. Preenche a simulação completa da Copa e confirma.
3. Seus dados aparecerão na aba **Ranking Clássico** e na aba **Minha Cartela**.

### B. Participante só Jogo a Jogo
1. O usuário acessa **Jogos de Hoje** e informa seu nome para identificação.
2. Não há necessidade de preencher o simulador completo (é opcional).
3. Palpita individualmente em cada partida até 10 minutos antes do início do jogo.
4. Seus dados e aproveitamento aparecerão no **Ranking Jogo a Jogo** e na aba **Minha Cartela** (com aviso de que o modo clássico é opcional).

### C. Participante em Ambos os Modos
1. Preenche o **Palpite Clássico** e depois identifica-se em **Jogos de Hoje** usando o mesmo nome ou código de confirmação.
2. O sistema sincroniza as participações, listando o usuário em todos os rankings e exibições conjuntas de cartela.

---

## 5. Funcionamento do Ranking Geral (Combinado)
Se ativado pelo administrador, o Ranking Geral pondera as notas dos dois modos:
- **Fórmula**: `Pontuação Geral = (Pontos Clássico * Peso Clássico) + (Pontos Jogo a Jogo * Peso Jogo a Jogo)`
- **Estratégia para Ausência**: Se o jogador participa de apenas um modo, sua pontuação no outro modo conta como zero (ou conforme configurado) sem travar a renderização das tabelas.

---

## 6. Políticas de Privacidade e Bloqueio
- **Palpites Clássicos**: Ficam totalmente ocultos do grupo até que o administrador feche as inscrições gerais do bolão clássico.
- **Palpites Jogo a Jogo**: Ficam trancados individualmente por jogo 10 minutos antes do início de cada partida. Após o trancamento, o Match Center revela as previsões individuais e os termômetros percentuais do grupo.
- **Segurança de Código**: Os códigos de confirmação completos são ocultados das exibições e relatórios públicos.

---

## 7. Controle do Modo Escuro Premium ("Noite de Estádio")
- **Seletor**: Localizado no menu lateral (“☀️ Claro | 🌙 Escuro | Sistema”).
- **Estética**: Tons de verde petróleo e oliva escuro com gradientes sutis, glow dourado no pódio do líder e campeão da Copa, botões verdes brilhantes de alto contraste e legibilidade acessível no mobile.
- A persistência é gerenciada na sessão do usuário (`st.session_state["theme_mode"]`).

---

## 8. Procedimento de Restauração de Backup
Caso seja necessária uma restauração manual:
1. Vá até a pasta `data/backups/` e identifique a pasta do backup desejado.
2. Copie os arquivos JSON (`submissions.json`, `config.json`, `matches.json`, `live_predictions.json`, etc.) de dentro da pasta `state` (ou similar) do backup.
3. Cole-os na pasta ativa de estado do projeto: `data/state/` (substituindo os arquivos atuais).
4. Reinicie a aplicação streamlit.

# Correção do OCR dos grupos do ge

Esta versão troca a leitura principal dos grupos por uma leitura especializada para os prints do simulador do ge.

## O que mudou

Antes, o sistema tentava ler o print inteiro com OCR textual. Em screenshots com 6 cards lado a lado, o Tesseract misturava colunas e grupos, gerando seleções repetidas ou grupos vazios.

Agora, para os grupos A-F e G-L, o sistema:

1. detecta as linhas horizontais dos cards;
2. divide o print em 3 colunas por 2 linhas;
3. usa a ordem fixa dos times no card do ge;
4. lê a cor de cada linha para identificar a posição escolhida:
   - roxo = 1º;
   - vinho/rosa = 2º;
   - ocre = 3º classificado;
   - cinza = restante do grupo;
5. preenche 3º/4º pela ordem visual quando o ge deixa duas linhas cinzas;
6. mantém o Tesseract apenas como fallback e diagnóstico.

## Resultado esperado nos prints de teste

A-F:

- Grupo A: México, África do Sul, Coreia do Sul, Rep. Tcheca
- Grupo B: Canadá, Bósnia, Catar, Suíça
- Grupo C: Brasil, Marrocos, Haiti, Escócia
- Grupo D: EUA, Paraguai, Austrália, Turquia
- Grupo E: Alemanha, Curaçao, Costa do Marfim, Equador
- Grupo F: Holanda, Japão, Suécia, Tunísia

G-L:

- Grupo G: Bélgica, Egito, Irã, Nova Zelândia
- Grupo H: Espanha, Cabo Verde, Arábia Saudita, Uruguai
- Grupo I: França, Senegal, Iraque, Noruega
- Grupo J: Argentina, Argélia, Áustria, Jordânia
- Grupo K: Portugal, RD Congo, Uzbequistão, Colômbia
- Grupo L: Inglaterra, Croácia, Gana, Panamá

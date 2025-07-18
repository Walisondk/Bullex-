# Bot WALISON para IQ Option

## Descrição
Este bot automatizado para IQ Option foi desenvolvido para realizar operações de forma inteligente, seguindo estratégias de análise técnica e sempre respeitando a tendência do mercado. O bot utiliza múltiplos indicadores para confirmar a direção das operações, aumentando significativamente a taxa de acertos.

## Características Principais
- **Verificação de Tendência Obrigatória**: Utiliza médias móveis e RSI para confirmar a tendência antes de realizar operações
- **Múltiplas Estratégias**: MHI, MHI2, MHI3, Milhão e Padrão 3 Velas (com variantes de maioria/minoria)
- **Gerenciamento de Risco**: Suporte a martingale e soros para gerenciamento de capital
- **Modo Automático**: Seleciona automaticamente a melhor estratégia com base na análise de assertividade
- **Compatibilidade**: Funciona com opções binárias e digitais

## Requisitos
- Python 3.6 ou superior
- Conta na IQ Option
- Pacotes Python: iqoptionapi, configobj, tabulate, colorama, numpy

## Configuração
Edite o arquivo `config.txt` com suas informações:

```
[LOGIN]
email = seu_email@exemplo.com
senha = sua_senha

[AJUSTES]
valor_entrada = 5
tipo = automatico
stop_win = 100
stop_loss = 100
velas_medias = 10
pay_minimo = 70

[MARTINGALE]
usar_martingale = S
niveis_martingale = 2
fator_martingale = 2
proximo_sinal = S

[SOROS]
usar_soros = N
niveis_soros = 2
```

## Como Usar
1. Configure o arquivo `config.txt` com suas credenciais
2. Execute o bot com o comando: `python bot.py`
3. Selecione o tipo de conta (Demo ou Real)
4. Escolha a estratégia desejada ou use o modo automático
5. O bot começará a operar automaticamente seguindo a estratégia escolhida

## Estratégias Disponíveis

### MHI (Maioria/Minoria)
Analisa as últimas 3 velas para identificar padrões de maioria ou minoria.

### MHI2 (Maioria/Minoria)
Similar ao MHI, mas analisa velas em posições diferentes.

### MHI3 (Maioria/Minoria)
Terceira variação do MHI, com análise de velas em posições específicas.

### Milhão (Maioria/Minoria)
Estratégia baseada em sequências de velas da mesma cor.

### Padrão 3 Velas (Maioria/Minoria)
Nova estratégia que identifica padrões de continuidade (3 velas consecutivas da mesma cor) e padrões de reversão (2 velas de uma cor seguidas por 1 vela forte da cor oposta).

## Verificação de Tendência
O bot utiliza dois indicadores para confirmar a tendência:

1. **Médias Móveis**: Calcula a média dos preços de fechamento e compara com o preço atual
2. **RSI (Índice de Força Relativa)**: Analisa se o ativo está sobrecomprado (RSI > 70) ou sobrevendido (RSI < 30)

Uma operação só é realizada quando ambos os indicadores concordam com a direção, aumentando significativamente a taxa de acertos.

## Dicas de Uso
- Comece com uma conta demo para testar as estratégias
- Defina valores adequados de stop win e stop loss
- O modo automático geralmente oferece os melhores resultados
- Para maior segurança, use valores baixos de martingale (1 ou 2 níveis)
- Monitore o desempenho e ajuste as configurações conforme necessário

## Aviso de Risco
Opções binárias e digitais envolvem alto risco. Este bot não garante lucros e deve ser usado com responsabilidade. Nunca invista dinheiro que não pode perder.

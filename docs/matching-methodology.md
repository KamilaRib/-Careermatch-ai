# Metodologia de compatibilidade

> Status: especificação. A implementação e os testes entram na Fase 4.

## Princípio
A IA **interpreta** (extrai requisitos da vaga, classifica e associa evidências do currículo). O backend **calcula** o score de forma determinística: mesma entrada, mesmo resultado.

## Pesos iniciais

| Categoria | Peso |
|---|---:|
| Competências técnicas | 30% |
| Experiência profissional | 25% |
| Requisitos obrigatórios | 20% |
| Formação e certificações | 10% |
| Competências comportamentais | 10% |
| Palavras-chave | 5% |

## Estados de correspondência e crédito

| Estado | Crédito | Observação |
|---|---:|---|
| Atendido | 1.0 | Precisa ter evidência textual |
| Parcialmente atendido | 0.5 | Ex.: tecnologia correlata, tempo menor que o exigido |
| Não identificado | 0.0 | Ausência de evidência **não** equivale a ausência de competência; aparece como "não comprovado" |
| Não atendido | 0.0 | Só quando há contradição comprovável |
| Não avaliável | excluído | Sai do denominador |

## Cálculo
1. Cada requisito pertence a **uma** categoria primária (sem dupla contagem). Os obrigatórios entram em "Requisitos obrigatórios"; as demais categorias ficam com os desejáveis e contextuais.
2. Score da categoria = média ponderada dos créditos (obrigatório 1.0, desejável 0.6, contextual 0.3).
3. Categorias sem requisitos avaliáveis são removidas e os pesos restantes são **renormalizados** para somar 100%.
4. Score final = Σ(score da categoria × peso normalizado), arredondado para um inteiro de 0 a 100.
5. Requisitos **eliminatórios explícitos** não atendidos ou não identificados aparecem em um alerta separado e não alteram o número.

## Faixas
0–39: baixa · 40–59: parcial · 60–79: boa · 80–100: alta.

O score é uma estimativa interna de compatibilidade, **não** uma probabilidade de contratação.

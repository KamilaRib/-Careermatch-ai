# Metodologia de Compatibilidade ATS (Implementada — Fases 4 e 5)

> **Status:** Implementado e validado em `backend/app/services/matching_engine.py` e `backend/tests/test_matching.py`.

## Princípio Fundamental
A camada de IA (ou o parser determinístico) **interpreta e estrutura** os requisitos da vaga e os dados do currículo com citações literais (`evidence_quote`). O motor de compatibilidade (`matching_engine.py`) **calcula** o score de forma 100% determinística: mesma entrada, mesmo resultado. O modelo de linguagem nunca inventa ou atribui pontuações.

## Pesos Base por Categoria

| Categoria | Peso Base |
|---|---:|
| Competências técnicas | 30% |
| Experiência profissional | 25% |
| Requisitos obrigatórios | 20% |
| Formação e certificações | 10% |
| Competências comportamentais | 10% |
| Palavras-chave | 5% |

## Estados de Correspondência e Crédito

| Estado | Crédito | Regra Determinística |
|---|---:|---|
| **Atendido** (`atendido`) | `1.0` | Exige evidência textual direta no currículo confirmado (ou sinônimo canônico exato, ex.: `PostgreSQL` / `Postgres`, `Node.js` / `NodeJS`). |
| **Parcialmente atendido** (`parcialmente_atendido`) | `0.5` | Aplicável apenas quando um requisito composto possui parte das tecnologias comprovadas no currículo (ex.: vaga pede `"Kubernetes e AWS"` e o currículo comprova `"AWS"`) ou quando o tempo de experiência é $\ge 60\%$ do solicitado. |
| **Não identificado** (`nao_identificado`) | `0.0` | Ausência de evidência textual no currículo. **Nunca** é tratada como prova de que o candidato não possui a competência, apenas como "não comprovado no documento". |
| **Não atendido** (`nao_atendido`) | `0.0` | Apenas quando há contradição objetiva comprovável (ex.: vaga exige 8 anos e o currículo comprova 2 anos). |
| **Não avaliável** (`nao_avaliavel`) | excluído | Requisitos subjetivos ou sem critério verificável por texto saem do denominador. |

> **Regra Estrita sobre Tecnologias Correlatas:** Experiência em tecnologias do mesmo ecossistema (ex.: `Docker` e `AWS` quando a vaga exige `Kubernetes`) **nunca** concede pontuação parcial (`0.5`) nem é registrada como evidência da competência exigida. Tecnologias correlatas são utilizadas exclusivamente para gerar **recomendações consultivas** na seção `recommendations`.

## Cálculo e Renormalização
1. Cada requisito pertence a **uma única** categoria primária (sem dupla contagem).
2. Score da categoria = média ponderada dos créditos pelos pesos de importância (`obrigatorio: 1.0`, `desejavel: 0.6`, `contextual: 0.3`, `nao_especificado: 0.5`).
3. Categorias sem requisitos avaliáveis são marcadas como `applicable: false` e os pesos das categorias aplicáveis são **renormalizados proporcionalmente** para somar `100%`.
4. Score final = $\sum(\text{score da categoria} \times \text{peso normalizado})$, arredondado para inteiro de `0` a `100`.
5. Requisitos **eliminatórios explícitos** não atendidos disparam alertas destacados em `eliminatory_alerts`.

## Faixas de Interpretação
- **80–100%:** Alta compatibilidade (`alta_compatibilidade`)
- **60–79%:** Boa compatibilidade (`boa_compatibilidade`)
- **40–59%:** Compatibilidade parcial (`compatibilidade_parcial`)
- **0–39%:** Baixa compatibilidade (`baixa_compatibilidade`)

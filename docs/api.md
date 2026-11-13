# API REST: v1

Base: `/api/v1`. A documentação interativa (OpenAPI/Swagger) fica em `/api/docs`.

## Convenções de Segurança

- **Sessão Anônima:** criada automaticamente no primeiro request (cookie `cm_session`, `HttpOnly`, `SameSite=Lax`, `Secure` em produção). Nenhum dado é compartilhado entre sessões.
- **CSRF Double-Submit:** requisições mutáveis (`POST`, `PUT`, `DELETE`) exigem o header `X-CSRF-Token` com o mesmo valor do cookie `cm_csrf` (comparação em tempo constante com `hmac.compare_digest`). Sem ele, a resposta é `403 csrf_failed`.
- **Erros Padronizados:**
  ```json
  { "error": { "code": "validation_error", "message": "Dados inválidos.", "details": [] } }
  ```
- **Rate Limit:** `429 rate_limited` com header `Retry-After`. Endpoints que acionam processamento de IA possuem bucket dedicado (`RATE_LIMIT_AI_PER_MINUTE`).
- **Limite de Payload:** verificado em streaming (`BodySizeLimitMiddleware`); requisições acima do limite retornam `413 payload_too_large`.

## Endpoints Implementados (Fases 1 a 5)

| Método | Rota | Fase | Descrição |
|---|---|---:|---|
| `GET` | `/api/v1/health` | 1 | Status da API, provedor de IA ativo (`ollama`, `gemini`, `openai`) e alertas de configuração |
| `GET` | `/api/v1/sessions/current` | 1 | Inicializa ou consulta a sessão anônima temporária |
| `DELETE` | `/api/v1/sessions/current` | 1 | Apaga imediatamente todos os dados da sessão na memória e expira os cookies (LGPD) |
| `POST` | `/api/v1/resumes/upload` | 2 | Upload seguro de currículo (`PDF`, `DOCX`, `TXT`) com inspeção por magic bytes e bloqueio de macros/JS |
| `POST` | `/api/v1/resumes/parse` | 2 | Estruturação do currículo (Ollama local + fallback determinístico) e validação literal de evidências |
| `GET` | `/api/v1/resumes/current` | 2 | Retorna o currículo estruturado e seu estado de confirmação na sessão |
| `PUT` | `/api/v1/resumes/current` | 2 | Salva edições revisadas pelo usuário e confirma o currículo (`confirmed=true`) |
| `POST` | `/api/v1/jobs/parse` | 3 | Analisa descrição de vaga colada e classifica requisitos (`obrigatorio`, `desejavel`, `contextual`, `nao_especificado`) |
| `POST` | `/api/v1/jobs/extract-url` | 3 | Extrai texto de vaga a partir de URL pública com proteção anti-SSRF (`ssrf_guard.py`) |
| `GET` | `/api/v1/jobs/current` | 3 | Retorna os dados e requisitos da vaga atual da sessão |
| `PUT` | `/api/v1/jobs/current` | 3 | Salva os requisitos revisados pelo usuário e confirma a vaga (`confirmed=true`) |
| `POST` | `/api/v1/matching/analyze` | 4 | Calcula o score determinístico de compatibilidade ATS, pesos renormalizados, evidências e lacunas |
| `GET` | `/api/v1/matching/current` | 4 | Retorna o último resultado de compatibilidade ATS da sessão |
| `POST` | `/api/v1/ats-resume/generate` | 5 | Gera currículo ATS otimizado com guardião anti-fabricação, histórico de alterações e sugestões |
| `GET` | `/api/v1/ats-resume/current` | 5 | Retorna o currículo ATS otimizado atual da sessão |
| `PUT` | `/api/v1/ats-resume/current` | 5 | Salva ajustes manuais e registra a aprovação humana (`approved=true`) |
| `GET` | `/api/v1/ats-resume/export/{fmt}` | 5 | Exporta o currículo ATS aprovado em `pdf`, `docx`, `txt` ou `md` |

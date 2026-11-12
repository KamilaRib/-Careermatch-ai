# API REST: v1

Base: `/api/v1`. A documentação interativa (OpenAPI) fica em `/api/docs`.

## Convenções

- **Sessão:** criada automaticamente no primeiro request (cookie `cm_session`, HttpOnly).
- **CSRF:** requisições `POST`/`DELETE` precisam do header `X-CSRF-Token` com o valor do cookie `cm_csrf`. Sem ele, a resposta é `403 csrf_failed`.
- **Erros:** sempre no formato
  ```json
  { "error": { "code": "validation_error", "message": "Dados inválidos.", "details": [] } }
  ```
- **Rate limit:** `429 rate_limited` com header `Retry-After`. Os endpoints de IA têm limite próprio.
- **Payload:** acima do limite configurado, a resposta é `413 payload_too_large`.

## Endpoints implementados (Fase 1)

### `GET /health`
```json
{ "status": "ok", "version": "0.1.0", "environment": "development", "ai_provider": "gemini", "ai_configured": true }
```

### `GET /sessions/current`
Inicializa ou consulta a sessão anônima.
```json
{ "active": true, "ttl_minutes": 60 }
```

### `DELETE /sessions/current`
Apaga todos os dados da sessão e remove os cookies.
```bash
curl -X DELETE http://localhost:8000/api/v1/sessions/current \
  -b "cm_session=...; cm_csrf=TOKEN" -H "X-CSRF-Token: TOKEN"
```
```json
{ "deleted": true }
```

## Endpoints planejados

| Método | Rota | Fase |
|---|---|---|
| POST | `/resumes/upload` | 2 |
| POST | `/resumes/parse` | 2 |
| POST | `/jobs/parse` | 3 |
| POST | `/jobs/extract-url` | 3 |
| POST | `/matching/analyze` | 4 |
| POST | `/resumes/optimize` | 5 |
| POST | `/resumes/validate` | 5 |
| POST | `/resumes/export/pdf` | 5 |
| POST | `/resumes/export/docx` | 5 |
| POST | `/assistant/chat` | 6 |

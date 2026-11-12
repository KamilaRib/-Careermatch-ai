# Privacidade e tratamento de dados

Alinhado aos princípios da LGPD (Lei 13.709/2018): finalidade, necessidade, transparência, segurança e prevenção.

## Dados tratados
- Conteúdo do currículo enviado (texto extraído e dados estruturados).
- Descrição da vaga.
- Histórico do assistente na sessão.

**Finalidade única:** análise de compatibilidade e geração do currículo ajustado, a pedido do próprio usuário.

## Sessões e retenção
- Não tem conta nem login. Cada visitante recebe um identificador aleatório (256 bits) em cookie HttpOnly.
- Os dados ficam **apenas em memória** no servidor e não vão para disco nem para banco.
- A sessão expira após `SESSION_TTL_MINUTES` (padrão: 60) de inatividade. Uma rotina periódica remove as sessões expiradas.
- O usuário pode apagar tudo na hora (ícone de lixeira, que chama `DELETE /api/v1/sessions/current`).
- Os arquivos enviados são processados em memória e descartados. Os documentos exportados são gerados sob demanda e não ficam armazenados.
- Sessões são isoladas: nenhum dado é compartilhado entre elas.

## Provedores de IA
O texto do currículo e da vaga é enviado ao provedor configurado pelo operador (Google Gemini ou OpenAI) para estruturação e otimização. Esses provedores têm políticas próprias de uso e retenção de dados. O operador deve escolher planos e configurações compatíveis com a LGPD e informar isso aos usuários. A interface mostra esse aviso na página **Privacidade**.

## Logs
São registradas apenas métricas técnicas: rota (sem query string), status, duração, tipo de erro. **Nunca** entram nos logs conteúdo de currículos, prompts, e-mails, telefones, cookies ou chaves de API. O formatter de log ainda redige chaves sensíveis por precaução.

## Segurança
CORS restritivo, CSRF, rate limiting, limites de payload, headers de segurança, validação de arquivos, proteção contra SSRF e prompt injection, e mensagens de erro sem detalhes internos.

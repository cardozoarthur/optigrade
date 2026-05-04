# OptiGrade Kubernetes

Deploy do piloto em Kubernetes com Traefik e cert-manager.

## Componentes

- `optigrade-postgres`: PostgreSQL com pgvector e PVC local-path.
- `optigrade-api`: FastAPI, migrações Alembic e seed inicial em init container.
- `optigrade-web`: Next.js standalone com Better Auth e BFF interno.
- `optgrade.digital-directive.com`: Ingress Traefik com TLS via `letsencrypt-production`.

## Secret esperado

O Secret `optigrade-secrets` nao fica versionado. Ele deve conter:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `DATABASE_URL`
- `BETTER_AUTH_DATABASE_URL`
- `BETTER_AUTH_SECRET`
- `OPTIGRADE_INTERNAL_API_SECRET`

`DATABASE_URL` usa o driver SQLAlchemy/psycopg para a API.
`BETTER_AUTH_DATABASE_URL` usa a URL PostgreSQL padrao para o Better Auth.

O ConfigMap define `OPTIGRADE_REQUIRE_INTERNAL_SECRET=true`; sem
`OPTIGRADE_INTERNAL_API_SECRET`, a API responde 503 para rotas que nao sejam
`/health`. Isso evita que a API interna aceite trafego direto sem passar pelo
BFF autenticado.

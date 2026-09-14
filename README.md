# FinZen - Backend

Backend de **FinZen**, la app de finanzas personales con consultas inteligentes (IA).
Está compuesto por **4 microservicios** en Python (FastAPI), cada uno con **su propia base de datos SQLite** (patrón database-per-microservice).

## Microservicios

| Microservicio | Puerto | Base de datos | Responsabilidad |
|---|---|---|---|
| `user-service` | 8001 | `users.db` | Registro, login y perfil (HU1, HU6) |
| `income-service` | 8002 | `incomes.db` | Registro y consulta de ingresos (HU2, HU4) |
| `expense-service` | 8003 | `expenses.db` | Registro y consulta de gastos (HU3, HU5) |
| `ai-service` | 8004 | `vectors.db` | Vectorización y consultas con IA (HU7) |

## Ejecutar en local (sin Docker)

```bash
./scripts/start_local.sh     # levanta los 4 servicios
./scripts/stop_local.sh      # los detiene
```

Cada servicio expone su documentación interactiva (Swagger) en `http://localhost:PUERTO/docs`.

## Ejecutar con Docker Compose

```bash
cp .env.example .env         # configura OPENAI_API_KEY y SECRET_KEY (opcional)
docker compose up --build    # levanta los 4 servicios + Nginx
```

Con Nginx, las APIs quedan publicadas como:

- `http://localhost/api/users/...`
- `http://localhost/api/incomes/...`
- `http://localhost/api/expenses/...`
- `http://localhost/api/ai/...`

## Autenticación

Los endpoints protegidos requieren el encabezado `Authorization: Bearer <token>`,
donde el token se obtiene en `POST /auth/login`. El `user-service` lo emite y los
demás servicios lo verifican con el mismo `SECRET_KEY`.

> Los montos se devuelven como **string** (por ejemplo `"450.50"`) porque se
> modelan con `Decimal`/`Numeric(12,2)` para no perder precisión financiera.

## Endpoints principales

**user-service**
- `POST /users` - registrar usuario
- `POST /auth/login` - iniciar sesión
- `GET /users/{user_id}` - obtener perfil
- `PUT /users/{user_id}` - actualizar perfil

**income-service**
- `POST /incomes` - registrar ingreso
- `GET /incomes/{user_id}` - listar ingresos
- `GET /incomes/detail/{income_id}` - detalle de un ingreso
- `DELETE /incomes/{income_id}` - eliminar un ingreso

**expense-service**
- `POST /expenses` - registrar gasto
- `GET /expenses/{user_id}` - listar gastos (filtros `category`, `date_from`, `date_to`)
- `GET /expenses/detail/{expense_id}` - detalle de un gasto
- `GET /expenses/categories/list` - catálogo de categorías

**ai-service**
- `POST /vectorize` - vectorizar un movimiento (uso interno)
- `POST /query` - consulta en lenguaje natural

## Variables de entorno

| Variable | Servicio | Descripción |
|---|---|---|
| `DB_PATH` | todos | Ruta del archivo SQLite propio |
| `SECRET_KEY` | todos | Secreto para firmar y verificar los tokens JWT (debe ser el mismo) |
| `ALLOWED_ORIGINS` | todos | Orígenes permitidos por CORS, separados por coma |
| `AI_SERVICE_URL` | income/expense | URL del ai-service para vectorizar |
| `OPENAI_API_KEY` | ai-service | Clave de OpenAI (si no está, usa modo local) |
| `EMBEDDING_MODEL` | ai-service | Modelo de embeddings (por defecto `text-embedding-3-large`) |
| `CHAT_MODEL` | ai-service | Modelo de chat para redactar la respuesta |

## Notas

- Si no se configura `OPENAI_API_KEY`, el `ai-service` funciona en **modo local** con un embedding
  determinista (bolsa de palabras), para poder probar el flujo completo sin conexión.
- Los datos de cada servicio se guardan en su propio volumen cuando se usa Docker.

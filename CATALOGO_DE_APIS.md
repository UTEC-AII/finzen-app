# Catálogo de APIs — FinZen (Backend)

Documentación de todos los endpoints de los 4 microservicios de FinZen.
Cada servicio tiene su propia base de datos SQLite y se publica a través de **Nginx**
(reverse proxy) en el puerto `80`.

- **Base URL local (Docker):** `http://localhost`
- **Base URL AWS:** `http://<TU-IP-ELASTICA>`
- **Formato:** JSON (`Content-Type: application/json`)
- **Autenticación:** `Authorization: Bearer <token>` (excepto registro y login)
- **Documentación interactiva:** Swagger de cada servicio en `http://localhost:8001/docs`, `:8002/docs`, `:8003/docs`, `:8004/docs`

## Códigos de estado

| Código | Significado |
|---|---|
| 200 | OK |
| 201 | Creado |
| 204 | Sin contenido (borrado) |
| 400 | Datos inválidos |
| 401 | No autenticado (token ausente/inválido) |
| 403 | No autorizado (el recurso no es del usuario) |
| 404 | No encontrado |
| 409 | Conflicto (correo ya registrado) |
| 422 | Error de validación |

---

## 1. `user-service` (puerto 8001 · `users.db`)

| Método | Ruta pública (Nginx) | Ruta interna | Auth | Descripción |
|---|---|---|---|---|
| POST | `/api/users/users` | `/users` | No | Registrar usuario |
| POST | `/api/users/auth/login` | `/auth/login` | No | Iniciar sesión (devuelve JWT) |
| GET | `/api/users/users/{id}` | `/users/{id}` | Sí | Obtener perfil |
| PUT | `/api/users/users/{id}` | `/users/{id}` | Sí | Actualizar perfil |
| GET | `/api/users/health` | `/health` | No | Estado del servicio |

**Registrar usuario** — `POST /api/users/users`
```json
{
  "name": "Demo",
  "email": "demo@test.com",
  "password": "secreto123",
  "preferred_currency": "PEN",
  "timezone": "America/Lima"
}
```
Respuesta `201`:
```json
{
  "id": "…",
  "name": "Demo",
  "email": "demo@test.com",
  "preferred_currency": "PEN",
  "timezone": "America/Lima",
  "monthly_savings_goal": "0.00",
  "created_at": "2026-09-14T…"
}
```

**Login** — `POST /api/users/auth/login`
```json
{ "email": "demo@test.com", "password": "secreto123" }
```
Respuesta `200`:
```json
{ "access_token": "eyJ…", "token_type": "bearer", "user": { "id": "…", "name": "Demo", "…": "…" } }
```

**Actualizar perfil** — `PUT /api/users/users/{id}` (solo campos enviados)
```json
{ "name": "Demo 2", "preferred_currency": "USD", "timezone": "America/Lima", "monthly_savings_goal": "100.00" }
```

> Los montos viajan como **string** (Decimal serializado) para no perder precisión.

---

## 2. `income-service` (puerto 8002 · `incomes.db`)

| Método | Ruta pública (Nginx) | Ruta interna | Auth | Descripción |
|---|---|---|---|---|
| POST | `/api/incomes/incomes` | `/incomes` | Sí | Registrar ingreso |
| GET | `/api/incomes/incomes/{user_id}` | `/incomes/{user_id}` | Sí | Listar ingresos |
| GET | `/api/incomes/incomes/detail/{id}` | `/incomes/detail/{id}` | Sí | Detalle de un ingreso |
| DELETE | `/api/incomes/incomes/{id}` | `/incomes/{id}` | Sí | Eliminar ingreso |
| GET | `/api/incomes/health` | `/health` | No | Estado del servicio |

**Registrar ingreso** — `POST /api/incomes/incomes`
```json
{
  "user_id": "<id>",
  "type": "Sueldo",
  "amount": "3500.50",
  "currency": "PEN",
  "date": "2026-09-01",
  "description": "Sueldo de setiembre"
}
```
Tipos válidos: `Sueldo`, `Freelance`, `Bono`, `Inversion`, `Otro`.

---

## 3. `expense-service` (puerto 8003 · `expenses.db`)

| Método | Ruta pública (Nginx) | Ruta interna | Auth | Descripción |
|---|---|---|---|---|
| POST | `/api/expenses/expenses` | `/expenses` | Sí | Registrar gasto |
| GET | `/api/expenses/expenses/{user_id}` | `/expenses/{user_id}` | Sí | Listar gastos (filtros) |
| GET | `/api/expenses/expenses/detail/{id}` | `/expenses/detail/{id}` | Sí | Detalle de un gasto |
| DELETE | `/api/expenses/expenses/{id}` | `/expenses/{id}` | Sí | Eliminar gasto |
| GET | `/api/expenses/expenses/categories/list` | `/expenses/categories/list` | Sí | Catálogo de categorías |
| GET | `/api/expenses/health` | `/health` | No | Estado del servicio |

**Registrar gasto** — `POST /api/expenses/expenses`
```json
{
  "user_id": "<id>",
  "category": "Alimentacion",
  "amount": "450.50",
  "currency": "PEN",
  "date": "2026-09-05",
  "description": "Supermercado"
}
```
Categorías: `Alimentacion`, `Transporte`, `Vivienda`, `Entretenimiento`, `Salud`, `Educacion`, `Ropa`, `Otros`.

**Filtros** — `GET /api/expenses/expenses/{user_id}?category=Alimentacion&date_from=2026-09-01&date_to=2026-09-30`

---

## 4. `ai-service` (puerto 8004 · `vectors.db`)

| Método | Ruta pública (Nginx) | Ruta interna | Auth | Descripción |
|---|---|---|---|---|
| POST | `/api/ai/query` | `/query` | Sí | Consulta en lenguaje natural (RAG) |
| POST | `/api/ai/reindex` | `/reindex` | Sí | Re-indexar movimientos |
| GET | `/api/ai/settings/openai-key` | `/settings/openai-key` | Sí | Estado de la clave de OpenAI |
| PUT | `/api/ai/settings/openai-key` | `/settings/openai-key` | Sí | Guardar la clave de OpenAI |
| DELETE | `/api/ai/settings/openai-key` | `/settings/openai-key` | Sí | Borrar la clave de OpenAI |
| POST | `/api/ai/vectorize` | `/vectorize` | No | Vectorizar un movimiento (interno) |
| DELETE | `/api/ai/vectors/{id}` | `/vectors/{id}` | No | Borrar un vector (interno) |
| GET | `/api/ai/health` | `/health` | No | Estado del servicio |

**Consulta** — `POST /api/ai/query`
```json
{ "user_id": "<id>", "question": "¿En qué categoría gasto más?", "timezone": "America/Lima" }
```
Respuesta `200`:
```json
{
  "answer": "Tu mayor gasto está en Alimentacion…",
  "matched_records": 5,
  "sources": [ { "id": "…", "text": "Gasto de 450.50 PEN en Alimentacion el 2026-09-05 (Supermercado)" } ]
}
```

**Re-indexar** — `POST /api/ai/reindex` → `{ "reindexed": 5, "model": "text-embedding-3-large" }`

**Estado de la clave** — `GET /api/ai/settings/openai-key` → `{ "configured": true, "masked": "sk-••••••abcd" }`

> **Nota:** `POST /vectorize` y `DELETE /vectors/{id}` son **internos** (los llaman
> income/expense). El resto requiere el JWT del usuario.

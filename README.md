# FinZen — Backend (Microservicios)

[![Python](https://img.shields.io/badge/Python-3--slim-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Nginx](https://img.shields.io/badge/Nginx-Reverse%20Proxy-009639?logo=nginx&logoColor=white)](https://nginx.org/)
[![AWS](https://img.shields.io/badge/AWS-EC2-FF9900?logo=amazonaws&logoColor=white)](https://aws.amazon.com/ec2/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Nota de arquitectura:** este repositorio contiene el **backend** de FinZen.
> El cliente web (Next.js) vive en **[finzen-webui](https://github.com/UTEC-AII/finzen-webui)**.

**FinZen** es una app de finanzas personales con un asistente de IA que responde
preguntas en lenguaje natural sobre tus propias transacciones. El backend está
compuesto por **4 microservicios FastAPI**, cada uno con **su propia base de datos
SQLite**, empaquetados con **Docker** (imagen base `python:3-slim`) y publicados
detrás de un **Nginx** reverse proxy.

## Tabla de contenidos

- [Arquitectura](#arquitectura)
- [Microservicios](#microservicios)
- [Prerrequisitos](#prerrequisitos)
- [Inicio rápido (local con Docker)](#inicio-rápido-local-con-docker)
- [Variables de entorno](#variables-de-entorno)
- [Despliegue en AWS (EC2)](#despliegue-en-aws-ec2)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Catálogo de APIs](#catálogo-de-apis)
- [Problemas conocidos](#problemas-conocidos)
- [Autores y licencia](#autores-y-licencia)

## Arquitectura

```text
                          Internet
                             │
                             ▼
                  ┌────────────────────┐
                  │     Nginx  :80     │  reverse proxy
                  └─────────┬──────────┘
        ┌───────────┬───────┴────────┬────────────┐
        ▼           ▼                ▼            ▼
  /api/users   /api/incomes   /api/expenses    /api/ai
    :8001         :8002           :8003         :8004
  user-service  income-service  expense-service  ai-service
   users.db       incomes.db      expenses.db     vectors.db
```

Cada microservicio corre en su propio contenedor y usa su **propia** base SQLite
(patrón *database-per-microservice*), persistida en un volumen de Docker.

## Microservicios

| Microservicio | Puerto | Base de datos | Responsabilidad |
|---|---|---|---|
| `user-service` | 8001 | `users.db` | Registro, login (JWT) y perfil |
| `income-service` | 8002 | `incomes.db` | Registro y consulta de ingresos |
| `expense-service` | 8003 | `expenses.db` | Registro y consulta de gastos por categoría |
| `ai-service` | 8004 | `vectors.db` | Embeddings y consultas en lenguaje natural (RAG) |

## Prerrequisitos

- **Git** ≥ 2.40
- **Docker Desktop** ≥ 24 (incluye Docker Compose v2)
- *(Opcional)* **OpenAI API Key** (`sk-...`) para activar embeddings y respuestas reales

## Inicio rápido (local con Docker)

```bash
# 1. Clonar el repositorio
git clone https://github.com/UTEC-AII/finzen-app.git
cd finzen-app

# 2. Configurar variables de entorno
cp .env.example .env        # opcional: edita OPENAI_API_KEY y SECRET_KEY

# 3. Construir y levantar la arquitectura
docker compose up --build -d

# 4. Verificar que los contenedores estén sanos
docker compose ps
```

Con esto, la API queda publicada a través de Nginx en `http://localhost`:

```bash
curl http://localhost/api/users/users -X POST \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo","email":"demo@test.com","password":"secreto123","preferred_currency":"PEN"}'
```

Documentación interactiva (Swagger) de cada servicio, si se accede directo a su puerto:
`http://localhost:8001/docs`, `:8002/docs`, `:8003/docs`, `:8004/docs`.

Detener todo:

```bash
docker compose down        # conserva los volúmenes (datos)
docker compose down -v     # elimina también los datos
```

> **Imagen base:** cada microservicio parte de `python:3-slim` (la imagen liviana
> recomendada en clase), instala sus dependencias y corre Uvicorn.

## Variables de entorno

Crea un `.env` a partir de `.env.example`:

| Variable | Servicio | Descripción | Ejemplo |
|---|---|---|---|
| `SECRET_KEY` | todos | Secreto para firmar/verificar los JWT (debe ser el mismo) | `cambia-esto` |
| `ALLOWED_ORIGINS` | todos | Orígenes permitidos por CORS | `http://localhost:3000` |
| `DB_PATH` | todos | Ruta del archivo SQLite | `/app/data/users.db` |
| `AI_SERVICE_URL` | income/expense | URL interna del ai-service | `http://ai-service:8004` |
| `OPENAI_API_KEY` | ai-service | Clave de OpenAI (opcional; sin ella usa modo local) | `sk-...` |

> La clave de OpenAI también puede configurarse en tiempo de ejecución desde la
> interfaz web (se guarda en SQLite, nunca en el navegador).

## Despliegue en AWS (EC2)

> **Orden:** levanta primero este backend; el frontend se conecta a su red.

1. **Crear la instancia EC2**
   - Región: `us-east-1` (Norte de Virginia)
   - AMI: Ubuntu 24.04 LTS · Tipo: `t3.micro`
   - Asignar una **IP elástica** (para tener una IP pública fija)

2. **Configurar el Security Group** (reglas de entrada)
   - `22` (SSH) → tu IP
   - `80` (HTTP) → `0.0.0.0/0`
   - *(opcional)* `443` (HTTPS) → `0.0.0.0/0`

3. **Conectarse por SSH**

   ```bash
   ssh -i "finzen-key.pem" ubuntu@<TU-IP-ELASTICA>
   ```

4. **Instalar Docker y clonar el proyecto**

   ```bash
   sudo apt update
   sudo apt install -y git docker.io docker-compose-v2
   sudo usermod -aG docker $USER && newgrp docker

   git clone https://github.com/UTEC-AII/finzen-app.git
   cd finzen-app
   cp .env.example .env
   nano .env          # coloca tus valores reales (SECRET_KEY, OPENAI_API_KEY, ...)
   ```

5. **Levantar los contenedores**

   ```bash
   docker compose up --build -d
   docker compose ps
   ```

6. **Probar**

   ```bash
   curl http://<TU-IP-ELASTICA>/api/users/users -X POST \
     -H "Content-Type: application/json" \
     -d '{"name":"Demo","email":"demo@test.com","password":"secreto123","preferred_currency":"PEN"}'
   ```

> **Importante (Mac Apple Silicon):** las imágenes construidas en un Mac son ARM.
> Para EC2 (x86) construye con `docker buildx build --platform linux/amd64` **o**,
> más simple, construye directamente dentro de la instancia (paso 5, que ya hace
> `--build`). No uses `latest` en las imágenes base.

## Estructura del proyecto

```text
finzen-app/
├── user-service/        # FastAPI :8001 + users.db      (+ Dockerfile, requirements.txt)
├── income-service/      # FastAPI :8002 + incomes.db
├── expense-service/     # FastAPI :8003 + expenses.db
├── ai-service/          # FastAPI :8004 + vectors.db
├── nginx/
│   └── nginx.conf       # reverse proxy (/api/users, /api/incomes, /api/expenses, /api/ai)
├── scripts/
│   ├── start_local.sh   # levanta los 4 servicios sin Docker (desarrollo)
│   ├── stop_local.sh
│   └── evaluate_rag.py  # evalúa el recall del asistente
├── docker-compose.yml
├── .env.example
└── README.md
```

## Catálogo de APIs

Todas las rutas se publican a través de Nginx y requieren `Authorization: Bearer <token>`
salvo el registro y el login.

**user-service** (`/api/users`)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/users` | Registrar usuario |
| POST | `/auth/login` | Iniciar sesión (devuelve JWT) |
| GET | `/users/{id}` | Obtener perfil |
| PUT | `/users/{id}` | Actualizar perfil |

**income-service** (`/api/incomes`)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/incomes` | Registrar ingreso |
| GET | `/incomes/{user_id}` | Listar ingresos |
| GET | `/incomes/detail/{id}` | Detalle de un ingreso |
| DELETE | `/incomes/{id}` | Eliminar un ingreso |

**expense-service** (`/api/expenses`)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/expenses` | Registrar gasto |
| GET | `/expenses/{user_id}` | Listar gastos (filtros `category`, `date_from`, `date_to`) |
| GET | `/expenses/detail/{id}` | Detalle de un gasto |
| GET | `/expenses/categories/list` | Catálogo de categorías |

**ai-service** (`/api/ai`)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/query` | Consulta en lenguaje natural (RAG) |
| POST | `/reindex` | Re-indexar movimientos |
| GET/PUT/DELETE | `/settings/openai-key` | Estado / guardar / borrar la clave de OpenAI |

## Problemas conocidos

- **SQLite**: ideal para ~10 usuarios. Un solo escritor por archivo; si el proyecto
  crece a muchos usuarios concurrentes, migrar a **PostgreSQL/RDS**.
- **Auto Scaling**: con varias instancias, cada una tendría su propio SQLite; para
  producción real se necesita una base compartida.
- **ARM vs x86**: imágenes construidas en Mac no corren en EC2 x86 sin
  `--platform linux/amd64` (ver Despliegue en AWS).
- **Puerto 80 ocupado**: si ya tienes algo escuchando en el 80, cambia el mapeo en
  `docker-compose.yml` (servicio `nginx`).

## Autores y licencia

Proyecto desarrollado para el curso de **Cloud Computing** de la
**Maestría en Ciencia de Datos e Inteligencia Artificial (CDIA) — UTEC**.

- **Sebastian Garcia Villacorta** — [@sebastian-rgv](https://github.com/sebastian-rgv)

Licencia: [MIT](LICENSE).

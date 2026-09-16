# FinZen — Backend (Microservicios)

[![Python](https://img.shields.io/badge/Python-3--slim-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Nginx](https://img.shields.io/badge/Nginx-Reverse%20Proxy-009639?logo=nginx&logoColor=white)](https://nginx.org/)
[![AWS](https://img.shields.io/badge/AWS-EC2-FF9900?logo=amazonaws&logoColor=white)](https://aws.amazon.com/ec2/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Nota de arquitectura:** este repositorio contiene el **backend** de FinZen.
> El cliente web (Next.js) vive en **[finzen-webui](https://github.com/UTEC-AII/finzen-webui)**.

**FinZen** es una aplicación de finanzas personales con un asistente de IA que responde
preguntas en lenguaje natural sobre las transacciones del propio usuario. El backend está
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

> El esquema completo de las 4 bases (DBML) y su diagrama Entidad-Relación están en el
> repositorio de documentación: [finzen-docs](https://github.com/UTEC-AII/finzen-docs).

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

> `docker compose ps` lista los contenedores de **este** proyecto; `docker ps` lista
> **todos** los que están corriendo (incluido el frontend `finzen-webui` si lo levantaste).

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
| `SECRET_KEY` | todos | Secreto para firmar/verificar los JWT (HS256); debe ser **el mismo** en los 4 servicios | salida de `openssl rand -hex 32` |
| `ALLOWED_ORIGINS` | todos | Orígenes permitidos por CORS | `http://localhost:3000` |
| `DB_PATH` | todos | Ruta del archivo SQLite | `/app/data/users.db` |
| `AI_SERVICE_URL` | income/expense | URL interna del ai-service | `http://ai-service:8004` |
| `OPENAI_API_KEY` | ai-service | Clave de OpenAI (opcional; sin ella usa modo local) | `sk-...` |

> La clave de OpenAI también puede configurarse en tiempo de ejecución desde la
> interfaz web (se guarda en SQLite, nunca en el navegador).

> **`SECRET_KEY` (para qué sirve y cómo generarla):** se usa para **firmar** el JWT al
> iniciar sesión y **verificarlo** en cada petición protegida (algoritmo `HS256`). Los 4
> servicios comparten el mismo valor: `user-service` firma, y el resto verifica.
> Si alguien la conoce podría **falsificar tokens** (suplantar usuarios), así que **no
> dejes el valor de ejemplo** ni la subas al repositorio. Genérala con:
>
> ```bash
> openssl rand -hex 32      # -> 64 caracteres hexadecimales (256 bits)
> ```
>
> Al cambiarla, las sesiones activas se invalidan (los usuarios vuelven a iniciar sesión).

**Costo de la API de OpenAI (independiente de AWS):** se factura según el consumo.
Precios oficiales ([platform.openai.com/docs/pricing](https://platform.openai.com/docs/pricing),
por 1 millón de tokens): `text-embedding-3-large` $0.13 y `gpt-4o-mini` $0.15 de entrada
/ $0.60 de salida. Para el volumen estimado del proyecto (1 000 movimientos vectorizados
y 200 consultas mensuales), el costo asciende a **aproximadamente $0.04 al mes**, un
valor marginal en relación con el costo de AWS.

## Despliegue en AWS (EC2)

> **Arquitectura:** **una sola instancia EC2** con **IP elástica** (sin Application
> Load Balancer ni Auto Scaling). **Nginx** es el único punto de entrada: sirve el
> **frontend** en `/` y enruta las **APIs** en `/api/*` a los microservicios.
>
> **Orden:** levanta primero este backend; el frontend se conecta a su red de Docker.
>
> **Conexión:** usamos **EC2 Instance Connect** (terminal en el navegador), así que
> **no necesitas key pair ni `ssh -i`**.
>
> **Red (VPC / Internet Gateway):** usamos la **VPC por defecto**, que ya trae el
> **Internet Gateway** (adjunto a la VPC) y una **Route Table** con la ruta
> `0.0.0.0/0 → Internet Gateway`, sobre **subredes públicas**. Por eso, al lanzar la
> EC2 con **IP elástica** en esa VPC ya tiene internet en ambos sentidos: entrante
> (usuarios → `:80`) y saliente (`docker pull`, `git clone`, API de OpenAI).
> **No hace falta crear VPC, Internet Gateway ni NAT Gateway** (el NAT es solo para
> subredes privadas y cuesta aparte).
>
> **Almacenamiento (EBS):** las bases SQLite viven en **volúmenes de Docker**, que se
> guardan en el **volumen EBS** de la instancia (su disco). Por eso persisten al
> reiniciar o redeployar. No se crea un EBS aparte: es el disco que ya trae la EC2.
>
> **Red interna de Docker:** Docker Compose crea automáticamente una red **bridge**
> donde Nginx alcanza a los microservicios por **nombre de servicio**
> (`user-service:8001`, `income-service:8002`, `expense-service:8003`,
> `ai-service:8004`), nunca por `localhost`.

1. **Crear la instancia EC2**
   - Región: `us-east-1` (Norte de Virginia)
   - **AMI:** `Cloud9Ubuntu22` (imagen de clase: Ubuntu 22.04 con Python, Node.js, Git,
     Docker y Apache preinstalados)
   - Tipo: `t3.micro`
   - **Key pair:** ninguno → elige **“Proceed without a key pair”** (usaremos Instance Connect)
   - Almacenamiento: **20 GB, gp3**
   - Asignar una **IP elástica** (IP pública fija)

2. **Configurar el Security Group** (firewall de la instancia, reglas de entrada)
   - `22` (SSH) → `0.0.0.0/0` *(necesario para EC2 Instance Connect)*
   - `80` (HTTP) → `0.0.0.0/0` *(por aquí entra todo: Nginx publica frontend + APIs)*
   - *(opcional)* `443` (HTTPS) → `0.0.0.0/0`
   - **Salida:** All traffic → `0.0.0.0/0` (para Docker Hub, GitHub y OpenAI)

3. **Conectarse (sin SSH)**
   - Consola **EC2** → selecciona la instancia → botón **Connect** →
   - pestaña **EC2 Instance Connect** → **Connect**. Se abre una terminal en el navegador.

4. **Liberar el puerto 80 (paso obligatorio)**
   La AMI trae **Apache** ocupando el puerto 80, y **Nginx también usa el 80**. Detén y
   deshabilita Apache o Nginx no arrancará:

   ```bash
   sudo systemctl stop apache2
   sudo systemctl disable apache2
   ```

   > Si al levantar ves `failed to bind host port 0.0.0.0:80/tcp: address already in use`,
   > es Apache. Verifícalo con `sudo ss -tlnp | grep :80`.

5. **Clonar el proyecto y configurar variables**

   ```bash
   git clone https://github.com/UTEC-AII/finzen-app.git
   cd finzen-app
   cp .env.example .env
   nano .env   # SECRET_KEY (openssl rand -hex 32) y ALLOWED_ORIGINS=http://<TU-IP-ELASTICA>
   ```

6. **Levantar los contenedores**

   ```bash
   docker compose up -d --build
   docker compose ps
   ```
   Deben quedar **5** contenedores: los 4 microservicios **+ `finzen-nginx`** (publicando `80:80`).

7. **Probar el backend**

   ```bash
   curl -s http://localhost/api/ai/health
   curl -s -o /dev/null -w "%{http_code}\n" http://localhost/api/expenses/expenses/categories/list
   ```

8. **Levantar el frontend** (en la misma instancia): sigue la guía del repositorio
   [finzen-webui](https://github.com/UTEC-AII/finzen-webui#despliegue-en-aws-ec2).

9. **Abrir la app:** `http://<TU-IP-ELASTICA>` (puerto 80, servido por Nginx).

> **Importante (Mac Apple Silicon):** las imágenes construidas en un Mac son ARM.
> Para EC2 (x86) construye con `docker buildx build --platform linux/amd64` **o**,
> más simple, construye directamente dentro de la instancia (paso 6, que ya hace
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

> **Documentación y pruebas:** el catálogo de APIs, la colección de Postman y las
> evidencias están en el repositorio
> [finzen-docs](https://github.com/UTEC-AII/finzen-docs).

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

- **SQLite**: adecuada para esta escala. Un solo escritor por archivo; si el proyecto
  crece a muchos usuarios concurrentes, migrar a **PostgreSQL/RDS**.
- **Escalado**: se despliega en **una sola instancia EC2** (con IP elástica). Si se
  quisiera escalar horizontalmente (varias instancias), SQLite no bastaría —cada
  instancia tendría su propia copia—; habría que migrar a PostgreSQL y añadir un
  **load balancer**.
- **ARM vs x86**: imágenes construidas en Mac no corren en EC2 x86 sin
  `--platform linux/amd64` (ver Despliegue en AWS).
- **Puerto 80 ocupado (Apache)**: la AMI `Cloud9Ubuntu22` trae **Apache** en el puerto
  80, y Nginx también lo usa. Si al levantar ves `failed to bind host port 0.0.0.0:80/tcp:
  address already in use`, mira **qué** ocupa el puerto con `sudo ss -tlnp | grep :80`
  y detén Apache: `sudo systemctl stop apache2 && sudo systemctl disable apache2`
  (ver Despliegue en AWS, paso 4).
- **Nginx no arranca** (`host not found in upstream "user-service"`): Nginx resuelve los
  nombres de los microservicios con el **resolver de Docker**; si aun así ocurre, recréalo:
  `docker compose up -d --force-recreate nginx`.
- **Tras reiniciar la instancia EC2**: los contenedores **no arrancan solos**. Vuelve a
  levantarlos: `cd finzen-app && docker compose up -d` y, si usas el frontend,
  `docker start finzen-webui`.

## Autores y licencia

Proyecto desarrollado para el curso de **Cloud Computing (MCD8007)** de la
**Maestría en Ciencia de Datos e Inteligencia Artificial (CDIA) — UTEC**.
Docente: **Mejia Fernandez, Oscar Rodolfo**.

**Grupo 2 — Integrantes:**
- García Villacorta, Sebastian Rodrigo — [@sebastian-rgv](https://github.com/sebastian-rgv)
- Barreto Daza, Dante Guillermo
- Chulluncuy Reynoso, Clinton
- Hilario Orihuela, Ronald Ramiro

Licencia: [MIT](LICENSE).

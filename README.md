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

> El esquema completo de las 4 bases está en **`schema.dbml`** (DBML, renderizable en
> [dbdiagram.io](https://dbdiagram.io)); es la fuente del diagrama Entidad-Relación.

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

**Costo de OpenAI (aparte de AWS):** se factura según el uso. Precios oficiales
(https://platform.openai.com/docs/pricing, por 1M tokens): `text-embedding-3-large`
$0.13, `gpt-4o-mini` $0.15 entrada / $0.60 salida. Al volumen del proyecto (~1 000
movimientos + 200 consultas/mes) ronda **~$0.04/mes**, insignificante frente a AWS.

## Despliegue en AWS (EC2)

> **Arquitectura:** **una sola instancia EC2** con **IP elástica** (sin Application
> Load Balancer ni Auto Scaling), dimensionada para el volumen del proyecto. Nginx reparte
> internamente a los contenedores.
>
> **Orden:** levanta primero este backend; el frontend se conecta a su red.
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
   - **AMI:** `Cloud9Ubuntu22` (imagen pública de clase: Ubuntu con Python, Node.js, Git,
     Docker y Apache preinstalados) — o **Ubuntu 24.04 LTS** si no está disponible
   - Tipo: `t3.micro`
   - **Key pair:** ninguno (usaremos Instance Connect)
   - Asignar una **IP elástica** (IP pública fija)

2. **Configurar el Security Group** (firewall de la instancia, reglas de entrada)
   - `22` (SSH) → `0.0.0.0/0` *(necesario para EC2 Instance Connect)*
   - `80` (HTTP) → `0.0.0.0/0` *(por aquí entra todo: Nginx publica frontend + APIs)*
   - *(opcional)* `443` (HTTPS) → `0.0.0.0/0`
   - **Salida:** All traffic → `0.0.0.0/0` (para Docker Hub, GitHub y OpenAI)

3. **Conectarse (sin SSH)**
   - Consola **EC2** → selecciona la instancia → botón **Connect** →
   - pestaña **EC2 Instance Connect** → **Connect**. Se abre una terminal en el navegador.

4. **Instalar Docker (si la AMI no lo trae) y clonar el proyecto**

   ```bash
   # Con la AMI Cloud9Ubuntu22 (Ubuntu 22.04) Docker ya viene instalado; en Ubuntu limpio ejecuta:
   sudo apt update && sudo apt install -y git docker.io docker-compose-v2
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

> **¿Es necesaria la AMI `Cloud9Ubuntu22`?** No es obligatoria: como todo corre en
> **Docker**, cualquier Ubuntu sirve. `Cloud9Ubuntu22` solo ahorra el paso de instalar
> Docker/Python/Node. Si no la encuentras, usa Ubuntu 24.04 LTS y el paso 4.

### Alternativa: Ubuntu desde cero (sin la AMI `Cloud9Ubuntu22`)

Si `Cloud9Ubuntu22` no aparece en tu consola, crea la instancia con una AMI pública de
Ubuntu y prepara el entorno tú mismo:

1. **AMI:** busca **"Ubuntu Server 24.04 LTS (HVM), SSD Volume Type"**,
   arquitectura `64-bit (x86)`.
2. Tipo `t3.micro`, **sin key pair**, con **IP elástica** (igual que arriba).
3. Conéctate con **EC2 Instance Connect** (paso 3).
4. **Instala Docker desde cero:**

   ```bash
   sudo apt update
   sudo apt install -y ca-certificates curl git

   # Repositorio oficial de Docker
   sudo install -m 0755 -d /etc/apt/keyrings
   sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
   sudo chmod a+r /etc/apt/keyrings/docker.asc
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
   sudo apt update
   sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

   # Permite usar Docker sin sudo
   sudo usermod -aG docker $USER && newgrp docker

   # Verifica
   docker --version && docker compose version
   ```

   > Atajo (paquete de Ubuntu, puede ser una versión más antigua de Docker):
   > `sudo apt install -y docker.io docker-compose-v2`.

5. Continúa con el **paso 4 (clonar)** y el **paso 5 (levantar los contenedores)**.

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
├── postman/             # colección Postman + entornos + guía de evidencia
├── CATALOGO_DE_APIS.md  # documentación de todos los endpoints
├── docker-compose.yml
├── .env.example
└── README.md
```

> **Documentación de APIs:** ver [`CATALOGO_DE_APIS.md`](CATALOGO_DE_APIS.md) y la
> [colección de Postman](postman/README.md) para probar todos los endpoints.

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
- **Puerto 80 ocupado**: si ya tienes algo escuchando en el 80, cambia el mapeo en
  `docker-compose.yml` (servicio `nginx`).

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

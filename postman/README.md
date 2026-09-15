# Colección Postman — FinZen

Evidencia de uso de las APIs (Parte C del Proyecto Parcial).

## Archivos

- `FinZen.postman_collection.json` — todas las peticiones de los 4 microservicios.
- `FinZen-Local.postman_environment.json` — `baseUrl = http://localhost`.
- `FinZen-AWS.postman_environment.json` — `baseUrl = http://<TU-IP-ELASTICA>`.

## Importar

1. Abre Postman → **Import** → arrastra los 3 archivos JSON.
2. Arriba a la derecha, selecciona el entorno **FinZen - Local** (o **FinZen - AWS**).

## Flujo recomendado (orden)

1. **`1. Autenticación → Registrar usuario`** → guarda `userId`.
2. **`1. Autenticación → Login`** → guarda `token` automáticamente (lo usa toda la colección).
3. **`3. Ingresos → Registrar ingreso`**.
4. **`4. Gastos → Registrar gasto`** y **`Registrar gasto (USD)`**.
5. **`5. Asistente IA →`** las 3 consultas + reindex.
6. **`6. Limpieza (opcional) →`** elimina el ingreso y el gasto de prueba.

> El `token` y los ids se llenan solos con los *test scripts* de cada request.
> Si ejecutas el login manualmente, cambia el correo por uno que ya exista.

## Ejecución automatizada con Newman (CLI de Postman)

```bash
npm install -g newman newman-reporter-htmlextra
newman run postman/FinZen.postman_collection.json \
  -e postman/FinZen-Local.postman_environment.json \
  --delay-request 2500 \
  --reporters cli,htmlextra \
  --reporter-htmlextra-export newman-report.html
```

`--delay-request 2500` da tiempo a que los microservicios vectoricen los movimientos
(tarea en segundo plano) antes de ejecutar las consultas al asistente.

## Evidencia (capturas incluidas)

La carpeta [`evidencia/`](evidencia/) contiene las capturas de las peticiones
realizadas contra el backend en ejecución, **generadas a partir de un run real de
Newman** (registro, login, ingreso, gastos PEN/USD, listado con filtro, las 3
consultas al asistente y la re-indexación).

## Evidencia para la entrega (checklist)

Toma capturas donde se vea el **método, la URL, el body y la respuesta**:

- [ ] Registro de usuario (201).
- [ ] Login (200) devolviendo `access_token`.
- [ ] Crear ingreso (201).
- [ ] Crear gasto en PEN (201) y gasto en USD (201).
- [ ] Listar gastos con filtro por categoría (200).
- [ ] **Consulta IA 1**: "¿En qué categoría gasto más?" (200 + respuesta).
- [ ] **Consulta IA 2**: "¿Cuánto he gastado este mes?" (200).
- [ ] **Consulta IA 3**: "¿Cuánto he recibido de ingresos?" (200).
- [ ] Re-indexar movimientos (200).
- [ ] Un endpoint protegido **sin token** devolviendo **401** (opcional, muestra seguridad).

## Ejecutar la colección completa

Botón **Run** (Runner) sobre la colección y el entorno elegido. El orden ya está
pensado para que las variables se llenen correctamente.

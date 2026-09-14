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
3. **`4. Gastos → Registrar gasto`** y **`Registrar gasto (USD)`**.
4. **`3. Ingresos → Registrar ingreso`**.
5. **`5. Asistente IA →`** las 3 consultas + reindex.

> El `token` y los ids se llenan solos con los *test scripts* de cada request.
> Si ejecutas el login manualmente, cambia el correo por uno que ya exista.

## Evidencia para la entrega (capturas)

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

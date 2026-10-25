# Pruebas locales y CI

Desde la raíz del repositorio, ejecutar la suite unitaria sin credenciales:

```bash
PYTHONPATH=backend python -m unittest discover -s backend/tests/services/texts_handler -v
ruff check backend
```

## PostgreSQL aislado

```bash
docker compose -f docker-compose.test.yml -p typr-tests up --build --abort-on-container-exit --exit-code-from test-runner
docker compose -f docker-compose.test.yml -p typr-tests down --volumes --remove-orphans
```

El runner ejecuta primero los tests unitarios y después cuatro pruebas reales
contra PostgreSQL 16. Usa el esquema original, almacenamiento efímero y una red
interna sin puertos publicados; no carga `.env`, Supabase ni credenciales Gemini.
Ejecutar el segundo comando también si falla el primero.

La prueba de rollback provoca el error `Deliberate local integration failure`;
ese log PostgreSQL es esperado. Su resultado correcto imprime:
`LIVE_ROLLBACK forced_insert_error=handled session_recovery=verified`.
El resultado global válido es `OK` y código de salida 0 del runner.
Fuera de esta fixture las cuatro pruebas de integración se omiten: eso **no**
acredita que PostgreSQL haya sido probado.

## CI y cobertura mantenida

[`backend-tests.yml`](../../../.github/workflows/backend-tests.yml) usa el mismo
Compose en cada PR a `main`, push a `main` y ejecución manual. No utiliza secretos
ni despliega; limita el tiempo de ejecución y limpia los recursos incluso ante
fallo. Los jobs existentes de lint/frontend/build no cambian.

| Área | Contratos cubiertos |
|---|---|
| Validación/normalización | Idiomas, caracteres, comillas, espacios, decimales y límites |
| Clasificación | Entropía, teclado, métricas, umbrales, casos extremos y referencia congelada |
| Cadenas | Orden, ejecución única, interrupción y estado desactualizado |
| Persistencia | Parámetros SQL, duplicados, commit, rollback, aislamiento y recuperación |
| Generación | Texto intacto, errores, cierre del cliente y ausencia de efectos al importar |

Se eliminaron pruebas duplicadas, comprobaciones de antiguas ubicaciones y
aserciones sobre helpers privados; no casos funcionales para reducir una cuota.
La referencia de 16 textos y mapas de teclado se conserva sin modificar en
[`text_calibration.json`](../../../backend/tests/fixtures/text_calibration.json).
Sus hashes identifican documentos históricos disponibles en Git; ya no depende
de Markdown para ejecutar pruebas. Cambiar los criterios requiere revisar esa
referencia explícitamente, no regenerarla para ocultar regresiones. Las
comparaciones numéricas admiten tolerancia para redondeo entre versiones Python.

Gemini se simula en las pruebas: esta suite no acredita una petición real al proveedor.

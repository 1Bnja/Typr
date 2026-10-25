# Comprobar duplicados y persistir textos con SQL explícito

**Implementado con pruebas exclusivamente con mocks. No se ha conectado a
Supabase ni se han ejecutado migraciones.** Las pruebas verifican SQL, parámetros
y coordinación transaccional, no una integración real con PostgreSQL o psycopg.

## Flujo y conector existente

```text
TextFacade(db).create(content, language)
    -> Validar -> Normalizar -> Comprobar duplicado -> Clasificar -> Persistir
```

La fachada construye la cadena y llama únicamente al primer paso.
`TextFacade().process(content, language)` mantiene su flujo sin BD de tres etapas.

Se reutiliza [`app.database`](../../../backend/app/database.py): `SessionLocal`
y el proveedor `get_db()` siguen creando y cerrando las sesiones. La nueva
función `execute_sql(db, statement, parameters)` utiliza la conexión de la
transacción de esa misma sesión:

```python
return db.connection().exec_driver_sql(statement, parameters)
```

No hay otro motor, cliente o conector. Los pasos no crean ni cierran
sesiones; difieren la importación del conector hasta una operación de BD
solicitada explícitamente. Importar el módulo o ejecutar `process()` no carga
configuración ni modelos ORM.

La [documentación de ejecución directa](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Connection.exec_driver_sql)
confirma que `exec_driver_sql` envía la cadena al controlador sin compilarla
mediante constructores SQL. Los parámetros siguen el formato del controlador,
`%(nombre)s` para psycopg. La [conexión de sesión](https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.connection)
comparte la transacción que confirma o revierte la sesión.

Ejemplo de integración, **no ejecutado por las pruebas**:

```python
from app.database import SessionLocal
from app.services.texts_handler import TextFacade

with SessionLocal() as db:
    text = TextFacade(db).create(" Hola ,mundo. ", "spa")
    print(text.id, text.content, text.difficulty)
```

También puede inyectarse la sesión ya entregada por `get_db()`. **No ejecutar
este ejemplo con una sesión real para reproducir las pruebas.** Los tests no
leen `.env`, no utilizan `DATABASE_URL` y no acceden a Supabase.

## Consultas explícitas y parámetros separados

[`CheckDuplicateTextStep`](../../../backend/app/services/texts_handler/processing/duplicate.py)
ejecuta:

```sql
SELECT id
FROM texts
WHERE content = %(content)s
LIMIT 1
```

Recibe por separado `{"content": contenido_normalizado}`. No carga el catálogo
completo ni filtra por idioma. Un resultado distinto de `None`, incluido ID `0`,
interrumpe la cadena con `duplicate_content` antes de clasificar o guardar.

[`PersistTextStep`](../../../backend/app/services/texts_handler/processing/persist.py)
ejecuta:

```sql
INSERT INTO texts (content, language, difficulty, ideal_time_ms, record_user_id)
VALUES (
    %(content)s,
    CAST(%(language)s AS text_language),
    CAST(%(difficulty)s AS difficulty),
    NULL,
    NULL
)
RETURNING id, content, language, difficulty, ideal_time_ms, record_user_id
```

Los valores de contenido, idioma y dificultad se envían en otro diccionario;
los enums se convierten a sus valores `spa`/`eng` y `easy`/`medium`/`advanced`/`expert`.
Los tipos `text_language` y `difficulty` corresponden al esquema existente.
No se concatena ni interpola contenido dentro del SQL. Los signos de apóstrofo
y los textos con aspecto de instrucción SQL siguen siendo valores, no código.
No se utilizan `select()`, `text()`, `where()`, `Session.add()`, `flush()` ni
`refresh()` para estas operaciones.

## Resultado y transacción

```text
INSERT ... RETURNING -> leer fila -> construir snapshot -> commit -> publicar resultado
```

`create()` devuelve un **`PersistedText` inmutable**, con los seis atributos de
la fila retornada: `id`, `content`, `language`, `difficulty`, `ideal_time_ms` y
`record_user_id`. Idioma y dificultad se convierten a los enums existentes.
Es un resultado desconectado, **no una entidad ORM**; leer sus atributos después
de confirmar no dispara consultas por expiración de atributos.

El paso de persistencia controla `commit` y `rollback`; la fachada no
confirma de nuevo. Si falla la ejecución, lectura o conversión de la fila o
`commit`, intenta `rollback`, interrumpe el flujo y no publica un resultado
exitoso. La causa original se conserva sin exponer sus detalles en el mensaje
público. Un fallo de conexión durante `commit` puede dejar un resultado incierto:
intentar rollback no demuestra que el servidor nunca haya confirmado.

Los fallos de consulta de duplicados también intentan rollback. Un duplicado
normal no escribe ni confirma; el proveedor conserva la responsabilidad de
cerrar la sesión y su transacción de lectura. No se interpreta cualquier error
de integridad como un duplicado.

La sesión debe estar dedicada a esta operación: confirmar o revertir una sesión
con cambios ajenos podría afectarlos. No se crean transacciones anidadas ni se
promete composición con transacciones externas. Persistencia es terminal: no
hay trabajo posterior al commit y el contexto no puede guardarse dos veces.

## Unicidad y límites pendientes

- El contenido se compara después de normalizar espacios, puntuación y comillas.
- La comparación conserva mayúsculas: `Hola` y `hola` son distintos. No se ha
  aprobado aplicar `lower()` o `casefold()`.
- La consulta no filtra por idioma; un contenido idéntico impide la creación.
- Textos históricos sin normalizar pueden necesitar una limpieza independiente.
- Consultar y luego insertar **no garantiza unicidad concurrente**. Falta una
  estrategia de unicidad en BD y su validación real; no se cambió el esquema.

## Comprobación reproducible sin BD

```bash
PYTHONPATH=backend python3 -m unittest discover \
  -s backend/tests/services/texts_handler -v
```

[`test_persistence.py`](../../../backend/tests/services/texts_handler/test_persistence.py)
y [`test_raw_sql.py`](../../../backend/tests/services/texts_handler/test_raw_sql.py)
usan mocks de sesión, conexión y resultados. La función real `execute_sql` se
extrae de su fuente mediante AST para probarla aisladamente, sin ejecutar la
creación del motor ni importar configuración. No está instalado SQLAlchemy en
este entorno; no se instalaron dependencias.

Se comprueban SQL y parámetros, orden de etapas, snapshots, duplicados, fallos
y rollback, consulta filtrada, ausencia de operaciones ORM, resultado inmutable,
imports sin BD y los 16 resultados de calibración. Esto **no valida** adaptación
real de parámetros psycopg, conversión de enums en PostgreSQL, aislamiento o
unicidad concurrente. Esas comprobaciones requieren un entorno de BD autorizado.

# Recibir, clasificar y almacenar un texto de mecanografía

**Estado: borrador para discusión; no se ha aprobado ninguna implementación ni contrato de API.**

Para la [issue #26](https://github.com/1Bnja/Typr/issues/26), incorporar un servicio
que reciba un texto en bruto y su idioma, calcule su dificultad y almacene el
resultado. Un endpoint HTTP puede actuar como adaptador ligero del mismo servicio;
la clasificación y la persistencia no deben depender de HTTP ni de un generador de textos.

## Código actual: ¿está implementada la recuperación de textos?

**No existe un servicio ni endpoint dedicado a recuperar textos en el árbol de
trabajo inspeccionado** (`feat/text-difficulty`, basado en el commit `29451bc`).
El backend tiene la estructura de datos, pero no el flujo de aplicación que la consulta.

| Evidencia verificada | Significado |
| --- | --- |
| [`Text`, líneas 14–34](../../../backend/app/models/text.py#L14-L34) | El mapeo de la tabla `texts` ya almacena contenido, idioma, dificultad y metadatos opcionales del récord. |
| [Índice de `Text`, líneas 18–22](../../../backend/app/models/text.py#L18-L22) | Ya existe un índice para filtrar por idioma y dificultad. Un índice no es una función de recuperación. |
| [Relaciones de `Text`, líneas 36–45](../../../backend/app/models/text.py#L36-L45) | Hay navegación ORM hacia el titular del récord y las partidas, no un servicio de selección o catálogo de textos. |
| [`User.texts`, líneas 31–34](../../../backend/app/models/user.py#L31-L34) | Esta relación representa los textos cuyo récord pertenece al usuario, no todos los textos disponibles ni los creados por él. |
| [`main.py`, líneas 1–8](../../../backend/app/main.py#L1-L8) | Solo están registrados los routers de estado del servicio, autenticación y usuarios. |
| [`services/auth.py`, líneas 12–35](../../../backend/app/services/auth.py#L12-L35) | Las consultas del servicio existente recuperan usuarios, no textos. Todavía no existe `services/texts.py`. |

La inspección abarcó el inventario actual de archivos de `backend/app` y las
referencias a textos y consultas después de explorar con CodeGraph. Es un hallazgo
del código fuente, no una prueba contra un servidor o una base de datos en ejecución.
No se actualizaron las referencias remotas.

El endpoint de recuperación aleatoria corresponde a
[#27](https://github.com/1Bnja/Typr/issues/27), asignada a Benjamín:
`GET /texts/random`, con filtros por idioma y dificultad. Coordinar un módulo
compartido `services/texts.py` sin implementar aquí esa otra issue.

## Flujo principal propuesto

```text
Contenido en bruto + idioma explícito
              |
              v
Validación de entrada
              |
              v
Clasificador puro de dificultad
              |
              v
Servicio de creación -> transacción de BD -> Text persistido
              ^
              |
Adaptador HTTP opcional o consumidor interno de confianza
```

1. Recibir `content` y `language`; quien invoca el servicio no elige la dificultad.
2. Validar la entrada antes de escribir datos.
3. Medir los factores aprobados y asignar un valor del enum de dificultad existente.
4. Persistir contenido, idioma y dificultad calculada en una sola transacción.
5. Devolver el texto persistido, incluidos su ID generado y dificultad.

### Responsabilidades y ubicaciones propuestas

| Ubicación | Responsabilidad |
| --- | --- |
| `backend/app/services/text_difficulty.py` (nuevo) | Clasificación determinista y sin efectos secundarios. Sin base de datos, HTTP, Gemini ni credenciales. |
| `backend/app/services/texts.py` (nuevo) | Crear un texto utilizando el clasificador y una sesión de base de datos explícita. Gestionar la transacción de creación y los errores. |
| `backend/app/schemas/text.py` (existente) | Añadir una solicitud de creación que acepte contenido e idioma, sin dificultad ni campos de récord proporcionados por el consumidor. |
| `backend/app/routers/texts.py` (opcional, nuevo) | Autorizar al consumidor, delegar en el servicio y convertir los resultados en respuestas HTTP. |
| `backend/app/main.py` (cambio opcional) | Registrar el router de textos solo si se aprueba su exposición por HTTP. |

Seguir la separación existente entre servicio y sesión en
[`services/auth.py:12–29`](../../../backend/app/services/auth.py#L12-L29)
y [`deps.py:11–16`](../../../backend/app/deps.py#L11-L16), en lugar de añadir una
capa genérica de repositorios para este único caso de uso. Una creación correcta
debe confirmar la transacción y devolver los datos persistidos actualizados;
una transacción fallida debe revertirse y no devolver un resultado de creación exitosa.

## Reutilizar el contrato existente

- Mantener los idiomas `spa` y `eng`, y las dificultades `easy`, `medium`,
  `advanced`, `expert` de
  [`models/enums.py:26–34`](../../../backend/app/models/enums.py#L26-L34).
- Reutilizar la validación de contenido no vacío y máximo de 5000 caracteres de
  [`schemas/text.py:7–20`](../../../backend/app/schemas/text.py#L7-L20).
  El validador actual comprueba los espacios en blanco, pero devuelve el contenido original.
- Conservar la convención `CamelModel` y la salida existente `TextPublic`.
- Dejar `ideal_time_ms` y `record_user_id` en null al crear el texto. Esta issue
  no crea récords de partidas ni estima el rendimiento del jugador.

**Propuesta de schema:** añadir una entrada separada, como `TextIngestRequest`,
compartiendo la validación del contenido en lugar de copiarla. El `TextCreate`
existente exige `difficulty` y acepta `ideal_time_ms`; utilizarlo directamente
permitiría al consumidor controlar campos que debe gestionar esta operación.
Modificar `TextCreate` sería un cambio menor, pero alteraría su contrato existente
y requeriría coordinación.

Las columnas actuales de la base de datos son suficientes **si** el alcance se
limita a almacenar contenido, idioma y el enum calculado. Persistir el desglose
de factores, versiones del clasificador o una restricción de unicidad exigiría
revisar el esquema y el plan de migraciones.

## Interfaz HTTP opcional: solo una propuesta

Ruta propuesta: `POST /api/v1/texts`, coherente con los prefijos actuales de la API.
«Texto en bruto» significa el valor de `content` sin clasificar dentro de una
solicitud JSON, no necesariamente un cuerpo HTTP `text/plain`:

```json
{
  "content": "A short example for a typing exercise.",
  "language": "eng"
}
```

Resultados propuestos:

| Situación | Comportamiento propuesto |
| --- | --- |
| Entrada válida y transacción confirmada | `201`, devolviendo la estructura existente `TextPublic`. |
| Contenido vacío, demasiado largo o idioma no admitido | Error de validación (`422` propuesto); sin inserción. |
| Consumidor no autenticado o no autorizado | Rechazar antes de crear; la política exacta y el uso de `401`/`403` requieren acuerdo. |
| Fallo de base de datos | Revertir la transacción, devolver un error de servidor apropiado y no exponer detalles de la base de datos. |
| Contenido repetido | Pendiente: no prometer `409` ni idempotencia sin definir una política de duplicados. |

**No exponer por defecto un endpoint público de escritura.** Existe autenticación,
pero el [`modelo User`](../../../backend/app/models/user.py#L15-L29) actual no
tiene campos de roles o permisos. «Haber iniciado sesión» no otorga por sí mismo
permiso para modificar el catálogo compartido. Comenzar con un servicio interno
de confianza hasta definir el consumidor y la política de autorización; HTTP
resulta útil para productores remotos, pero añade una superficie de API y autorización.

## Decisiones de clasificación pendientes

La issue #26 enumera factores, pero no especifica una fórmula. Los siguientes
puntos son decisiones por resolver, no reglas implementadas:

| Área | Decisión necesaria |
| --- | --- |
| Medición | Definición del conteo de caracteres; límites de palabras y longitud media; conteos frente a proporciones de mayúsculas, tildes, signos y números. |
| Asignación de nivel | Pesos y umbrales para los cuatro niveles, con ejemplos representativos y casos límite. |
| Idioma | Determinar si la puntuación varía según el idioma. Inicialmente, exigir un idioma admitido explícito; la detección automática no forma parte de esta propuesta. |
| Preservación de caracteres | Normalización Unicode, finales de línea, tabulaciones y espacios en los extremos. Clasificar la representación que realmente se almacena y entrega al jugador. |
| Duplicados | Decidir si un contenido e idioma idénticos se rechazan, reutilizan o permiten; definir envíos concurrentes y repetidos. Una consulta previa por sí sola no garantiza unicidad. |

Modificar un texto ya utilizado en una partida puede alterar el significado de
los resultados históricos. Este flujo debe crear textos, no editar ni reclasificar
silenciosamente los existentes. La reclasificación y el versionado requieren otra decisión.

## Generador relacionado: productor separado, no recuperación

La **instantánea local** de `origin/feat/logica-frases` contiene
`backend/app/services/generador.py` (ausente en este árbol de trabajo). Invoca
Gemini al importar el módulo (líneas 4–9), solicita frases en español en tres
grupos (líneas 13–44) e imprime la salida (línea 52). No consulta ni persiste
textos. Sus tres grupos no son una correspondencia aprobada con los cuatro
niveles de la base de datos.

Más adelante podría enviar candidatos al servicio de creación, pero la generación
debe permanecer separada: el clasificador debe funcionar sin red ni claves de API.

## Comprobaciones de implementación sugeridas: TDD

- [ ] Acordar definiciones de factores, umbrales y ejemplos representativos.
- [ ] Escribir pruebas fallidas del clasificador para cada factor y límite entre niveles; después implementar el clasificador puro.
- [ ] Probar contenido vacío, demasiado largo, idioma no admitido y casos Unicode o de espacios en blanco.
- [ ] Probar que la entrada del consumidor no puede determinar la dificultad almacenada ni los metadatos de récord.
- [ ] Probar la persistencia correcta y la reversión ante fallos siguiendo el patrón de sesión existente.
- [ ] Verificar la persistencia con PostgreSQL y los enums existentes; los mocks por sí solos no demuestran compatibilidad.
- [ ] Añadir pruebas de duplicados y concurrencia cuando se apruebe esa política.
- [ ] Si se elige HTTP, probar por separado autorización, estructura de respuesta y documentación de la API.

## Siguiente paso

Elegir quién proporcionará los textos y si necesita acceso HTTP. Después, acordar
un pequeño conjunto de ejemplos etiquetados para diseñar y probar la política
de dificultad. Este documento no implementa endpoints, clasificadores ni cambios
en la base de datos.

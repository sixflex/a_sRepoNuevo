# Recorrido: unificar las dos cuentas institucionales (@uautonoma.cl y @cloud.uautonoma.cl)

Recorrido hecho ANTES de cambiar código. Búsqueda en `.py`, plantillas, comandos y pruebas de:
`correo_institucional, correo, email, entra_oid, entra_id, perfil_docente, request.user, get_user_model, AUTH_USER_MODEL, username`.
Archivo de trabajo: se puede borrar.

## 1. Dónde nace la identidad (login)

| Archivo:línea | Qué hace con el correo | Impacto de unificar | Decisión |
|---|---|---|---|
| usuarios/entra.py:68 `dominio_permitido()` | Acepta UN dominio (`uautonoma.cl`) | Rechaza @cloud.uautonoma.cl | **Cambia**: `dominios_permitidos()` con `ENTRA_DOMINIOS_PERMITIDOS` (por defecto ambos); `ENTRA_DOMINIO_PERMITIDO` sigue funcionando si está definido |
| usuarios/entra.py:79-108 `ConectorEntraSimulado.identificar` | Valida dominio, arma `IdentidadEntra` (oid sim-uuid5) | Falta `tenant_id` | **Cambia**: agrega `tenant_id="simulado"`; mensajes mencionan los dos dominios |
| usuarios/entra.py:120-157 `_provisionar_usuario` | Busca por `entra_oid` → `correo_institucional` → `username` | Dos correos = dos Usuario | **Cambia**: busca primero `IdentidadInstitucional` (tenant+oid, luego correo), después lo antiguo (y le crea su identidad), si no crea usuario + identidad principal |
| usuarios/entra.py (CUENTAS_PRUEBA) | Cuentas de la pantalla simulada | — | **Cambia**: agrega `docente@cloud.uautonoma.cl` y `estudiante@cloud.uautonoma.cl` |
| usuarios/views.py:44-62 `EntraLoginSimuladoView.post` | `login()` del usuario | No se sabe con qué cuenta entró | **Cambia**: guarda `session["identidad_id"]`; modo vincular (en sesión) para /cuenta/ |
| templates/usuarios/entra_simulado.html:191 | placeholder `tucorreo@{{ dominio }}` | Un solo dominio | **Cambia**: texto con ambos dominios y modo vincular |
| usuarios/models.py:24-36 `Usuario.entra_oid / correo_institucional` (unique) | Copia de la identidad | Se mantienen | **Sin cambio de esquema**: quedan como copia de la identidad PRINCIPAL (el servicio las sincroniza) |
| usuarios/models.py:47 `__str__` | Muestra `correo_institucional or email` | Mostrará el principal | Sin cambio |
| Login nunca enlaza Usuario ↔ `academico.Docente` | Solo lo hacen los scripts de datos | Docente que entra por Microsoft no ve su panel | **Cambia (efecto en cadena)**: en cada login, si no tiene `perfil_docente`, se enlaza el Docente cuyo correo coincide con CUALQUIERA de sus identidades (solo si ese Docente no tiene usuario) y se agrega el grupo Docente. Nunca se roba un Docente de otro usuario |

## 2. Quién usa al usuario de la sesión

| Archivo:línea | Qué hace | Impacto | Decisión |
|---|---|---|---|
| core/views.py:243, 335 `docentes__usuario=request.user` | Paneles del docente | Funciona igual si las dos cuentas son el mismo Usuario | Sin cambio |
| core/views.py:41 / 323 (panel_coordinacion, inicio_docente) | Inicio Coordinador / Docente | Lugar del aviso | **Cambia**: aviso "¿También tienes una cuenta…?" solo aquí |
| cartas/views.py:48, 160, 603; rutas/views.py:38, 275, 356, 866; rutas/services.py:380, 675; socios/views.py:454 `perfil_docente` | Permisos y datos del docente | Mismo Usuario → mismo Docente | Sin cambio |
| usuarios/permissions.py, decorators.py (grupos) | `es_docente`/`es_coordinador` por grupo | Grupos se suman al fusionar | Sin cambio (la fusión copia grupos) |
| templates/base.html:49 `{{ user.username }}` | Nombre en la barra superior | Lugar del enlace a "Mi cuenta" | **Cambia**: nombre enlaza a /cuenta/ |
| templates/usuarios/login.html:188 | "Tienes la sesión iniciada como" | — | Sin cambio |

## 3. Correo/oid guardado en otras tablas

| Archivo:línea | Qué hace | Impacto | Decisión |
|---|---|---|---|
| proyectos/views.py:749-753 `correo_informante = request.user.correo_institucional` | Correo del estudiante informante; se exige que el integrante 1 tenga ese correo | Si entró con la otra cuenta, el formulario lo rechaza | **Cambia**: usa `identidad_actual(request).correo` |
| proyectos/views.py:813-821, 862-869 "Ya registraste un equipo" por `informante_correo__iexact` | Evita doble registro | Con dos cuentas podría registrar dos equipos | **Cambia (efecto en cadena)**: compara contra `correos_de_usuario(request.user)` |
| proyectos/views.py:935-936 `informante_correo / informante_entra_id` | Guarda correo + oid | Debe ser la cuenta usada | **Cambia**: identidad de la sesión |
| proyectos/views.py:1013 + templates/proyectos/acceso_registro_equipos.html:84, 366 | Muestra y precarga el correo del informante (`informante.correo_institucional`) | Mostraría el principal y la validación fallaría | **Cambia**: plantilla usa `correo_informante` del contexto |
| proyectos/views.py:1236-1290 (coordinador edita integrante) | Unicidad de correo de integrantes por equipo; correo del informante fijo | Datos tipeados de estudiantes | Sin cambio |
| templates/proyectos/gestionar_equipo*.html, socios/revisar_propuesto.html | Muestran `informante_correo` | Se ve la cuenta con que registró | Sin cambio |
| cartas/views.py:712-719 solicitante (estudiante) | `solicitante_correo/entra_id` de `request.user` | Debe ser la cuenta usada | **Cambia**: identidad de la sesión |
| cartas/views.py:84-89 solicitante (docente) | Usa `docente.correo_institucional`, entra_id None | Es el correo oficial del Docente | Sin cambio |
| cartas/views.py:358; cartas/services.py:551 | Avisa/envía la carta a `docente.correo_institucional` | Correo oficial registrado por coordinación | Sin cambio (decisión del brief) |
| cartas/services.py:305 "Emitido por" `usuario.username` | Texto del PDF | — | Sin cambio |
| cartas/templates/cartas/detalle_solicitud_coordinacion.html:102 | Muestra `solicitante_correo` | — | Sin cambio |

## 4. Búsqueda de docentes por correo

| Archivo:línea | Qué hace | Impacto | Decisión |
|---|---|---|---|
| planificacion/services.py:154-175 `_resolver_docente` | Busca Docente por RUT y luego por correo | Fila con el correo cloud no encuentra al docente registrado con uautonoma | **Cambia**: si no hay coincidencia directa, `usuario_por_correo(correo)` → su `perfil_docente`, o el Docente cuyo correo es otra cuenta del mismo usuario |
| academico/views.py:834-851 `_guardar_docente` | Unicidad de correo entre Docentes | Podía registrar como docente el correo de OTRA persona | **Cambia**: rechaza el correo si es una cuenta vinculada de otra persona (otro Usuario con otro Docente) |
| templates/academico/* | Muestran `docente.correo_institucional` | — | Sin cambio |
| planificacion/models.py:228, forms.py, views.py:27,127,168 | Correo tipeado en la fila de planificación | Se resuelve en `_resolver_docente` | Sin cambio |

## 5. Respuestas, indicadores, Ruta, reportes

| Archivo:línea | Qué hace | Impacto | Decisión |
|---|---|---|---|
| encuestas/services.py:625-642, 701 `respondente_correo` | Correo TIPEADO en la respuesta | No es identidad de login | Sin cambio (sin campo nuevo) |
| encuestas/services.py:655 `existe_respuesta_duplicada` | Duplicados por RUT | — | Sin cambio |
| encuestas/views.py:727 (Excel), templates/encuestas/respuestas.html:91-95 | Muestran/exportan el correo tipeado | — | Sin cambio |
| historicos/services.py:389, 406 | Dedup de importación por (fecha, correo, rut, nombre) | Datos importados | Sin cambio |
| socios/views.py:596-653, socios/services.py:575 | Correo del socio (externo) | No es institucional | Sin cambio |
| core/indicadores.py:720, reportes/services.py:177, rutas/services.py:372, 667 | Correo de contacto del socio | Externo | Sin cambio |
| core/indicadores.py, reportes, rutas (agrupación por persona) | Se agrupa por `Docente`/`Seccion`, nunca por correo | Ninguno | Sin cambio — no hay nada que agrupe por correo del docente |
| encuestas `enlace_abierto`, URL `encuestas:responder`, `EnlaceFormulario` (dependencia de Ruta Docente) | — | — | No se toca |

## 6. Llaves foráneas a AUTH_USER_MODEL (para fusionar)

| Archivo:línea | Campo | Decisión en `fusionar_usuarios` |
|---|---|---|
| academico/models.py:168 | `Docente.usuario` (OneToOne) | Se mueve si el destino no tiene Docente; si ambos tienen Docente distinto → error, lo resuelve Coordinación |
| archivos/models.py:7, 62 | `Archivo.cargado_por_usuario`, `RecursoRepositorio.publicado_por_usuario` | Se reasignan |
| cartas/models.py:49, 162 | `SolicitudCarta.solicitante_usuario`, `CartaDocumento.generado_por_usuario` (PROTECT) | Se reasignan |
| encuestas/models.py:41, 184 | `creado_por_usuario` (versiones, enlaces) | Se reasignan |
| historicos/models.py:13 | `CargaHistorica.responsable_usuario` | Se reasigna |
| rutas/models.py:22 | `VersionRuta.creado_por_usuario` | Se reasigna |
| socios/models.py:382, 418 | `revisado_por_usuario`, `cambiado_por` | Se reasignan |
| auditoria/models.py:7 | `AuditoriaCambio.usuario` | **No se reasigna**: la bitácora queda como ocurrió; la fusión deja su propio registro con ambos ids |
| django admin `LogEntry.user` | Historial del admin | No se reasigna (mismo criterio) |
| `groups`, `user_permissions` (M2M) | — | Se suman al destino |
| usuarios `IdentidadInstitucional.usuario` (nuevo) | — | Se mueven como no principales |

Recorrido genérico con `Usuario._meta.related_objects` (si aparece otra FK mañana, también se mueve). Ninguna restricción única existente incluye una FK a usuario.

## 7. Datos de prueba y pruebas

| Archivo | Qué hace | Decisión |
|---|---|---|
| usuarios/management/commands/crear_usuarios_prueba.py | Crea usuarios con clave (sin correo, salvo estudiante1) | **Cambia**: identidad principal (con el servicio) para docente1/docente2 con el correo de su Docente y para estudiante1 |
| core/management/commands/cargar_datos_demo.py:200-280 | Coordinador y docentes del Excel (username = correo) | **Cambia**: identidad principal para cada uno; el primer docente del Excel queda además con su otra cuenta (@cloud ↔ @uautonoma) ya vinculada |
| core/management/commands/cargar_datos_demo.py:493-494, 528 | `informante_entra_id` con el conector simulado | Sin cambio (sigue siendo determinista) |
| core/management/commands/preparar_datos_desarrollo.py | Llama a los anteriores | Sin cambio |
| historicos/management/commands/cargar_historicos.py | `get_user_model` para el responsable | Sin cambio |
| Pruebas existentes que crean usuarios con `create_user` | Sin identidad | El login antiguo les crea la identidad: siguen pasando |
| usuarios/tests_entra.py (`ENTRA_DOMINIO_PERMITIDO="uautonoma.cl"`) | Prueba un dominio | Se respeta la compatibilidad: con esa variable solo se acepta ese dominio |

## Efectos en cadena encontrados (no estaban en el encargo)
1. "Ya registraste un equipo en esta sección" comparaba un solo correo → ahora todos los correos del usuario.
2. La pantalla de registro de equipos mostraba/precargaba el correo principal → ahora el de la sesión (si no, la validación del integrante 1 fallaba al entrar con la otra cuenta).
3. Tras fusionar, el usuario origen conservaba `correo_institucional`, `entra_oid` y `username` = correo; el login "antiguo" lo volvía a encontrar si luego se desvinculaba esa cuenta. Al fusionar se limpian esos valores del origen (queda desactivado).
4. Una cuenta nueva sin rol conocido entra como Estudiante. Si un docente entra primero con su cuenta @cloud, queda Estudiante; al enlazarle su Docente (login o fusión) se le quita el grupo Estudiante y su rol pasa a Docente, para que el menú lateral (que mira el primer grupo) muestre lo correcto.

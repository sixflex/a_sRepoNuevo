# Análisis técnico del proyecto Portal Integrado A+

## 1. Propósito y estado general

Portal web para gestionar el proceso de Aprendizaje + Servicio (A+S) de una universidad. El proyecto está construido con Django y PostgreSQL, con una arquitectura modular por dominios: usuarios, estructura académica, proyectos A+S, planificación, encuestas, rutas de actividades, socios comunitarios, archivos, cartas, comunicaciones, auditoría, histórico, reportes y contenido público.

Este documento describe el estado real del código disponible en el repositorio. Hay dos niveles distintos:

- **Funcionalidad conectada:** autenticación, paneles, CRUD académico, generación de enlaces de planificación y formulario tabular de planificación.
- **Modelo de dominio preparado:** muchas tablas ya están diseñadas y migradas, pero sus apps todavía no tienen vistas, URLs ni lógica de negocio expuesta.

El proyecto contiene aproximadamente 57 modelos de dominio, además de los modelos estándar de Django y del usuario personalizado.

## 2. Stack y ejecución

- Python 3.11, según el README.
- Django 5.2.4.
- PostgreSQL, usando `psycopg2-binary==2.9.10`.
- `python-dotenv` para cargar variables desde `.env`.
- Templates Django renderizados en servidor.
- Bootstrap 5.3.8, Bootstrap Icons 1.11.3 y Google Fonts cargados desde CDN.
- Zona horaria: `America/Santiago`.
- Idioma: español (`es`).
- Clave primaria por defecto: `BigAutoField`.
- Servidores de entrada: WSGI y ASGI en `portal_as/wsgi.py` y `portal_as/asgi.py`.

### Configuración

`portal_as/settings.py`:

- `ROOT_URLCONF = portal_as.urls`.
- `AUTH_USER_MODEL = usuarios.Usuario`.
- `LOGIN_URL = usuarios:login`.
- Después del login se redirige a `core:inicio`.
- Después del logout se redirige a `usuarios:login`.
- `DEBUG` se lee de `DJANGO_DEBUG` y por defecto queda en `True`.
- La clave se lee de `DJANGO_SECRET_KEY` y tiene una clave de desarrollo por defecto.
- `ALLOWED_HOSTS` solo incluye `127.0.0.1` y `localhost`.
- Base de datos PostgreSQL configurada con `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` y `DB_PORT`.
- Templates globales en `templates/` y templates propios de cada app mediante `APP_DIRS=True`.
- Archivos estáticos en `static/`; `STATIC_ROOT` es `staticfiles/`.
- Middleware estándar de seguridad, sesiones, CSRF, autenticación, mensajes y X-Frame-Options.

El archivo `.env` existe localmente y no debe exponerse ni documentarse con sus valores reales. El README indica crear `.env` a partir de `.env.example`, aunque ese archivo de ejemplo no aparece en el inventario actual.

### Comandos documentados

```text
conda create -n portal_as python=3.11
conda activate portal_as
pip install -r requirements.txt
python manage.py check
python manage.py migrate
python manage.py makemigrations
python manage.py runserver
```

## 3. Estructura de carpetas y archivos

### Raíz

- `manage.py`: punto de entrada de comandos Django.
- `README.md`: instalación, variables de entorno, migraciones, ejecución y estrategia de ramas.
- `requirements.txt`: dependencias fijadas o declaradas.
- `.env`: configuración local; contiene secretos y no debe versionarse.
- `.gitignore`: exclusiones Git.
- `portal_as/`: configuración del proyecto.
- `templates/`: templates compartidos y por módulo.
- `static/`: CSS, JavaScript e imágenes.
- Cada app incluye normalmente `__init__.py`, `admin.py`, `apps.py`, `models.py`, `tests.py`, `views.py` y `migrations/`.

### Proyecto Django

- `portal_as/settings.py`: configuración general.
- `portal_as/urls.py`: URLs raíz.
- `portal_as/asgi.py`: entrada ASGI.
- `portal_as/wsgi.py`: entrada WSGI.

### Aplicaciones instaladas

1. `core`: navegación, inicio, paneles de coordinación y docente.
2. `usuarios`: usuario personalizado, roles, login/logout y permisos.
3. `proyectos`: proyectos A+S, equipos y enlaces; también contiene vistas del flujo de planificación.
4. `socios`: socios comunitarios y su participación.
5. `encuestas`: plantillas, versiones, preguntas, enlaces y respuestas.
6. `reportes`: reservado para indicadores y reportes; sin implementación actual.
7. `academico`: sedes, campus, facultades, carreras, asignaturas, docentes, periodos y secciones.
8. `campus`: carpeta instalada, pero sin modelos funcionales propios identificados.
9. `planificacion`: enlaces y captura tabular de planificación.
10. `rutas`: rutas de actividades, expedientes y evidencias.
11. `archivos`: metadatos de archivos y repositorio.
12. `cartas`: solicitudes y documentos de cartas.
13. `comunicaciones`: plantillas y envíos de correo.
14. `publico`: noticias públicas.
15. `auditoria`: registro genérico de cambios.
16. `historicos`: carga de información histórica, filas, mapeos y errores.

## 4. Modelo de datos por aplicación

Todos los modelos usan un `id` automático `BigAutoField`, salvo que se indique una relación o restricción especial.

### 4.1 `usuarios`

#### `Rol`

- `nombre`: `CharField(50)`, único.
- `descripcion`: `TextField`, opcional.

#### `Usuario`

Extiende `django.contrib.auth.models.AbstractUser`, por lo tanto conserva `username`, contraseña, nombres, apellidos, email, permisos, grupos, `is_active`, `is_staff`, `is_superuser`, `last_login` y `date_joined`.

Campos propios:

- `rol`: FK a `Rol`, `SET_NULL`, opcional.
- `entra_oid`: `CharField(80)`, único y opcional; preparado para integración con Microsoft Entra ID.
- `correo_institucional`: `EmailField(254)`, único y opcional.
- `activo`: booleano, por defecto `True`.
- `fecha_ultimo_acceso`: `DateTimeField`, opcional.

El método `__str__` muestra nombre completo y correo institucional o email.

### 4.2 `academico`

#### `Sede`

- `nombre`: `CharField(120)`, único.
- `ciudad`: `CharField(120)`, opcional.
- `activo`: booleano.

#### `Campus`

- `sede`: FK a `Sede`, `PROTECT`, related name `campus`.
- `nombre`: `CharField(120)`.
- `direccion`: `CharField(255)`, opcional.
- `activo`: booleano.
- Restricción: combinación `sede + nombre` única.

#### `PeriodoAcademico`

- `anio`: `SmallIntegerField`.
- `tipo`: `CharField(30)`.
- `nombre`: `CharField(80)`.
- `fecha_inicio`, `fecha_fin`: fechas opcionales.
- `estado`: `CharField(20)`.
- Restricción: `anio + tipo + nombre` única.

#### `Facultad`

- `codigo`: `CharField(60)`, único y opcional.
- `nombre`: `CharField(160)`.
- `activo`: booleano.

#### `Carrera`

- `facultad`: FK a `Facultad`, `PROTECT`, related name `carreras`.
- `codigo`: `CharField(30)`, único y opcional.
- `nombre`: `CharField(180)`.
- `activo`: booleano.

#### `UnidadAcademica`

- `facultad`: FK a `Facultad`, `SET_NULL`, opcional.
- `carrera`: FK a `Carrera`, `SET_NULL`, opcional.
- `tipo`: `CharField(40)`.
- `nombre`: `CharField(180)`.
- `correo_oficial`: `CharField(254)`, opcional.
- `activo`: booleano.

#### `Asignatura`

- `codigo`: `CharField(30)`, único y opcional.
- `nombre`: `CharField(180)`.
- `activo`: booleano.
- Relación N:M con `Carrera` mediante `AsignaturaCarrera`.

#### `AsignaturaCarrera`

- `asignatura`: FK a `Asignatura`, `CASCADE`.
- `carrera`: FK a `Carrera`, `CASCADE`.
- Restricción: combinación `asignatura + carrera` única.

#### `Docente`

- `usuario`: OneToOne con `usuarios.Usuario`, `SET_NULL`, opcional, related name `perfil_docente`.
- `rut`: `CharField(12)`, único.
- `nombres`, `apellidos`: `CharField(120)`.
- `correo_institucional`: `CharField(254)`, único.
- `telefono`: `CharField(30)`, opcional.
- `activo`: booleano.

#### `Seccion`

- `periodo`: FK a `PeriodoAcademico`, `PROTECT`.
- `campus`: FK a `Campus`, `PROTECT`.
- `asignatura`: FK a `Asignatura`, `PROTECT`.
- `nrc`: `CharField(20)`.
- `seccion`: `CharField(20)`.
- `jornada`: `CharField(40)`, opcional.
- `horario`: `CharField(160)`, opcional.
- `estado`: `CharField(20)`.
- `fecha_consolidacion`: fecha/hora opcional.
- Relación N:M con `Carrera` mediante `SeccionCarrera`.
- Relación N:M con `Docente` mediante `SeccionDocente`.
- Restricción: `periodo + nrc` única.

#### `SeccionCarrera`

- `seccion`: FK a `Seccion`, `CASCADE`.
- `carrera`: FK a `Carrera`, `CASCADE`.
- `nivel`: `CharField(30)`, opcional.
- `declaracion_as`: booleano opcional.
- `estudiantes_planificados`: entero opcional.
- Restricción: `seccion + carrera` única.

#### `SeccionDocente`

- `seccion`: FK a `Seccion`, `CASCADE`.
- `docente`: FK a `Docente`, `CASCADE`.
- `tipo_contrato`: `CharField(80)`, opcional.
- `capacitado_as`: booleano opcional.
- Restricción: `seccion + docente` única.

### 4.3 `proyectos`

#### `ProyectoAS`

- `nombre`: `CharField(220)`.
- `descripcion`, `servicio_propuesto`, `resumen_publico`: texto opcional.
- `estado`: `CharField(30)`.
- `fecha_inicio`, `fecha_fin`: fechas opcionales.
- `es_publico`: booleano, por defecto `False`.
- `fecha_creacion`: fecha/hora automática.

#### `Equipo`

- `seccion`: FK a `academico.Seccion`, `PROTECT`.
- `proyecto`: FK a `ProyectoAS`, `SET_NULL`, opcional.
- `numero_grupo`: entero.
- `informante_nombre`: `CharField(180)`.
- `informante_correo`: `CharField(254)`.
- `informante_entra_id`: `CharField(80)`, opcional.
- `fecha_registro`: automática.
- `estado`: `CharField(20)`.
- Restricción: `seccion + numero_grupo` única.

#### `IntegranteEquipo`

- `equipo`: FK a `Equipo`, `CASCADE`.
- `rut`: `CharField(12)`.
- `nombres`, `apellidos`: `CharField(120)`.
- `correo_institucional`: `CharField(254)`.
- `es_informante`: booleano, por defecto `False`.
- Restricción: `equipo + rut` única.

#### `Etiqueta`

- `nombre`: `CharField(80)`, único.
- `activo`: booleano, por defecto `True`.

#### `IntegranteEtiqueta`

- `integrante`: FK a `IntegranteEquipo`, `CASCADE`.
- `etiqueta`: FK a `Etiqueta`, `PROTECT`.
- `asignado_por_docente`: FK a `academico.Docente`, `PROTECT`.
- `fecha_asignacion`: automática.
- Restricción: `integrante + etiqueta` única.

#### `EnlaceRegistroEquipo`

- `seccion`: FK a `Seccion`, `PROTECT`.
- `creado_por_docente`: FK a `Docente`, `PROTECT`.
- `token`: UUID único generado automáticamente y no editable.
- `fecha_inicio`, `fecha_expiracion`: fechas/horas; expiración opcional.
- `activo`: booleano, por defecto `True`.

### 4.4 `planificacion`

#### `PlanificacionEnlace`

- `unidad_academica`: FK a `academico.UnidadAcademica`, `PROTECT`.
- `campus`: FK a `Campus`, `PROTECT`.
- `periodo`: FK a `PeriodoAcademico`, `PROTECT`.
- `token`: UUID único generado automáticamente.
- `destinatario_nombre`, `destinatario_correo`: datos del receptor.
- `fecha_emision`: fecha/hora.
- `fecha_expiracion`: fecha/hora opcional.
- `activo`: booleano.

#### `Planificacion`

- `enlace`: OneToOne con `PlanificacionEnlace`, `PROTECT`.
- `estado`: `CharField(20)`.
- `fecha_guardado`, `fecha_envio_final`: fechas/horas opcionales.
- `filas_recibidas`, `filas_aceptadas`, `filas_observadas`: enteros.

#### `FilaPlanificacion`

- `planificacion`: FK a `Planificacion`, `CASCADE`.
- `numero_fila`: entero; único por planificación.
- Texto importado: `facultad_texto`, `carrera_texto`, `campus_texto`, `asignatura_texto`, `posible_socio_texto`.
- Datos académicos: `nrc`, `seccion`, `nivel`, `jornada`, `horario`.
- `declaracion_as`: booleano opcional.
- `estudiantes_planificados`: entero opcional.
- `estado_validacion`: `CharField(20)`.
- Resoluciones opcionales a `Campus`, `Carrera`, `Asignatura` y `Seccion`, todas con `SET_NULL`.

#### `FilaPlanificacionDocente`

- `fila`: FK a `FilaPlanificacion`, `CASCADE`.
- `docente_resuelto`: FK a `Docente`, `SET_NULL`, opcional.
- `rut`, `nombre`, `tipo_contrato`, `correo`, `telefono`: campos opcionales.
- `capacitado_as`: booleano opcional.

#### `PlanificacionError`

- Pertenece a una `FilaPlanificacion` mediante FK con borrado en cascada.
- Registra `campo`, `codigo`, `mensaje` y el estado/detalle de validación definido en el modelo.

El formulario `FilaPlanificacionForm` expone solo los datos de entrada de la fila y omite campos de resolución, estado y relaciones internas. El `FilaPlanificacionFormSet` permite una fila adicional y borrado de filas.

### 4.5 `encuestas`

#### `FormularioPlantilla`

- `codigo`: `CharField(60)`, único.
- `titulo`: `CharField(220)`.
- `descripcion`: texto opcional.
- `proceso`: `CharField(60)`.
- `activo`: booleano.

#### `FormularioVersion`

- `plantilla`: FK a `FormularioPlantilla`, `PROTECT`.
- `creado_por_usuario`: FK al usuario, `SET_NULL`, opcional.
- `numero_version`, `estado`, `contexto_tipo`.
- Fechas de creación, publicación y vigencia, varias opcionales.
- Restricción: `plantilla + numero_version` única.

#### `BloqueFormulario`

- `formulario_version`: FK, `CASCADE`.
- `titulo`, `descripcion`, `orden`.
- `regla_visibilidad_json`: JSON opcional.

#### `PreguntaFormulario`

- `version`: FK a `FormularioVersion`, `CASCADE`.
- `bloque`: FK opcional a `BloqueFormulario`, `SET_NULL`.
- `pregunta_padre`: FK autorreferente opcional, `SET_NULL`, para preguntas hijas.
- `texto`, `tipo`, `obligatoria`, `orden`.
- `configuracion_json` y `regla_visibilidad_json`: JSON opcional.

#### `OpcionPregunta`

- `pregunta`: FK, `CASCADE`.
- `texto`, `valor`, `orden`, `es_otras`.

#### `EnlaceFormulario`

- `version`: FK a `FormularioVersion`, `PROTECT`.
- Creador: FK a usuario, `SET_NULL`.
- Contextos opcionales: `Seccion`, `Equipo`, `ProyectoAS`, `SocioComunitario` y `Convocatoria`, todos con `SET_NULL`.
- `token`: UUID único.
- `fecha_inicio`, `fecha_expiracion`, `activo`.

#### `RespuestaFormulario`

- `version`: FK, `PROTECT`.
- `enlace`: FK opcional, `SET_NULL`.
- Contexto académico opcional: sede, campus, periodo, carrera, asignatura, sección y docente.
- Contexto A+S opcional: equipo, proyecto y socio.
- `fecha_envio`, `origen`, `es_historica`, `estado_registro`.
- Snapshot del respondente: tipo, nombre, correo y RUT.
- Snapshot académico: NRC y sección.

El modelo representa respuestas agregadas por formulario; en el código leído no aparece un modelo separado de respuesta por pregunta, por lo que el almacenamiento detallado de respuestas requeriría campos adicionales o una implementación pendiente.

### 4.6 `socios`

#### `ClasificacionSocio`

- `nombre`: único.
- `activo`: booleano.

#### `Comuna`

- `nombre`, `region`.
- `lat_centro`, `lon_centro`: decimales opcionales, 9 dígitos y 6 decimales.
- `activo`.
- Restricción: `nombre + region` única.

#### `SocioComunitario`

- FK opcionales a `ClasificacionSocio` y `Comuna`, ambos `SET_NULL`.
- `rut`: único, opcional.
- `nombre_organizacion`, `clasificacion_otra`, `direccion_exacta`, `centro_servicio`.
- `estado_revision`, `es_provisional`, `activo`, `fecha_creacion`.

#### `ContactoSocio`

- `socio`: FK, `CASCADE`.
- `nombre`, `cargo`, `correo`, `telefono`.
- `es_principal`, `activo`.

#### `ParticipacionSocio`

- Relaciones obligatorias con socio, equipo y proyecto, usando `PROTECT`.
- Relaciones contextuales opcionales con sede, campus, periodo, carrera, asignatura y sección, usando `SET_NULL`.
- `servicio_realizado`, `beneficiarios_estimados`, `evaluacion`, `comentario`.
- `fecha_inicio`, `fecha_fin`, `origen`.

#### `InvitacionCierre`

- `seccion_ruta`: FK a `rutas.SeccionRuta`, `PROTECT`.
- `socio`: FK, `PROTECT`.
- `token`: UUID único generado automáticamente.
- `modo_contacto`, `respuesta`, fechas de envío/respuesta y observación.
- Restricción: `seccion_ruta + socio` única.

#### `Convocatoria`

- `formulario_version`: FK a `encuestas.FormularioVersion`, `PROTECT`.
- `nombre`, `descripcion`, fechas de inicio/fin y `estado`.

### 4.7 `rutas`

#### `RutaPlantilla` y `RutaVersion`

- Plantilla: nombre, descripción opcional y activo.
- Versión: FK a plantilla, creador opcional, número, estado y fechas de vigencia.
- Restricción: `plantilla + numero_version` única.

#### `RutaActividad`

- `ruta_version`: FK, `CASCADE`.
- Formulario asociado opcional y archivo/recurso opcional, ambos `SET_NULL`.
- `etapa`, `nombre`, `descripcion`, `es_obligatoria`, `orden`.
- `recurso_url` y `config_recordatorio_json` opcionales.

#### `SeccionRuta`

- `seccion`: OneToOne con `academico.Seccion`, `PROTECT`.
- `ruta_version`: FK, `PROTECT`.
- Docente que la cierra opcional, `SET_NULL`.
- `estado`, porcentaje final decimal opcional y fecha de cierre opcional.

#### `SeccionActividad`

- `seccion_ruta`: FK, `CASCADE`.
- `ruta_actividad`: FK, `PROTECT`.
- Docente que completa opcional, `SET_NULL`.
- `estado`, fecha de completado y observación.
- Restricción: `seccion_ruta + ruta_actividad` única.

#### `ExpedienteSeccion`

- OneToOne con `academico.Seccion`, `PROTECT`.
- `estado`, `fecha_creacion`, `fecha_cierre` opcional.

#### `Evidencia`

- `expediente`: FK, `CASCADE`.
- `seccion_actividad`: FK, `PROTECT`.
- `archivo`: OneToOne con `archivos.Archivo`, `PROTECT`.
- `descripcion` opcional.

### 4.8 `archivos`

#### `Archivo`

- Usuario que carga: FK al usuario, `SET_NULL`, opcional.
- `nombre_original`, `storage_key`, `mime_type`, `tamano_bytes`.
- `storage_key` es único.
- `hash_sha256` opcional.
- `fecha_carga` automática.

El modelo guarda metadatos y clave de almacenamiento, pero no configura un `FileField` ni un backend de almacenamiento en el código revisado.

#### `RecursoRepositorio`

- Archivo opcional, `SET_NULL`.
- Usuario publicador opcional, `SET_NULL`.
- `titulo`, `descripcion`, `categoria`, `url_externa`.
- `visibilidad` con choices `PUBLICO` y `PRIVADO`.
- `estado`, `fecha_publicacion` opcional.

### 4.9 `cartas`

#### `SolicitudCarta`

- Relaciones obligatorias a sección, campus, sede y docente derivador.
- Relaciones opcionales a equipo, socio y usuario solicitante.
- Datos del solicitante, institución/persona receptora, cargo y consideraciones.
- `estado`, motivo de observación, fecha de solicitud y fecha de aprobación opcional.

#### `CartaEstudiante`

- `solicitud`: FK, `CASCADE`.
- `nombre`, `rut`, `orden`.
- Restricción: `solicitud + orden` única.

#### `CartaDocumento`

- `solicitud`: FK, `CASCADE`.
- `archivo`: OneToOne a `Archivo`, `PROTECT`.
- Usuario generador: FK, `PROTECT`.
- `numero_version`, `tipo`, `fecha_generacion`, `hash_documento` opcional.
- Restricción: `solicitud + numero_version` única.

### 4.10 `comunicaciones`

#### `PlantillaCorreo`

- `codigo`: único.
- `asunto_template`, `cuerpo_template`, `activo`.

#### `EnvioCorreo`

- Relaciones opcionales a plantilla, documento de carta, postulación de socio e invitación de cierre; usan `SET_NULL`.
- `remitente`, `destinatario`, `asunto`, `cuerpo`.
- `fecha_envio` opcional.
- `resultado`: `PENDIENTE`, `OK` o `ERROR`.
- `detalle_error` opcional y `numero_intento`.

### 4.11 `publico`

#### `Noticia`

- `titulo`, `resumen` opcional, `fuente`, `url_fuente`, `imagen_url` opcional.
- `fecha_publicacion`, `fecha_sincronizacion` opcional y `estado`.

### 4.12 `auditoria`

#### `AuditoriaCambio`

- Usuario opcional que ejecuta el cambio, `SET_NULL`.
- `actor_externo` opcional.
- `entidad`, `entidad_id`, `accion`.
- Valores anterior y nuevo en JSON opcional.
- `fecha` e `ip` opcional.

Es un registro polimórfico: la entidad auditada se identifica por texto y no mediante una FK genérica.

### 4.13 `historicos`

#### `CargaHistorica`

- OneToOne con `archivos.Archivo`, `PROTECT`.
- Usuario responsable opcional, `SET_NULL`.
- `tipo_origen`, `hoja`, `fecha_carga`, `estado`.
- Contadores: total, aceptadas, observadas y omitidas.

#### `CargaMapeo`

- FK a carga histórica, `CASCADE`.
- `columna_origen` y `campo_destino`.

#### `CargaFila`

- FK a carga, `CASCADE`.
- Relaciones opcionales a respuesta de formulario, socio y participación, todas `SET_NULL`.
- `numero_fila`, `datos_raw_json`, `estado`.
- Restricción: `carga + numero_fila` única.

#### `CargaError`

- FK a fila, `CASCADE`.
- `campo`, `codigo` opcionales y `mensaje` obligatorio.

## 5. Relaciones principales entre dominios

```text
Usuario
  ├── Rol
  ├── Docente
  ├── FormularioVersion / EnlaceFormulario
  ├── RutaVersion
  ├── Archivo / RecursoRepositorio
  ├── SolicitudCarta / CartaDocumento
  └── AuditoriaCambio / CargaHistorica

Sede
  └── Campus
       └── Seccion
            ├── Carreras mediante SeccionCarrera
            ├── Docentes mediante SeccionDocente
            ├── Equipos
            ├── Ruta mediante SeccionRuta
            ├── ExpedienteSeccion
            └── Planificacion / Encuestas / Participaciones

Carrera
  ├── Asignaturas mediante AsignaturaCarrera
  └── UnidadesAcademicas

ProyectoAS
  ├── Equipos
  ├── ParticipacionSocio
  ├── RespuestaFormulario
  └── EnlaceFormulario

FormularioPlantilla
  └── FormularioVersion
       ├── Bloques y preguntas
       ├── Enlaces
       ├── Respuestas
       ├── RutasActividad
       └── Convocatorias

RutaPlantilla
  └── RutaVersion
       ├── RutaActividad
       ├── SeccionRuta
       └── SeccionActividad

Archivo
  ├── Evidencia
  ├── CartaDocumento
  ├── RecursoRepositorio
  └── CargaHistorica
```

## 6. URLs y vistas realmente conectadas

### URLs raíz: `portal_as/urls.py`

- `/admin/`: administración Django.
- `/`: incluye `core.urls`.
- `/academico/`: incluye `academico.urls`.
- `/usuarios/`: incluye `usuarios.urls`.
- `/proyectos/`: incluye `proyectos.urls`.
- `/planificacion/`: incluye `planificacion.urls`.

No se incluyen en la raíz las URLs de `socios`, `encuestas`, `reportes`, `rutas`, `archivos`, `cartas`, `comunicaciones`, `publico`, `auditoria` ni `historicos`.

### `core`

- `GET /`: `inicio`; requiere login y redirige por grupo a coordinación o docente.
- `GET /coordinacion/`: `panel_coordinacion`; requiere coordinador y muestra conteos de secciones, docentes, asignaturas y periodos activos.
- `GET /docente/`: `panel_docente`; requiere docente y muestra las secciones vinculadas al usuario.
- `GET /secciones/<seccion_id>/`: `detalle_seccion`; requiere login y verifica que el docente pertenezca a la sección; coordinación puede acceder.
- `GET /coordinacion/planificacion/`: lista planificaciones para coordinación.
- `GET /coordinacion/planificacion/<planificacion_id>/`: detalle y filas de una planificación.

### `usuarios`

- `/usuarios/login/`: `LoginTemporalView`, basado en `LoginView`, template `usuarios/login.html`.
- `/usuarios/logout/`: `LogoutView`.

### `academico`

Todas las vistas usan `coordinador_required`.

- `/academico/`: home.
- CRUD de campus: listar, crear, editar y eliminar.
- CRUD de sedes: listar, crear, editar y eliminar.
- CRUD de facultades: listar, crear, editar y eliminar.
- CRUD de carreras: listar, crear, editar y eliminar.
- CRUD de asignaturas: listar, crear, editar y eliminar; creación y edición manejan la relación N:M con carreras usando `AsignaturaCarrera`.
- `/academico/planificacion/`: lista planificaciones.
- `/academico/planificacion/<pk>/`: detalle de planificación.
- CRUD de secciones: listar, crear, editar y eliminar.
- CRUD de docentes: listar, crear, editar y eliminar.
- CRUD de periodos: listar, crear, editar y eliminar.

La app usa principalmente lectura directa de `request.POST`; solo existe un `CampusForm` y no es el mecanismo central de los CRUD observados.

### `proyectos`

- `/proyectos/coordinador-contexto/`: template demostrativo, sin verificación de rol.
- `/proyectos/formulario-prueba/`: template demostrativo.
- `/proyectos/enlaces-planificacion/`: GET lista enlaces y POST intenta crear un enlace; requiere coordinador.
- `/proyectos/planificacion/<uuid:token>/`: muestra formulario de planificación asociado a un token.

### `planificacion`

- `/planificacion/formulario/<uuid:token>/`: formulario tabular A+S.
- Obtiene el enlace por token, comprueba `activo` y fecha de expiración, crea u obtiene una planificación y permite guardar borrador o enviar estado final.
- El POST usa `transaction.atomic()`, guarda el formset, elimina filas marcadas y actualiza el estado/fecha de envío.

## 7. Autenticación y autorización

`usuarios.permissions` define permisos por pertenencia a grupos Django:

- `es_coordinador(user)`: grupo `Coordinador`.
- `es_docente(user)`: grupo `Docente`.

`usuarios.decorators` define:

- `coordinador_required`: redirige a login si no está autenticado; permite superusuarios como excepción temporal; exige grupo Coordinador.
- `docente_required`: redirige a login si no está autenticado; exige grupo Docente.

El flujo principal no usa el campo `Usuario.rol` para autorizar; usa grupos. El template base inspecciona `user.groups.all.0.name`, por lo que asume que el primer grupo representa el rol visual del usuario.

## 8. Templates y recursos estáticos

### Templates

- `templates/base.html`: layout general, navbar, sidebar, usuario autenticado, logout y bloques de contenido.
- `templates/usuarios/login.html`: login.
- `templates/core/`: inicio, panel de coordinación, panel docente, detalle de sección y vistas de planificación.
- `templates/academico/`: home, listados, formularios y confirmaciones para sede, campus, facultad, carrera, asignatura, docente, periodo y sección.
- `templates/proyectos/`: contexto de coordinador, formulario de prueba, gestión de enlaces y formulario docente.
- `templates/planificacion/formulario_tabular.html`: edición tabular mediante formset.

### Static

- `static/css/styles.css`: estilos propios.
- `static/js/app.js`: JavaScript propio.
- `static/img/bg_login.png`: fondo de login.
- `static/img/logo_ua.png`: logo institucional.

La interfaz usa una identidad visual institucional roja, sidebar para usuarios autenticados y diseño Bootstrap.

## 9. Administración y migraciones

### Admin registrado

- `usuarios/admin.py`: `Usuario`, `Rol`.
- `academico/admin.py`: todos los modelos académicos, incluidos modelos intermedios.
- El resto de las apps tienen `admin.py` vacío o solo comentarios, por lo que sus modelos no están registrados explícitamente en el admin.

### Migraciones

La mayoría de las apps tienen `0001_initial.py`; algunas apps de desarrollo tienen también `0002_initial.py`. Las migraciones muestran que el esquema fue diseñado de forma transversal y que existen dependencias entre apps, especialmente:

- `proyectos` depende de `academico`.
- `rutas` depende de `academico`, `archivos` y `encuestas`.
- `socios` depende de `academico`, `encuestas`, `proyectos` y `rutas`.
- `cartas` depende de `archivos` y referencia varios dominios.
- `comunicaciones` depende de `cartas`.
- `historicos` referencia archivos, encuestas y socios.

Las migraciones son una representación útil del esquema inicial, pero la fuente actual de verdad para cambios futuros son los `models.py` y la salida de `makemigrations`.

## 10. Tests y nivel de implementación

Cada app contiene un `tests.py`, pero el código revisado no muestra una suite funcional desarrollada. Las pruebas de comportamiento más importantes que faltan o deberían confirmarse son:

- Login, logout y redirección por grupo.
- Acceso denegado a vistas por rol.
- Aislamiento de un docente respecto de secciones ajenas.
- CRUD académico y restricciones de unicidad.
- Expiración y desactivación de enlaces.
- Guardado de borrador y envío final de planificación.
- Integridad de formsets y transacciones.
- Relaciones de borrado `PROTECT`, `SET_NULL` y `CASCADE`.
- Modelos de encuestas, rutas, cartas, socios, archivos, auditoría e históricos, todavía sin flujo web.

## 11. Inconsistencias y riesgos detectados

Estos puntos describen el código actual y son importantes para cualquier IA que continúe el desarrollo:

1. **Desajuste en enlaces de planificación:** `proyectos.views.gestionar_enlaces_planificacion` intenta leer `destinatario_tipo`, pero `PlanificacionEnlace` no tiene ese campo. También usa `fecha_creacion`, mientras el modelo define `fecha_emision`.
2. **Campo requerido omitido al crear enlaces:** `PlanificacionEnlace.unidad_academica` no es opcional, pero la vista de proyectos crea el objeto sin asignarlo.
3. **Campos no existentes en consultas:** `core.views` usa `unidad_carrera` y `fecha_envio` en consultas/contextos de `Planificacion`, mientras el modelo leído usa `enlace`, `fecha_guardado` y `fecha_envio_final`; esto puede provocar errores en ejecución.
4. **Dos flujos de planificación paralelos:** existe `proyectos.formulario_planificacion_docente` y existe `planificacion.formulario_tabular_as`. El primero solo muestra el enlace y el segundo implementa el formset de edición.
5. **URLs sin namespace en académica:** `academico.urls` no define `app_name`, y varias vistas redirigen con nombres globales como `sede_list`; funciona solo mientras no haya colisiones.
6. **Definiciones duplicadas en `academico.views`:** `sede_list` y `sede_create` aparecen definidas dos veces; la segunda definición es la que queda activa en Python.
7. **Campos booleanos sin default:** numerosos modelos requieren enviar explícitamente `activo`, estados o flags; los formularios manuales deben cubrirlos siempre.
8. **Respuesta de encuesta incompleta como modelo normalizado:** existe `RespuestaFormulario`, pero no un modelo visible que guarde una respuesta individual para cada `PreguntaFormulario`.
9. **Archivos sin carga física implementada:** `Archivo` guarda metadata y `storage_key`, pero no se ve `FileField`, servicio de almacenamiento ni vista de subida.
10. **Autorización basada en grupos y no en `Rol`:** hay dos conceptos de rol en el modelo, pero la autorización efectiva usa grupos Django.
11. **Superusuario como excepción temporal:** `coordinador_required` permite superusuarios, pero `docente_required` no tiene esa excepción.
12. **Seguridad de configuración:** `DEBUG=True` y una clave por defecto son adecuados solo para desarrollo; deben ser obligatorios o seguros en producción.
13. **Validación manual limitada:** varios campos de correo, RUT, estados y fechas se reciben como texto sin formularios Django ni validadores de dominio consistentes.
14. **Apps de dominio sin rutas:** socios, encuestas, rutas, archivos, cartas, comunicaciones, público, auditoría, históricos y reportes tienen modelos, pero sus `views.py` son placeholders y no tienen URLs raíz incluidas.
15. **Registro admin incompleto:** la mayoría de los modelos no se pueden gestionar desde el admin salvo que se registren posteriormente.

## 12. Lectura arquitectónica para futuras tareas

El proyecto parece estar en una etapa de construcción incremental por sprints. La base de datos ya anticipa el sistema completo, mientras que la interfaz operativa implementa primero la administración académica y el ciclo de planificación. Para continuar de forma consistente, una IA debería:

1. Tratar `usuarios.Usuario` como el usuario autenticado oficial.
2. Usar grupos `Coordinador` y `Docente` para autorización, salvo que se decida migrar todo al campo `Rol`.
3. Considerar `academico` como el núcleo referencial de periodos, sedes, campus, carreras, asignaturas, secciones y docentes.
4. Mantener las reglas `PROTECT` en entidades históricas o referenciales y `CASCADE` en entidades hijas de composición.
5. Revisar primero los desajustes entre `core`, `proyectos` y `planificacion` antes de ampliar funcionalidades.
6. No asumir que un modelo tiene API o pantalla solo porque exista en `models.py` o en una migración.
7. Preferir formularios Django, validación de modelo y transacciones para nuevos flujos de escritura.
8. Añadir URLs, permisos, templates, admin y tests como parte de cada módulo funcional, no solo el modelo.

## 13. Resumen de madurez por módulo

| Módulo | Modelos | Vistas | URLs conectadas | Admin | Estado |
|---|---:|---|---|---|---|
| `core` | No propios | Sí | Sí | No aplica | Navegación y paneles funcionales |
| `usuarios` | Sí | Login/logout | Sí | Sí | Autenticación base |
| `academico` | Sí | CRUD amplio | Sí | Sí | Módulo operativo principal |
| `proyectos` | Sí | Parcial | Sí | No | Flujo de enlaces y pantallas de apoyo |
| `planificacion` | Sí | Formulario tabular | Sí | No | Flujo operativo con inconsistencias a revisar |
| `encuestas` | Sí | Placeholder | No | No | Modelo de dominio pendiente |
| `socios` | Sí | Placeholder | No | No | Modelo de dominio pendiente |
| `rutas` | Sí | Placeholder | No | No | Modelo de dominio pendiente |
| `archivos` | Sí | Placeholder | No | No | Metadata pendiente de almacenamiento |
| `cartas` | Sí | Placeholder | No | No | Modelo de dominio pendiente |
| `comunicaciones` | Sí | Placeholder | No | No | Modelo de dominio pendiente |
| `publico` | Sí | Placeholder | No | No | Modelo de dominio pendiente |
| `auditoria` | Sí | Placeholder | No | No | Modelo de dominio pendiente |
| `historicos` | Sí | Placeholder | No | No | Modelo de dominio pendiente |
| `reportes` | No propio | Placeholder | No | No | Reservado |
| `campus` | Sin dominio funcional identificado | Placeholder | No | No | Posible app heredada o pendiente |

Este archivo debe utilizarse como contexto de arquitectura y estado del repositorio. Para implementar cambios concretos, siempre se debe volver a verificar el código fuente y las migraciones actuales, porque los nombres y contratos de los modelos pueden evolucionar.

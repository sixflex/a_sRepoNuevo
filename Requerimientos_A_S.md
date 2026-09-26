# ESPECIFICACIÓN DE REQUISITOS DEL SOFTWARE

## Portal Integrado de Gestión e Información A+S

**Universidad Autónoma de Chile**

---

### Información General del Documento

| Aspecto | Descripción |
|--------|------------|
| **Alcance** | Sistema multicampus; carga inicial de Sede Santiago, Campus Providencia |
| **Base documental** | Documento presentado, reuniones con profesores y cliente, formularios, planilla de asignaturas, carta oficial y mapa territorial |
| **Propósito** | Consolidar el MVP con requisitos completos, comprobables y explicables |
| **Versión** | Consolidada posterior a la última reunión - septiembre de 2026 |

---

## 1. Propósito y método de especificación

El proyecto "Portal Integrado de Gestión e Información A+S" tiene como objetivo entregar a la Universidad Autónoma de Chile una base de gestión e información para la metodología Aprendizaje y Servicio. El sistema deberá quedar preparado para operar con los distintos campus y sedes de la universidad; la carga inicial del piloto utilizará únicamente información de la Sede Santiago, Campus Providencia.

El objetivo de este documento es definir una base verificable para el sistema del Portal Integrado de Gestión e Información A+S, recopilando su alcance y lo que queda fuera de este, los actores y su modelo de acceso, las reglas de negocio, las historias de usuario y los requisitos funcionales y no funcionales. La redacción se organiza siguiendo principios de ingeniería de requisitos: cada requisito debe ser necesario, comprensible, singular, factible, trazable y susceptible de validación mediante un resultado observable.

La estructura toma como referencia **ISO/IEC/IEEE 29148:2018** para la especificación y gestión de requisitos, e **ISO/IEC 25010:2023** para ordenar atributos de calidad del producto. Esta referencia no implica certificación ni reemplaza las definiciones del Product Owner.

### 1.1 Convención de estados

| Código | Significado | Uso |
|--------|------------|-----|
| **C** | Confirmado | Respaldado directamente por la reunión o por una decisión ya consolidada |
| **V** | Por validar | Propuesta necesaria para completar el flujo, pero requiere confirmación explícita |
| **P** | Pendiente | No puede especificarse correctamente sin un archivo, regla o decisión faltante |

---

## 2. Alcance del proyecto y exclusiones

### 2.1 Alcance del sistema

- **Plataforma preparada** para registrar, separar y consultar información de los distintos campus y sedes de la Universidad Autónoma de Chile.

- **Carga operativa inicial** con datos de Sede Santiago, Campus Providencia. Los cursos y equipos de períodos anteriores no se reactivan como vigentes; las respuestas históricas de formularios sí se incorporan para consulta, indicadores y mapa territorial.

- **Portal público**: acceso sin autenticación a información general sobre la metodología, noticias, un repositorio de proyectos, estadísticas de impacto agregadas y los formularios dirigidos a personas interesadas en participar en la metodología.

- **Acceso mediante Microsoft Entra ID**: los portales privados de Coordinación y Docencia y el acceso del estudiante informante al formulario de registro de equipos utilizarán la identidad institucional de la Universidad. El estudiante se autenticará únicamente para responder el formulario contextual y no dispondrá de un panel permanente.

- **Portal de Coordinación**: gestión académica, formularios, Socios Comunitarios, cartas, Ruta Docente, evidencias, repositorio, indicadores, mapa, noticias y exportaciones, con filtros combinables.

- **Portal de Docencia**: consulta de asignaturas y secciones, seguimiento de la Ruta A+S, habilitación del formulario de equipos mediante enlace o QR, revisión de registros enviados por estudiantes, asociación con Socios Comunitarios, solicitud de cartas y carga de evidencias.

- **Formularios**: implementación de los formularios definidos en la metodología, entre ellos:
  - Solicitud de Carta de Presentación
  - Resumen de Implementación A+S por docente
  - Registro de Socios Comunitarios Aprendizaje Servicio UA
  - Ficha de Inscripción Emprendedores Investigación de Mercados
  - Encuesta de evaluación de metodología A+S para estudiantes, docentes y Socios Comunitarios
  - Ficha de Inscripción en Programa de Consultoría a Empresas de Ingeniería Civil Industrial
  - Ficha de Inscripción en Programa de Gestión de Procesos de Negocios
  - Formulario del Núcleo de Apoyo Fiscal
  - Encuesta de Satisfacción de Operación Renta

- **Indicadores y trazabilidad**: resultados históricos, Socios Comunitarios únicos y participaciones consultables mediante filtros por campus, sede, año, período, carrera, asignatura, sección/NRC, docente, formulario, comuna y estado; exportación a Excel y mapa público agregado.

- **Reactivación de cursos, secciones o equipos históricos** como registros operativos vigentes. Sus datos podrán conservarse únicamente como antecedentes históricos cuando provengan de los formularios entregados.

### 2.2 Fuera del alcance base

- ❌ Panel o perfil permanente para Dirección de Carrera, estudiantes, Socios Comunitarios o beneficiarios. El estudiante informante podrá autenticarse mediante Microsoft Entra ID únicamente para acceder y responder el formulario compartido por el Docente.

- ❌ Firma electrónica avanzada o distribución libre del recurso de firma autorizado del Coordinador.

- ❌ Integración con SharePoint o acceso directo a sistemas académicos institucionales no autorizados.

- ❌ Verificación automática o bloqueo por cumplimiento del curso habilitante del Docente.

- ❌ Firma electrónica avanzada, códigos públicos de autenticidad de cartas o insignias digitales para estudiantes.

- ❌ Sincronización automática en tiempo real con Microsoft Forms u otros formularios externos; la carga histórica se realizará mediante sus archivos exportados.

- ❌ Reconstrucción automática de un formulario pegando un enlace de Microsoft Forms o de otro proveedor.

**Nota**: Los criterios de aceptación se incluyen únicamente cuando agregan una validación, condición, excepción o resultado que no sea evidente al leer el requisito. **C** identifica requisitos confirmados y **V** aquellos que todavía requieren una decisión institucional antes de comprometer su desarrollo.

---

## 3. Actores y modelo de acceso

| Actor | Acceso | Responsabilidad principal |
|-------|--------|--------------------------|
| **Coordinador A+S** | Autenticado | Administra oferta académica, formularios, Socios Comunitarios, cartas, Ruta, evidencias, repositorio, indicadores, mapa, noticias, importaciones y exportaciones de los campus habilitados. |
| **Docente** | Autenticado | Gestiona sus asignaturas y secciones; comparte formularios, revisa equipos, asigna etiquetas informativas, controla su Ruta, solicita cartas y carga evidencias. |
| **Dirección de Carrera / Secretaría de Estudios** | Enlace individual | Recibe por correo un enlace asociado a su unidad y período y completa la planificación A+S en un formulario tabular, sin disponer de panel permanente. |
| **Estudiante informante** | Enlace o QR con autenticación institucional | Un integrante abre el formulario compartido por el Docente, se autentica mediante Microsoft Entra ID y declara los datos del equipo. Su identidad institucional queda asociada al envío, pero no obtiene permisos especiales ni se verifica su matrícula en la sección. |
| **Socio Comunitario / Beneficiario** | Sin cuenta | Postula, responde encuestas y confirma o rechaza invitaciones mediante formularios o enlaces únicos. |
| **Visitante** | Sin cuenta | Ve noticias, recursos, estadísticas agregadas y el mapa territorial utilizando los filtros públicos. |
| **Servicio de correo institucional** | Integración | Envía cartas, invitaciones y notificaciones desde una cuenta genérica de Coordinación A+S; su dirección y permisos finales requieren habilitación institucional. |
| **Portal institucional de noticias** | Integración | Fuente preferente de noticias A+S. El mecanismo autorizado de consulta debe validarse con la universidad. |

---

## 4. Reglas de negocio

| ID | Regla |
|----|-------|
| **RN-01** | Todo registro académico u operativo debe quedar asociado a un campus y una sede. La carga inicial del piloto corresponde a Sede Santiago, Campus Providencia. |
| **RN-02** | Solo el Coordinador y los Docentes disponen de un panel autenticado. El estudiante informante deberá autenticarse con Microsoft Entra ID para responder el formulario de equipos, pero no dispondrá de un panel permanente. Dirección de Carrera y Socios Comunitarios interactuarán mediante los enlaces o formularios correspondientes. |
| **RN-03** | No existirá una nómina institucional previa de estudiantes. Microsoft Entra ID permitirá identificar la cuenta institucional de quien envía el formulario, pero no acreditará su matrícula ni su pertenencia a la asignatura, NRC o sección. Los datos de los demás integrantes serán declarados por el estudiante informante. |
| **RN-04** | El enlace o QR del equipo aporta automáticamente campus, sede, período, asignatura, NRC y sección; el estudiante no puede cambiar ese contexto. |
| **RN-05** | Toda Carta de Presentación aprobada y distribuida debe pasar por el control del Coordinador. |
| **RN-06** | La carta final se envía en PDF desde la cuenta institucional genérica de Coordinación A+S al correo institucional del Docente; el Docente la entrega a sus estudiantes. |
| **RN-07** | El recurso de firma autorizado del Coordinador solo puede utilizarse en el servidor para generar cartas aprobadas y no debe quedar expuesto ni descargable como imagen independiente. |
| **RN-08** | Quien envía el formulario queda registrado como informante del equipo, no como líder funcional. El Docente puede asignar etiquetas como Líder, Product Owner o Scrum Master sin conceder permisos adicionales. |
| **RN-09** | Cada equipo se asocia a un solo Socio Comunitario; un Socio Comunitario puede trabajar con varios equipos. Los cambios de asociación conservan historial. |
| **RN-10** | Un Socio Comunitario incorporado por un grupo puede utilizarse inmediatamente. El Coordinador revisa la calidad de sus datos y decide si lo habilita para otros grupos; esta revisión no autoriza ni detiene el trabajo ya iniciado. |
| **RN-11** | Una Carta de Presentación admite hasta seis estudiantes para conservar el formato oficial en una página. Si el grupo es mayor, se genera otra solicitud para los integrantes restantes. |
| **RN-12** | Una solicitud de carta no se rechaza ni vence automáticamente por demora. Permanece pendiente y la alerta aumenta su notoriedad con el paso de los días. |
| **RN-13** | Todas las actividades de la Ruta se marcan manualmente por el Docente. Cargar una evidencia no completa una actividad de forma automática. |
| **RN-14** | El avance corresponde al porcentaje de actividades obligatorias completadas. Las actividades opcionales no disminuyen el porcentaje ni bloquean el cierre. |
| **RN-15** | La actividad de cierre es opcional. Si el Docente indica que se realizará, se habilita la invitación y el registro opcional de asistencia del Socio Comunitario; su respuesta no bloquea la Ruta. |
| **RN-16** | RUT, correos, teléfonos, direcciones exactas, evaluaciones individuales y nombres de estudiantes no forman parte de la información pública. |
| **RN-17** | Los formularios guardan datos normalizados y su contexto. Una versión publicada que ya tenga respuestas no se modifica: se crea una nueva versión. |
| **RN-18** | Las respuestas históricas de todos los formularios entregados se solicitarán para una carga masiva. El nuevo período comienza sin cursos ni equipos antiguos activos, pero conserva la historia para consultas, indicadores y mapa. |

---

## 5. Historias de usuario

| ID | Historia |
|----|---------|
| **HU-01** | Como Coordinador, quiero solicitar y consolidar la planificación A+S por campus, sede, carrera y período para habilitar la gestión académica. |
| **HU-02** | Como Docente, quiero ver mis asignaturas y su Ruta A+S para saber qué actividades y evidencias debo completar. |
| **HU-03** | Como Estudiante, quiero autenticarme con mi cuenta institucional y registrar una sola vez los integrantes y el Socio Comunitario de mi equipo desde el enlace de la sección, para dejar el grupo asociado al contexto correcto. |
| **HU-04** | Como Socio Comunitario, quiero enviar mi postulación mediante un formulario público para participar en una convocatoria A+S. |
| **HU-05** | Como Coordinador, quiero revisar Socios Comunitarios y conocer sus asociaciones e historial mediante búsquedas y filtros combinados. |
| **HU-06** | Como estudiante informante o Docente, quiero solicitar una carta para que el Coordinador revise los datos y envíe el PDF firmado al Docente. |
| **HU-07** | Como Docente, quiero completar la Ruta y sus evidencias para registrar el cierre; como Coordinador, quiero ver su estado y descargar las evidencias para acreditación. |
| **HU-08** | Como Coordinador, quiero ver y exportar respuestas e indicadores históricos aplicando filtros combinados para responder solicitudes institucionales y apoyar procesos de acreditación. |
| **HU-09** | Como Coordinador, quiero crear y versionar formularios con preguntas condicionales para adaptar los procesos sin desarrollar un formulario nuevo cada vez. |
| **HU-10** | Como Visitante, quiero ver el impacto territorial agregado de A+S mediante filtros, sin acceder a datos personales. |
| **HU-11** | Como Coordinador, quiero decidir qué documentos son públicos y consultar noticias A+S provenientes idealmente del portal institucional. |
| **HU-12** | Como Dirección de Carrera, quiero completar una tabla guiada desde el enlace recibido por correo para informar las asignaturas A+S sin enredarme con el formato. |

---

## 6. Requisitos funcionales

### 6.1 Acceso y gestión académica

#### Requisitos de autenticación y permisos

| ID | Requisito | Criterios de aceptación | Est. |
|----|-----------|------------------------|------|
| **RF-ACC-01** | El sistema deberá autenticar al Coordinador y a los Docentes mediante la identidad institucional configurada antes de permitir el acceso a sus respectivos paneles. | CA1. Una identidad no autorizada es rechazada sin crear una cuenta local paralela. | **V** |
| **RF-ACC-02** | El sistema deberá aplicar los permisos definidos para el Coordinador y el Docente en la tabla de actores de la Sección 3. | CA1. El Docente no puede operar sobre secciones asignadas a otro Docente ni ejecutar funciones exclusivas de Coordinación. | **C** |
| **RF-ACC-03** | El sistema deberá permitir al Docente ver únicamente las asignaturas y secciones/NRC que tenga asignadas en el período seleccionado. | CA1. El acceso directo a una sección ajena es denegado. | **C** |

#### Requisitos de gestión académica

| ID | Requisito | Criterios de aceptación | Est. |
|----|-----------|------------------------|------|
| **RF-ACA-01** | El sistema deberá permitir al Coordinador registrar y actualizar campus, sedes, años, períodos académicos, carreras, asignaturas, secciones/NRC y docentes participantes. | CA1. Cada sección queda asociada a campus, sede, año, tipo de período (anual, semestral, trimestral o bimestral), nombre del período, carrera y Docente. CA2. La carga inicial utiliza Sede Santiago, Campus Providencia. | **C** |
| **RF-ACA-02** | El sistema deberá permitir al Coordinador enviar a cada Dirección de Carrera o Secretaría de Estudios un enlace individual para informar la planificación A+S de una unidad, campus, sede y período. | CA1. El enlace identifica al destinatario oficial, tiene vigencia configurable y puede reenviarse bajo responsabilidad de quien lo recibe. | **C** |
| **RF-ACA-03** | El sistema deberá presentar mediante ese enlace un formulario tabular equivalente a la planilla de asignaturas entregada, con una fila por sección y listas de opciones donde corresponda. | CA1. Cada fila contempla facultad, carrera, declaración A+S, NRC, campus, sección, asignatura, nivel, horario, estudiantes planificados y datos del Docente. CA2. El usuario puede guardar un borrador y enviar la versión final. | **C** |
| **RF-ACA-04** | Antes de incorporar una planificación, el sistema deberá validar campos obligatorios, formatos y duplicidad de NRC y mostrar un resumen conservado dentro de la plataforma. | CA1. El resumen registra fecha, unidad, período, filas recibidas, aceptadas y observadas, con los errores asociados a cada fila. CA2. Los datos válidos se conservan aunque existan errores en otras filas. | **C** |

---

### 6.2 Registro de equipos y estudiantes

| ID | Requisito | Criterios de aceptación | Est. |
|----|-----------|------------------------|------|
| **RF-EQP-01** | El sistema deberá permitir al Docente habilitar y compartir mediante enlace o código QR el formulario de registro de equipos de una asignatura/sección. | CA1. El enlace queda asociado a la sección y a un período de vigencia; cuando se cierra deja de aceptar respuestas. | **C** |
| **RF-EQP-02** | Antes de mostrar el formulario de registro de equipos, el sistema deberá autenticar al estudiante informante mediante Microsoft Entra ID y aceptar únicamente cuentas institucionales autorizadas. | CA1. Una cuenta no autorizada no puede acceder ni enviar el formulario. CA2. El envío queda asociado al nombre y correo institucional del informante. CA3. La autenticación no acredita matrícula ni pertenencia a la asignatura, NRC o sección. | **V** |
| **RF-EQP-03** | El formulario deberá recibir automáticamente campus, sede, período, asignatura, NRC y sección desde el enlace o QR compartido por el Docente, sin permitir que el estudiante modifique ese contexto. | — | **C** |
| **RF-EQP-04** | El sistema deberá permitir que un integrante registre la cantidad de miembros, sus nombres, RUT y correos institucionales, además del Socio Comunitario con el que trabajará el equipo. | CA1. Se muestran dinámicamente los campos requeridos para la cantidad declarada. CA2. El correo del informante se obtiene de la identidad autenticada; los demás datos son declarados por el estudiante y no acreditan matrícula. | **C** |
| **RF-EQP-05** | Antes del envío, el sistema deberá validar el dígito verificador del RUT, el formato y dominio del correo, los campos obligatorios y los RUT repetidos dentro de la sección, y normalizar la escritura de los nombres. | CA1. Los errores se muestran junto al campo y no borran los datos válidos. | **C** |
| **RF-EQP-06** | Al recibir un envío válido, el sistema deberá generar un número de grupo, crear la nómina interna de sus integrantes y registrar como informante a la identidad institucional autenticada que completó el formulario. | CA1. El informante no obtiene permisos ni la etiqueta de líder de forma automática. CA2. Recargar o reenviar la misma respuesta no crea un segundo grupo. | **C** |
| **RF-EQP-07** | El sistema deberá permitir al Docente revisar y corregir los equipos de su sección y asignar a uno o más estudiantes etiquetas informativas predefinidas o personalizadas. | CA1. Cambiar una etiqueta no altera permisos y toda corrección conserva autor, fecha y valores anterior y nuevo. | **C** |
| **RF-EQP-08** | El sistema deberá asociar cada equipo a un solo Socio Comunitario y permitir al Docente cambiar esa asociación conservando el historial. | CA1. El mismo Socio Comunitario puede quedar asociado a varios equipos. | **C** |

---

### 6.3 Socios Comunitarios

| ID | Requisito | Criterios de aceptación | Est. |
|----|-----------|------------------------|------|
| **RF-SC-01** | El sistema deberá permitir a una persona externa ingresar al formulario público de una convocatoria, completarlo y enviar una postulación. | CA1. El formulario registra la convocatoria de origen. CA2. Después de un envío válido, la respuesta recibe identificador y fecha y se muestra una confirmación de recepción. | **C** |
| **RF-SC-02** | El sistema deberá permitir al Coordinador revisar una postulación y cambiarla de Recibida a Aprobada o Rechazada; una aprobada puede pasar a Disponible, Asignada y Trabajo terminado. | CA1. El rechazo exige un motivo y envía un mensaje que informa la decisión, agradece la participación e invita a una próxima oportunidad. CA2. Cada cambio conserva responsable y fecha. | **C** |
| **RF-SC-03** | El sistema deberá mostrar a los Docentes un catálogo de Socios Comunitarios aprobados que puedan ser seleccionados para sus asignaturas. | CA1. Solo se muestran registros aprobados y disponibles, sin evaluaciones internas. | **C** |
| **RF-SC-04** | El formulario de equipo deberá permitir registrar un Socio Comunitario que no figure en el catálogo y asociarlo inmediatamente al grupo como incorporación provisional. | CA1. El grupo puede trabajar sin esperar la revisión del Coordinador. CA2. El Coordinador corrige sus datos y decide si queda disponible para otros grupos o solo en el historial del equipo. | **C** |
| **RF-SC-05** | El sistema deberá permitir al Coordinador buscar y filtrar Socios Comunitarios por nombre, RUT cuando exista, organización, clasificación, comuna, centro SERCOTEC, campus, sede, carrera, año, período y estado. | CA1. Los filtros pueden combinarse y cada resultado permite abrir el historial del registro. | **C** |
| **RF-SC-06** | El sistema deberá mantener el historial de asociaciones y cambios de cada Socio Comunitario con campus, sedes, períodos, carreras, asignaturas, secciones, equipos y servicios realizados. | CA1. Una nueva asociación no reemplaza las anteriores y el historial puede verse cronológicamente. | **C** |

---

### 6.4 Cartas de Presentación

| ID | Requisito | Criterios de aceptación | Est. |
|----|-----------|------------------------|------|
| **RF-CAR-01** | El sistema deberá permitir al estudiante informante o al Docente solicitar una Carta de Presentación ingresando Docente, correo y RUT del Docente, asignatura, sección, institución, persona receptora, cargo, consideraciones y entre uno y seis estudiantes con nombre y RUT. | CA1. La cantidad seleccionada habilita dinámicamente los campos. Un grupo mayor a seis utiliza una segunda solicitud. | **C** |
| **RF-CAR-02** | Al recibir una solicitud, el sistema deberá asociarla al Docente y a la asignatura/sección y dejarla en estado pendiente de revisión del Coordinador. | CA1. El Docente asociado queda definido como destinatario del documento final. | **C** |
| **RF-CAR-03** | El sistema deberá generar una vista previa de la carta usando la plantilla oficial y los datos ingresados antes de permitir su aprobación. | CA1. La vista previa muestra todos los datos que aparecerán en el PDF y se distingue del documento final firmado. | **C** |
| **RF-CAR-04** | Desde la vista previa, el sistema deberá permitir únicamente al Coordinador corregir los datos de origen y regenerar la carta, sin editar directamente el documento generado. | CA1. Se corrigen los datos visibles de la carta; identificador, campus, sede, fecha e historial no se alteran. CA2. Cada cambio conserva responsable, fecha y valores anterior y nuevo. | **C** |
| **RF-CAR-05** | El sistema deberá mostrar al Coordinador una alerta persistente y notoria mientras existan solicitudes de carta pendientes, indicando cantidad, antigüedad y priorizando la más antigua. | CA1. La alerta aumenta gradualmente su notoriedad cada día y nunca rechaza, vence ni elimina una solicitud de forma automática. | **C** |
| **RF-CAR-06** | El sistema deberá permitir al Coordinador observar una solicitud indicando el motivo por el cual no puede aprobarla. | CA1. Una solicitud observada no genera PDF final ni correo y permanece disponible para corrección y nueva revisión. | **C** |
| **RF-CAR-07** | Al aprobar una solicitud, el sistema deberá generar el PDF final firmado y enviarlo automáticamente desde la cuenta institucional de Coordinación A+S al correo del Docente. | CA1. El PDF utiliza la última vista previa aprobada; el mensaje solicita al Docente comprobar que la carta corresponda antes de entregarla a los estudiantes y la firma no queda expuesta. | **C** |
| **RF-CAR-08** | El sistema deberá registrar el resultado del envío y permitir al Coordinador reintentar un despacho fallido sin generar una carta distinta. | CA1. Se conserva destinatario, fecha, resultado e identificador del PDF; un fallo mantiene la carta aprobada y pendiente de envío. | **C** |

---

### 6.5 Ruta Docente

| ID | Requisito | Criterios de aceptación | Est. |
|----|-----------|------------------------|------|
| **RF-RUT-01** | El sistema deberá permitir al Docente ver las etapas, actividades, formularios y documentos de la Ruta A+S correspondientes a su asignatura. | CA1. La Ruta se muestra por sección y período, junto con el recurso o acción asociado a cada actividad cuando exista. | **C** |
| **RF-RUT-02** | El sistema deberá permitir al Docente marcar manualmente cada actividad de la Ruta como pendiente o completada, con independencia de los archivos cargados. | CA1. Cada cambio conserva fecha y Docente; cargar una evidencia no modifica el estado de la actividad. | **C** |
| **RF-RUT-03** | El sistema deberá calcular la completitud de la Ruta como actividades obligatorias completadas dividido por el total de actividades obligatorias, expresado como porcentaje. | CA1. El resultado muestra porcentaje, actividades completas y pendientes; las opcionales no reducen el avance. | **C** |
| **RF-RUT-04** | El sistema deberá recordar al Docente las acciones pendientes, incluida la invitación previa al Socio Comunitario cuando haya indicado que existirá una actividad de cierre. | CA1. El recordatorio identifica la acción pendiente y se presenta en el momento definido en la Ruta. | **C** |
| **RF-RUT-05** | El sistema deberá permitir al Coordinador ver el porcentaje, las actividades pendientes y el estado de cierre de cada Docente por campus, sede, asignatura/sección y período. | CA1. El Coordinador solo monitorea; no marca actividades ni aprueba el cierre de la Ruta. | **C** |

#### 6.5.1 Evidencias y cierre

| ID | Requisito | Criterios de aceptación | Est. |
|----|-----------|------------------------|------|
| **RF-EVI-01** | El sistema deberá mantener un expediente por asignatura/sección para reunir evidencias y documentos durante el período. | CA1. El expediente identifica campus, sede, período, Docente y sección. | **C** |
| **RF-EVI-02** | El sistema deberá permitir al Docente cargar evidencias PDF, DOC/DOCX, XLS/XLSX, JPG o PNG en las actividades de la Ruta de su asignatura/sección. | CA1. Cada archivo se asocia a una actividad y conserva nombre, tipo, tamaño, fecha y autor; no se admiten videos. | **C** |
| **RF-EVI-03** | El sistema deberá permitir al Coordinador revisar y descargar las evidencias de una asignatura/sección de forma individual o como conjunto para acreditación. | CA1. La descarga identifica campus, sede, año, período, carrera, asignatura, sección y Docente, y solo contiene archivos del expediente seleccionado. | **C** |
| **RF-EVI-04** | El sistema deberá permitir al Docente indicar si se realizará una actividad de cierre para la asignatura/sección. | CA1. Seleccionar que no habrá actividad de cierre no genera incumplimiento ni bloquea la finalización de la Ruta. | **C** |
| **RF-EVI-05** | Cuando el Docente indique que habrá actividad de cierre, el sistema deberá preguntarle si contactará al Socio Comunitario por su cuenta o si desea enviar una invitación desde la plataforma. | CA1. Si elige la plataforma, se envía un correo con enlaces únicos Asistiré y No asistiré y se registra la respuesta; si elige contacto externo, el sistema le recuerda registrar el resultado. | **C** |
| **RF-EVI-06** | El sistema deberá mostrar la asistencia como Asistirá, No asistirá o Sin respuesta, sin utilizarla como condición obligatoria de la Ruta. | — | **C** |
| **RF-EVI-07** | Cuando todas las actividades obligatorias estén completadas, el sistema deberá habilitar al Docente la acción Completar Ruta. | CA1. Las evidencias y actividades opcionales, incluida la asistencia al cierre, no bloquean la habilitación salvo que la Ruta oficial las defina como obligatorias. | **C** |
| **RF-EVI-08** | Al seleccionar Completar Ruta, el sistema deberá registrar el cierre de la asignatura/sección y mostrarlo al Coordinador sin exigir aprobación posterior. | CA1. El cierre conserva fecha, Docente y porcentaje; el Coordinador puede descargar las evidencias. | **C** |

---

### 6.6 Formularios, importación e indicadores

#### Requisitos de formularios

| ID | Requisito | Criterios de aceptación | Est. |
|----|-----------|------------------------|------|
| **RF-FOR-01** | El sistema deberá incluir un módulo para que el Coordinador cree, copie, ordene, publique, cierre y archive formularios. | CA1. Cada formulario conserva identificador, título, versión, estado, vigencia y contexto; las respuestas anteriores permanecen asociadas a la versión contestada. | **C** |
| **RF-FOR-02** | El módulo deberá permitir preguntas de texto corto o largo, número, fecha, correo, RUT, alternativa única, selección múltiple, lista desplegable, escala, carga de archivo y secciones condicionales. | CA1. El Coordinador define obligatoriedad, opciones, orden y reglas de visibilidad sin modificar código. | **C** |
| **RF-FOR-03** | El sistema deberá permitir que la selección de una línea de servicio o programa muestre únicamente las preguntas aplicables y que el Coordinador agregue nuevas líneas y preguntas. | CA1. Las preguntas comunes se responden una vez y las específicas se muestran según la opción elegida; siempre puede configurarse una alternativa Otros. | **C** |
| **RF-FOR-04** | El sistema deberá generar enlaces y códigos QR para las versiones publicadas y dejar de recibir respuestas cuando el Coordinador cierre su vigencia. | — | **C** |
| **RF-FOR-05** | El sistema deberá asociar cada respuesta con su formulario y versión y con el campus, sede, año, período, carrera, asignatura/sección, Docente, proyecto o Socio Comunitario que corresponda. | CA1. Un campo queda sin asociación solo cuando no sea aplicable al proceso. | **C** |

#### Requisitos de migración e importación

| ID | Requisito | Criterios de aceptación | Est. |
|----|-----------|------------------------|------|
| **RF-MIG-01** | El sistema deberá permitir al Coordinador cargar de forma masiva los archivos exportados de todos los formularios históricos entregados por Jorge. | CA1. La carga presenta antes de confirmar el origen, hoja, columnas reconocidas, totales aceptados, observados y omitidos, y la causa por fila. CA2. Conserva archivo de origen, fecha, responsable y correspondencia de campos. | **C** |
| **RF-MIG-02** | La carga histórica deberá incorporar los datos necesarios para encuestas, indicadores y mapa sin crear cursos, secciones o equipos antiguos como registros operativos activos. | — | **C** |

#### Requisitos de indicadores

| ID | Requisito | Criterios de aceptación | Est. |
|----|-----------|------------------------|------|
| **RF-IND-01** | El sistema deberá permitir al Coordinador consultar respuestas e indicadores mediante filtros combinables por campus, sede, año, período, carrera, asignatura, sección/NRC, Docente, formulario, pregunta o métrica, Socio Comunitario, comuna y estado. | CA1. El resultado muestra los filtros aplicados y permite comparar la misma métrica entre años o períodos. | **C** |
| **RF-IND-02** | Los indicadores de Socios Comunitarios deberán distinguir el número de organizaciones únicas del número de participaciones registradas en períodos o actividades. | CA1. Una organización que participa tres veces cuenta como una organización única y tres participaciones. | **C** |
| **RF-IND-03** | El sistema deberá generar el mapa territorial a partir de la información almacenada de los Socios Comunitarios y permitir filtrar sus datos agregados por año, campus/sede, facultad, carrera y comuna. | CA1. El mapa admite datos históricos importados y no expone direcciones exactas ni datos personales. | **C** |
| **RF-IND-04** | El sistema deberá permitir al Coordinador exportar a Excel las respuestas e indicadores filtrados para reportes institucionales y acreditación. | CA1. El archivo identifica los filtros y conserva RUT y teléfonos como texto cuando el rol y la finalidad permiten incluirlos. | **C** |

---

### 6.7 Portal público, repositorio, noticias y comunicaciones

#### Requisitos del portal público

| ID | Requisito | Criterios de aceptación | Est. |
|----|-----------|------------------------|------|
| **RF-PUB-01** | El sistema deberá permitir a un Visitante ver información, proyectos, recursos, estadísticas agregadas y el mapa de impacto que el Coordinador haya definido como públicos, aplicando filtros por campus/sede, año, carrera, comuna o tipo de actividad cuando esos datos estén disponibles. | CA1. Los filtros no exponen documentos internos, respuestas individuales ni datos personales. | **C** |
| **RF-PUB-02** | El sistema deberá permitir al Coordinador administrar un repositorio de archivos PDF, Word y Excel y enlaces externos, indicando título, descripción, categoría y visibilidad pública o privada. | CA1. Puede publicar, retirar o reemplazar un recurso; el portal público nunca muestra los marcados como privados. | **C** |
| **RF-PUB-03** | El sistema deberá obtener idealmente desde una fuente institucional autorizada las noticias relacionadas con A+S y mostrar título, fecha, imagen, resumen y enlace a la publicación original. | CA1. La integración evita duplicados por URL, conserva la última sincronización válida y permite ocultar resultados no pertinentes. CA2. El mecanismo técnico —API, RSS u otro medio autorizado— queda sujeto a validación institucional. | **V** |
| **RF-PUB-04** | El sistema deberá permitir al Coordinador agregar manualmente el enlace de una noticia cuando la fuente institucional no pueda integrarse o no incluya una publicación pertinente. | — | **C** |

#### Requisitos de comunicaciones

| ID | Requisito | Criterios de aceptación | Est. |
|----|-----------|------------------------|------|
| **RF-COM-01** | El sistema deberá permitir al Coordinador utilizar plantillas de correo aprobadas para comunicar aceptación, rechazo, invitación o primer contacto con un Socio Comunitario desde la cuenta institucional genérica de Coordinación A+S. | CA1. Antes del envío se muestran destinatario y contenido; el remitente no corresponde a la cuenta personal del Coordinador. | **C** |
| **RF-COM-02** | El sistema deberá registrar los correos enviados desde la plataforma con remitente, destinatario, asunto, tipo, fecha, responsable y resultado. | CA1. Un envío fallido no cambia el estado de la operación asociada y puede reintentarse. | **C** |

---

## 7. Requisitos no funcionales

### 7.1 Seguridad, privacidad y auditoría

| ID | Requisito de calidad | Criterios de aceptación | Est. |
|----|----------------------|------------------------|------|
| **RNF-SEG-01** | Toda operación del Coordinador o del Docente y todo acceso al formulario de registro de equipos deberán exigir una sesión institucional autenticada y una autorización comprobada en el servidor. Los demás enlaces contextuales deberán utilizar identificadores no predecibles y respetar su vigencia. | CA1. Alterar la URL o la interfaz no permite acceder a otro rol, unidad, sección o formulario. Una cuenta externa o no autorizada no puede acceder ni enviar el formulario de equipos. | **C** |
| **RNF-SEG-02** | La plataforma deberá transmitir información mediante HTTPS con TLS 1.2 o superior en los ambientes expuestos. | CA1. La verificación técnica confirma el protocolo mínimo y las solicitudes HTTP son rechazadas o redirigidas. | **V** |
| **RNF-PRI-01** | El portal público no deberá mostrar RUT, correo, teléfono, dirección exacta, evaluaciones individuales ni nombres de estudiantes. | CA1. Ninguna vista ni exportación pública contiene esos campos. | **C** |
| **RNF-AUD-01** | Las acciones críticas deberán registrar actor, fecha y hora, operación, entidad afectada, resultado y valores anterior y nuevo cuando corresponda. | CA1. Incluye planificación, cartas, formularios, importaciones, Socios Comunitarios, equipos y la identidad del estudiante informante, archivos, visibilidad pública y cierres; el historial no puede ser alterado por el Docente. | **C** |

### 7.2 Usabilidad, rendimiento y compatibilidad

| ID | Requisito de calidad | Criterios de aceptación | Est. |
|----|----------------------|------------------------|------|
| **RNF-USA-01** | Las funciones del sistema deberán ser utilizables en escritorio y móvil entre 360 px y 1440 px de ancho sin perder acciones ni contenido esencial. | CA1. Los flujos principales pueden completarse en ambos rangos sin desplazamiento horizontal, salvo tablas extensas justificadas. | **V** |
| **RNF-USA-02** | Los formularios deberán identificar campos obligatorios y mostrar los errores junto al campo sin borrar los datos válidos ingresados. | CA1. Un envío inválido informa causa y ubicación del error y conserva los valores correctos. | **C** |
| **RNF-USA-03** | El formulario de planificación académica deberá presentar instrucciones breves, una estructura semejante a la planilla entregada y listas de opciones que reduzcan el ingreso libre. | CA1. Una Dirección de Carrera puede completar, guardar y enviar varias filas sin manipular un archivo externo. | **C** |
| **RNF-PER-01** | Bajo una carga de hasta 100 usuarios concurrentes, el 95 % de las vistas y filtros deberá responder en menos de 3 segundos, excluyendo exportaciones y cargas de archivos. | CA1. Una prueba acordada mide el percentil 95 y documenta el resultado. | **V** |
| **RNF-COM-01** | La aplicación web deberá soportar las dos versiones estables más recientes de Microsoft Edge, Google Chrome y Mozilla Firefox al momento de la aceptación. | CA1. Los flujos críticos pasan las pruebas acordadas en cada navegador y se documentan las diferencias conocidas. | **V** |

### 7.3 Calidad de datos, confiabilidad y continuidad

| ID | Requisito de calidad | Criterios de aceptación | Est. |
|----|----------------------|------------------------|------|
| **RNF-DAT-01** | El sistema deberá almacenar de forma separada y normalizada los campos necesarios para filtrar, como campus, sede, nombres, apellidos, RUT, correo, comuna, carrera, año, tipo y nombre del período, asignatura, sección/NRC, Docente, formulario, pregunta o métrica y centro SERCOTEC. | CA1. Los filtros no dependen de separar nombres ni interpretar texto libre; año y período se almacenan en campos distintos. | **C** |
| **RNF-DAT-02** | Una respuesta confirmada no deberá duplicarse por recargar la página o repetir accidentalmente la acción de envío. | CA1. La prueba de reenvío genera un solo registro confirmado y una confirmación inequívoca para el usuario. | **V** |
| **RNF-ARC-01** | Las evidencias no deberán eliminarse automáticamente por antigüedad y cada archivo deberá limitarse inicialmente a 20 MB y cada actividad a 10 archivos. | CA1. Los límites y la retención definitiva se ajustan a la política y capacidad institucional antes de producción. | **V** |
| **RNF-ALC-01** | La plataforma deberá separar la información por campus y sede, aunque la carga inicial del piloto contenga únicamente datos de Sede Santiago, Campus Providencia. | CA1. Todo registro incluye campus y sede y las consultas permiten filtrarlos. CA2. Incorporar posteriormente otra sede no exige rediseñar el modelo ni mezcla sus datos con los de Providencia. | **C** |
| **RNF-INT-01** | Si la fuente institucional de noticias no responde, el portal deberá conservar las noticias obtenidas en la última sincronización válida y mostrar la fecha de actualización al Coordinador. | — | **V** |
| **RNF-MAN-01** | La entrega deberá incluir manual de administración, manual de usuario, diccionario de datos, instrucciones de despliegue y registro de configuraciones externas. | CA1. Una persona distinta del equipo puede desplegar y operar el sistema con la documentación, sin que esta exponga secretos. | **C** |
| **RNF-RES-01** | La estrategia de respaldo y recuperación deberá definir frecuencia, retención, responsable, RPO y RTO antes del paso a producción. | CA1. Existe un procedimiento aprobado, valores acordados y una prueba documentada de restauración. | **V** |

---

## 8. Matriz de trazabilidad

Vinculación entre Historias de Usuario y Requisitos Funcionales:

| HU | Necesidad | Requisitos asociados |
|----|-----------|---------------------|
| **HU-01** | Gestionar planificación académica | RF-ACA-01 a RF-ACA-04 |
| **HU-02** | Seguir la Ruta A+S | RF-ACC-03; RF-RUT-01 a RF-RUT-05 |
| **HU-03** | Registrar equipos y estudiantes | RF-EQP-01 a RF-EQP-08; RF-SC-04 |
| **HU-04** | Postular como Socio Comunitario | RF-SC-01 y RF-SC-02; RF-FOR-04 y RF-FOR-05 |
| **HU-05** | Revisar y asociar Socios Comunitarios | RF-SC-02 a RF-SC-06; RF-EQP-08 |
| **HU-06** | Gestionar Cartas de Presentación | RF-CAR-01 a RF-CAR-08 |
| **HU-07** | Completar Ruta y descargar evidencias | RF-RUT-01 a RF-RUT-05; RF-EVI-01 a RF-EVI-08 |
| **HU-08** | Consultar y exportar históricos | RF-MIG-01 y RF-MIG-02; RF-IND-01 a RF-IND-04 |
| **HU-09** | Crear formularios configurables | RF-FOR-01 a RF-FOR-05 |
| **HU-10** | Ver impacto territorial | RF-PUB-01; RF-IND-02 y RF-IND-03; RNF-PRI-01 |
| **HU-11** | Gestionar recursos y noticias | RF-PUB-02 a RF-PUB-04 |
| **HU-12** | Informar planificación mediante enlace | RF-ACA-02 a RF-ACA-04; RNF-USA-03 |

---

## 9. Dependencias y validaciones externas

### 9.1 Decisiones pendientes de validación

| ID | Decisión pendiente |
|----|-------------------|
| **PV-01** | Confirmar con TI la configuración de Microsoft Entra ID para Coordinador, Docentes y estudiantes informantes, incluyendo las cuentas institucionales autorizadas, el tratamiento de cuentas invitadas, la información de identidad disponible y los permisos requeridos por la aplicación. |
| **PV-02** | Crear o confirmar la cuenta institucional genérica de Coordinación A+S, sus permisos de envío, límites y responsables. En pruebas se utilizará una cuenta no institucional. |
| **PV-03** | Validar la Ruta oficial por tipo de asignatura y señalar sus actividades obligatorias y opcionales para configurar el porcentaje. |
| **PV-04** | Aprobar con TI los límites iniciales de 20 MB por archivo y 10 archivos por actividad y definir la política institucional de conservación. |
| **PV-05** | Confirmar con Comunicaciones o TI una fuente institucional autorizada para noticias A+S —preferentemente API o RSS del portal— y su frecuencia de sincronización. |

### 9.2 Dependencias externas

| ID | Dependencia |
|----|------------|
| **DE-01** | Solicitar y entregar los archivos Excel o CSV con las respuestas de todos los formularios históricos, incluido el registro de Socios Comunitarios que alimentó el mapa territorial, para ejecutar la carga masiva. |
| **DE-02** | Entregar el recurso de firma autorizado y confirmar la configuración final de la plantilla oficial de Carta de Presentación. |

---

## Anexo 1.1: Reglas comunes para formularios

### Definición y estructura

Cada formulario debe tener:
- **Identificador**: único dentro del sistema
- **Título**: descriptivo del propósito
- **Versión**: control de cambios
- **Estado de publicación**: borrador, publicado, cerrado, archivado
- **Fecha de vigencia**: período durante el cual acepta respuestas

### Campos y validaciones

- Los campos obligatorios deben distinguirse de los opcionales y sus validaciones deben definirse antes del desarrollo.

- Campus, sede, RUT, teléfonos, correos, nombres, comunas, carreras, año, tipo y nombre del período, asignaturas, secciones/NRC, docentes, formularios y preguntas o métricas deben almacenarse en campos separados cuando se requieran para filtrar.

- La opción 'Otras' debe guardar tanto la selección como el texto complementario.

- Las escalas de estrellas deben conservar el valor numérico y su rango.

### Gestión de respuestas

- Las respuestas deben registrar su contexto y no depender del nombre del formulario para determinar a qué proceso pertenecen.

### Regla de lectura para cierre de línea base

Un requisito se considera listo para incorporarse a la línea base solo cuando:
1. Su estado sea **C** (Confirmado)
2. Su redacción no contenga términos pendientes
3. Sus criterios de aceptación puedan evaluarse como cumple/no cumple

---

## Anexo 2: Inventario funcional de formularios

| Formulario | Respondente | Grupos de datos | Relación |
|-----------|------------|-----------------|---------|
| **Planificación de asignaturas A+S** | Dirección de Carrera / Secretaría de Estudios | Facultad; carrera; declaración A+S; NRC; campus; sección; asignatura; nivel; horario; estudiantes planificados; RUT, nombre, contrato, capacitación, correo y teléfono del Docente; posible SC. | RF-ACA-02 a RF-ACA-04 |
| **Solicitud de Carta de Presentación** | Estudiante informante autenticado o Docente mediante enlace o QR | Docente, correo y RUT; asignatura y sección; institución y receptor; cargo; uno a seis estudiantes con nombre y RUT; consideraciones. | RF-CAR-01 a RF-CAR-08 |
| **Registro de Socio Comunitario en trabajo** | Estudiante informante o Docente | Organización; representante y cargo; RUT cuando corresponda; teléfono; correo; comuna y dirección; clasificación; campus/sede; carrera; período; servicio; beneficiarios; evaluación. | RF-SC-04 a RF-SC-06 |
| **Postulación a programas / convocatorias** | Emprendedor u organización | Identificación y contacto; emprendimiento; rubro; antigüedad; formalización; trabajadores; centro y asesor SERCOTEC; áreas de apoyo; web/redes; comentarios. | RF-SC-01 y RF-SC-02 |
| **Confirmación de asistencia** | Socio Comunitario | Invitado; actividad; campus/sede; carrera/asignatura; respuesta de asistencia; observación si se define. | RF-EVI-05 y RF-EVI-06 |
| **Evaluación A+S de Socio / Beneficiario** | Socio Comunitario o Beneficiario | Organización; carrera; nombre de quien responde; tipo de participante; campus/sede; preguntas de evaluación y comentarios. | RF-FOR-01 a RF-FOR-05; RF-IND-01 |
| **Evaluación A+S Docentes 2026** | Docente | RUT; período; carrera; asignatura; campus/sede; preguntas de evaluación y comentarios. | RF-FOR-01 a RF-FOR-05; RF-IND-01 |
| **Ficha Consultoría Empresas 2026** | Emprendedor | Identificación; RUT; contacto; emprendimiento; producto; rubro; antigüedad; trabajadores; centro/asesor SERCOTEC; temas de apoyo; redes; requerimientos especiales. | RF-SC-01; RF-FOR-01 a RF-FOR-05 |
| **Ficha Gestión de Procesos de Negocios 2026** | Emprendedor u organización | Identificación; contacto; emprendimiento; formalización; rubro; antigüedad; trabajadores; centro/asesor; temas de apoyo. | RF-SC-01; RF-FOR-01 a RF-FOR-05 |
| **Núcleo Apoyo Fiscal** | Atención registrada | Local; estudiante que atendió y RUT; contribuyente y contacto; dirección/comuna; tipo y motivo de atención; resultado de la consulta. | RF-FOR-01 a RF-FOR-05 |
| **Satisfacción Operación Renta 2026** | Participante | Origen de convocatoria; identificación del participante; campus; escalas de conocimiento, aporte y satisfacción; estudiante que atendió; comentarios. | RF-FOR-01 a RF-FOR-05; RF-IND-01 |

---

**Fin del documento**

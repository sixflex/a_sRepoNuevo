# Inventario Técnico y Mapeo de Formularios Históricos A+S (DE-01 / CDE-325)

## 1. Contexto y Alcance del Requerimiento

El presente documento formaliza el inventario, análisis estructural y matriz de mapeo técnico correspondiente a la tarea **DE-01 (CDE-325: Obtener archivos históricos para carga inicial)** y sus subtareas asociadas (**CDE-335 a CDE-341**).

La Universidad Autónoma de Chile recopiló información del programa de Aprendizaje + Servicio (A+S) mediante formularios institucionales externos (Microsoft Forms / Google Forms) antes del despliegue del portal integrado. Este inventario desglosa los 9 formularios origen, sus estructuras de columnas, períodos, sedes, discrepancias y su correspondencia hacia los modelos de datos en Django (`historicos.CargaHistorica`, `historicos.CargaMapeo`, `historicos.CargaFila`, `socios.SocioComunitario`, `socios.ParticipacionSocio` y `encuestas.RespuestaFormulario`).

---

## 2. Inventario de Formularios de Origen (CDE-335, CDE-336)

| ID Formulario | Nombre Formal del Formulario Origen | `tipo_origen` Django | Total Preguntas / Columnas | Entidad Principal Destino |
| :--- | :--- | :--- | :--- | :--- |
| **FORM-01** | Información para Cartas de Presentación Estudiantes a Socios Comunitarios A+S | `CARTAS_PRESENTACION` | 22 | `socios.ParticipacionSocio` / `cartas.SolicitudCarta` |
| **FORM-02** | Resumen de Implementación A+S por docente - Sede Santiago | `RESUMEN_DOCENTE` | 26 | `historicos.CargaFila` / `academico.Seccion` |
| **FORM-03** | Registro de Socios Comunitarios Aprendizaje Servicio UA | `REGISTRO_SOCIOS` | 22 | `socios.SocioComunitario` |
| **FORM-04** | Ficha de Inscripción Emprendedores Investigación de Mercados | `EMPRENDEDORES_FAN` | 14 | `socios.SocioComunitario` |
| **FORM-05** | Encuesta de Evaluación A+S Estudiantes 2026 | `EVAL_ESTUDIANTES_2026` | 21 (multi-ítem) | `encuestas.RespuestaFormulario` |
| **FORM-06** | Encuesta de Evaluación Socios Comunitarios A+S 2026 | `EVAL_SOCIOS_2026` | 14 (multi-ítem) | `encuestas.RespuestaFormulario` |
| **FORM-07** | Encuesta Evaluación A+S Docentes 2026 | `EVAL_DOCENTES_2026` | 20 (multi-ítem) | `encuestas.RespuestaFormulario` |
| **FORM-08** | Ficha Inscripción Emprendedores Programa Consultoría Empresas 2026 Ing. Civil Industrial | `CONSULTORIA_ICI` | 15 | `socios.SocioComunitario` |
| **FORM-09** | Ficha de Inscripción en Programa de Gestión de Procesos de Negocios 2026 | `PROCESOS_NEGOCIOS` | 14 | `socios.SocioComunitario` |
| **FORM-10** | Núcleo de Apoyo Fiscal (NAF) - Registro de Atenciones Tributarias | `NAF_ATENCIONES` | 13 | `historicos.CargaFila` |
| **FORM-11** | Encuesta de Satisfacción Operación Renta 2026 | `SATISFACCION_RENTA` | 12 | `encuestas.RespuestaFormulario` |

---

## 3. Caracterización por Períodos, Sedes y Hojas (CDE-337)

### 3.1. Períodos Académicos Identificados
* **Años detectados en histórico:** `2021`, `2022`, `2023`, `2024`, `2025`, `2026` y proyección `2027`.
* **Semestres y Modalidades:**
  * Diurno Otoño (Primer Semestre).
  * Diurno Primavera (Segundo Semestre).
  * Vespertino Tech: 1º, 2º y 3º trimestre.
  * Advance: 1º, 2º y 3º trimestre.

### 3.2. Sedes y Campus Reconocidos
* **Sede Santiago:** Campus Providencia, Campus El Llano Subercaseaux, Convenio HUB Providencia.
* **Sede Talca:** Campus Talca.
* **Sede Temuco:** Campus Temuco.
* **Modalidad Virtual:** Reportes transversales e-learning / streaming.

---

## 4. Matriz Detallada de Mapeo de Columnas hacia Modelos Django (CDE-337, CDE-338)

### Formulario 1: Información para Cartas de Presentación (`CARTAS_PRESENTACION`)
| N° | Columna Origen (Excel/Forms) | Tipo Dato | Campo Destino en Django | Obligatorio | Regla de Transformación / Validación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Nombre completo Docente | String | `academico.Docente.nombres` / `apellidos` | Sí | Separar nombre y apellidos; verificar contra usuarios existentes |
| 2 | Correo docente | Email | `academico.Docente.correo_institucional` | Sí | Validar sufijo `@uautonoma.cl` |
| 3 | Rut docente | String | `academico.Docente.rut` | Sí | Normalizar a formato `XXXXXXXX-X` (sin puntos, con guion) |
| 4 | Nombre de la Asignatura | String | `academico.Asignatura.nombre` | Sí | Búsqueda por coincidencia de texto (case-insensitive) |
| 5 | Sección | String | `academico.Seccion.seccion` | Sí | Extraer número entero ("SEC. 1" -> "1") |
| 6 | Asignatura corresponde a FG | String / Bool | `academico.Asignatura.es_formacion_general` | No | True si es 'Si', False en caso contrario |
| 7 | Institución receptora de la carta | String | `socios.SocioComunitario.nombre_organizacion` | Sí | Normalizar texto institucional |
| 8 | Nombre de quien recibirá la carta | String | `socios.SocioComunitario.representante_nombre` | Sí | Campo obligatorio de la contraparte |
| 9 | Cargo del receptor | String | `socios.SocioComunitario.representante_cargo` | No | Limpieza de espacios en blanco |
| 10-21 | Alumnos 1 al 6 (Nombre y RUT) | Strings | `socios.ParticipacionSocio.estudiantes` | No | Desanidar duplas estudiante-RUT; crear o asociar estudiantes |
| 22 | Consideración especial | Text | `cartas.SolicitudCarta.observaciones` | No | Almacenar en texto sin truncar |

### Formulario 2: Resumen de Implementación A+S Docente (`RESUMEN_DOCENTE`)
| N° | Columna Origen (Excel/Forms) | Tipo Dato | Campo Destino en Django | Obligatorio | Regla de Transformación / Validación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1-4 | Datos Identificación Docente (Nombre, RUT, Fono, Correo) | Strings | `academico.Docente` | Sí | Normalizar RUT y correo |
| 5 | Tipo de contrato | Select | `historicos.CargaFila.datos_raw_json['tipo_contrato']` | Sí | Regular / Adjunto |
| 6-7 | Año reportado y Período | Selects | `academico.PeriodoAcademico` | Sí | Mapear contra período activo o crear histórico correspondiente |
| 8-10 | Campus, Facultad, Carrera | Selects | `academico.Campus`, `academico.Carrera` | Sí | Cruce de claves foráneas con tablas académicas maestras |
| 11-14 | Asignatura, Nivel, Cantidad Secciones, Secciones | Strings / Int | `academico.Seccion` | Sí | Resolución de secciones múltiples informadas en un solo registro |
| 15 | Descripción Proyectos A+S | Text | `proyectos.Proyecto.descripcion` | No | Texto descriptivo del servicio |
| 16 | Nota promedio A+S | Decimal / Float | `historicos.CargaFila.datos_raw_json['promedio_as']` | No | Casteo numérico (control de coma por punto decimal) |
| 17-18 | Total estudiantes y Reprobados | Integer | `historicos.CargaFila.datos_raw_json` | No | Control numérico de consistencia (`reprobados <= total`) |
| 19-20 | Cantidad y Tipo de Socios | Int / Checkbox | `socios.ParticipacionSocio` | No | Desglose de categorías (Pyme, Cesfam, Junta Vecinos, etc.) |
| 21-22 | Beneficiarios (Cantidad y Tipo) | Int / Checkbox | `historicos.CargaFila.datos_raw_json` | No | Conteo estimado de impacto territorial |
| 23 | ODS abordados | Multi-check | `proyectos.Proyecto.ods` | No | Arreglo JSON de identificadores ODS (1 a 17) |
| 24-25 | Encuestas y Evidencias enviadas | Selects | `historicos.CargaFila.datos_raw_json` | Sí | Verificación de cumplimiento documental |

### Formulario 3: Registro de Socios Comunitarios UA (`REGISTRO_SOCIOS`)
| N° | Columna Origen (Excel/Forms) | Tipo Dato | Campo Destino en Django | Obligatorio | Regla de Transformación / Validación |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1-4 | Informante (Nombre, RUT, Correo, Rol) | Strings | `usuarios.Usuario` / `historicos.CargaHistorica.responsable` | Sí | Trazabilidad del usuario que declaró el socio |
| 5-7 | Sede, Facultad, Carrera | Selects | `academico.Sede`, `academico.Carrera` | Sí | Vinculación académica territorial |
| 8 | Asignatura vinculada | String | `academico.Asignatura` | No | Búsqueda por texto |
| 9 | Nombre del Socio Comunitario | String | `socios.SocioComunitario.nombre_organizacion` | Sí | Entidad comunitaria principal |
| 10-13 | Contacto (Representante, Cargo, Teléfono, Correo) | Strings | `socios.SocioComunitario` | No | Contacto formal del socio |
| 14-15 | Comuna y Dirección | Strings | `socios.SocioComunitario.comuna`, `direccion` | No | Georreferenciación e impacto comunal |
| 16 | Clasificación Socio | Radio | `socios.SocioComunitario.clasificacion` | Sí | Mapear choices (Fundación, Pyme, Municipalidad, etc.) |
| 17-20 | Período, Beneficiarios, Servicio realizado | Check / Text | `socios.ParticipacionSocio` | No | Registro histórico de la actividad ejecutada |
| 21-22 | Evaluación y Comentarios | Rating 1-5 / Text| `historicos.CargaFila.datos_raw_json` | No | Nivel de satisfacción de la contraparte |

### Formularios 5, 6 y 7: Batería de Encuestas A+S 2026 (`encuestas.RespuestaFormulario`)
* **Estructura común:** 
  * Identificación: RUT informante, sede, carrera, semestre, asignatura.
  * Respuestas Likert (1 a 5): Almacenadas en `datos_raw_json` estructuradas por dimensiones:
    * `DIM_APRENDIZAJE`
    * `DIM_BALANCE_CARGA`
    * `DIM_COMPETENCIAS_INTEGRALES` (Comunicación, Trabajo en Equipo, Pensamiento Crítico, Ética, Responsabilidad Social)
    * `DIM_REFLEXION`
    * `DIM_SERVICIO`
    * `DIM_SOCIO_COMUNITARIO`
  * Textos abiertos: Aspectos positivos y aspectos a mejorar.

---

## 5. Detección de Campos Faltantes y Discrepancias (CDE-338, CDE-339)

1. **Ausencia del código NRC formal:**  
   Los formularios históricos solicitan texto libre para la asignatura y un dropdown o texto simple para la sección ("SEC. 1", "Sección 2"). No capturan el NRC de 5 dígitos requerido por el modelo `academico.Seccion.nrc`.  
   *Solución técnica:* El cargador de datos debe implementar una búsqueda combinada (`asignatura__nombre__icontains` + `periodo` + `seccion`). Si no existe correspondencia exacta, marcar la fila con estado `OBSERVADA` en `historicos.CargaFila`.

2. **Heterogeneidad en formatos de RUT:**  
   En FORM-01, FORM-02 y FORM-04 se identifican preguntas con formatos libres, con puntos o sin guion (`15548766-5`, `15.548.766-5`, `155487665`).  
   *Solución técnica:* Implementar una función de normalización que elimine puntos y espacios, asegure el guion verificador y valide el algoritmo Módulo 11 antes de persistir en `Docente`, `Usuario` o `SocioComunitario`.

3. **Multi-selección y campos agrupados en una sola celda:**  
   En las preguntas de selección múltiple (ODS abordados, actividades fuera de clase, tipos de beneficiarios) las exportaciones de Google Forms y Microsoft Forms concatenan las opciones separadas por punto y coma (`;`).  
   *Solución técnica:* La ingesta debe hacer un split de cadenas y serializar el resultado como lista JSON nativa en `datos_raw_json`.

4. **Diferencias de versiones entre períodos:**  
   * Formularios 2021-2024: No incluían la dimensión explícita de Objetivos de Desarrollo Sostenible (ODS 1 al 17) ni el desglose de competencias transversales.
   * Formularios 2026: Incorporan de forma obligatoria las métricas Likert desagregadas de competencias y el tracking de horas presenciales vs. autónomas.

---

## 6. Registro de Archivos Pendientes y Custodia Segura (CDE-340, CDE-341)

### 6.1. Archivos Pendientes de Recepción
Se deja constancia de que los archivos de datos brutos (.xlsx / .csv) correspondientes a las respuestas acumuladas de los 11 formularios inventariados deben ser descargados y provistos por la Coordinación A+S de la Universidad Autónoma.

### 6.2. Protocolo de Almacenamiento Seguro (Ley 19.628)
Dado que los archivos contienen datos sensibles de personas naturales (nombres, RUTs, teléfonos, correos y evaluaciones docentes/estudiantiles):
1. **Exclusión de Git:** Se añade la ruta `historicos/datos_origen/` al archivo `.gitignore` del proyecto para evitar la subida accidental de información confidencial al repositorio remoto de GitHub.
2. **Ambiente Local:** Las copias de trabajo se conservarán en carpetas locales seguras y encriptadas destinadas exclusivamente al proceso de desarrollo y validación de scripts de carga inicial.
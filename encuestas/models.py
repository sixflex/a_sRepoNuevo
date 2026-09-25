from django.conf import settings
from django.db import models


class FormularioPlantilla(models.Model):
    codigo = models.CharField(
        max_length=60,
        unique=True,
    )

    titulo = models.CharField(max_length=220)

    descripcion = models.TextField(
        null=True,
        blank=True,
    )

    proceso = models.CharField(max_length=60)

    activo = models.BooleanField()

    def __str__(self):
        return self.titulo


class FormularioVersion(models.Model):
    plantilla = models.ForeignKey(
        FormularioPlantilla,
        on_delete=models.PROTECT,
        related_name="versiones",
    )

    creado_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="versiones_formulario_creadas",
    )

    numero_version = models.IntegerField()

    estado = models.CharField(max_length=20)

    contexto_tipo = models.CharField(
        max_length=60,
        null=True,
        blank=True,
    )

    fecha_creacion = models.DateTimeField()

    fecha_publicacion = models.DateTimeField(
        null=True,
        blank=True,
    )

    fecha_inicio_vigencia = models.DateTimeField(
        null=True,
        blank=True,
    )

    fecha_fin_vigencia = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plantilla", "numero_version"],
                name="unique_version_por_formulario_plantilla",
            )
        ]

    def __str__(self):
        return f"{self.plantilla} - Versión {self.numero_version}"


class BloqueFormulario(models.Model):
    formulario_version = models.ForeignKey(
        FormularioVersion,
        on_delete=models.CASCADE,
        related_name="bloques",
    )

    titulo = models.CharField(max_length=220)

    descripcion = models.TextField(
        null=True,
        blank=True,
    )

    orden = models.IntegerField()

    regla_visibilidad_json = models.JSONField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.orden} - {self.titulo}"


class PreguntaFormulario(models.Model):
    version = models.ForeignKey(
        FormularioVersion,
        on_delete=models.CASCADE,
        related_name="preguntas",
    )

    bloque = models.ForeignKey(
        BloqueFormulario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preguntas",
    )

    pregunta_padre = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preguntas_hijas",
    )

    texto = models.TextField()

    tipo = models.CharField(max_length=40)

    obligatoria = models.BooleanField()

    orden = models.IntegerField()

    configuracion_json = models.JSONField(
        null=True,
        blank=True,
    )

    regla_visibilidad_json = models.JSONField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.texto[:50]


class OpcionPregunta(models.Model):
    pregunta = models.ForeignKey(
        PreguntaFormulario,
        on_delete=models.CASCADE,
        related_name="opciones",
    )

    texto = models.CharField(max_length=255)

    valor = models.CharField(max_length=120)

    orden = models.IntegerField()

    es_otras = models.BooleanField()

    def __str__(self):
        return self.texto


class EnlaceFormulario(models.Model):
    version = models.ForeignKey(
        FormularioVersion,
        on_delete=models.PROTECT,
        related_name="enlaces",
    )

    creado_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enlaces_formulario_creados",
    )

    seccion = models.ForeignKey(
        "academico.Seccion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enlaces_formulario",
    )

    equipo = models.ForeignKey(
        "proyectos.Equipo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enlaces_formulario",
    )

    proyecto = models.ForeignKey(
        "proyectos.ProyectoAS",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enlaces_formulario",
    )

    socio = models.ForeignKey(
        "socios.SocioComunitario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enlaces_formulario",
    )

    convocatoria = models.ForeignKey(
        "socios.Convocatoria",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enlaces_formulario",
    )

    token = models.UUIDField(
        unique=True,
        editable=False,
    )

    fecha_inicio = models.DateTimeField()

    fecha_expiracion = models.DateTimeField(
        null=True,
        blank=True,
    )

    activo = models.BooleanField()

    def __str__(self):
        return f"Enlace {self.id} - {self.version}"


class RespuestaFormulario(models.Model):
    version = models.ForeignKey(
        FormularioVersion,
        on_delete=models.PROTECT,
        related_name="respuestas",
    )

    enlace = models.ForeignKey(
        EnlaceFormulario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respuestas",
    )

    sede = models.ForeignKey(
        "academico.Sede",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respuestas_formulario",
    )

    campus = models.ForeignKey(
        "academico.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respuestas_formulario",
    )

    periodo = models.ForeignKey(
        "academico.PeriodoAcademico",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respuestas_formulario",
    )

    carrera = models.ForeignKey(
        "academico.Carrera",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respuestas_formulario",
    )

    asignatura = models.ForeignKey(
        "academico.Asignatura",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respuestas_formulario",
    )

    seccion = models.ForeignKey(
        "academico.Seccion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respuestas_formulario",
    )

    docente = models.ForeignKey(
        "academico.Docente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respuestas_formulario",
    )

    equipo = models.ForeignKey(
        "proyectos.Equipo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respuestas_formulario",
    )

    proyecto = models.ForeignKey(
        "proyectos.ProyectoAS",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respuestas_formulario",
    )

    socio = models.ForeignKey(
        "socios.SocioComunitario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respuestas_formulario",
    )

    fecha_envio = models.DateTimeField()

    origen = models.CharField(max_length=30)

    es_historica = models.BooleanField()

    respondente_tipo = models.CharField(
        max_length=40,
        null=True,
        blank=True,
    )

    respondente_nombre = models.CharField(
        max_length=180,
        null=True,
        blank=True,
    )

    respondente_correo = models.CharField(
        max_length=254,
        null=True,
        blank=True,
    )

    respondente_rut = models.CharField(
        max_length=12,
        null=True,
        blank=True,
    )

    nrc_snapshot = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    seccion_snapshot = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    estado_registro = models.CharField(max_length=20)

    def __str__(self):
        return f"Respuesta formulario {self.id}"


class RespuestaPregunta(models.Model):
    respuesta = models.ForeignKey(
        RespuestaFormulario,
        on_delete=models.CASCADE,
        related_name="respuestas_preguntas",
    )

    pregunta = models.ForeignKey(
        PreguntaFormulario,
        on_delete=models.PROTECT,
        related_name="respuestas",
    )

    valor_texto = models.TextField(
        null=True,
        blank=True,
    )

    valor_numero = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )

    valor_fecha = models.DateTimeField(
        null=True,
        blank=True,
    )

    valor_booleano = models.BooleanField(
        null=True,
        blank=True,
    )

    valor_correo = models.CharField(
        max_length=254,
        null=True,
        blank=True,
    )

    valor_rut = models.CharField(
        max_length=12,
        null=True,
        blank=True,
    )

    valor_escala = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    otro_texto = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["respuesta", "pregunta"],
                name="unique_pregunta_por_respuesta",
            )
        ]

    def __str__(self):
        return f"Respuesta {self.respuesta_id} - Pregunta {self.pregunta_id}"


class RespuestaOpcion(models.Model):
    respuesta_pregunta = models.ForeignKey(
        RespuestaPregunta,
        on_delete=models.CASCADE,
        related_name="opciones_seleccionadas",
    )

    opcion = models.ForeignKey(
        OpcionPregunta,
        on_delete=models.PROTECT,
        related_name="respuestas",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["respuesta_pregunta", "opcion"],
                name="unique_opcion_por_respuesta_pregunta",
            )
        ]

    def __str__(self):
        return f"{self.respuesta_pregunta_id} - {self.opcion_id}"


class RespuestaArchivo(models.Model):
    respuesta_pregunta = models.ForeignKey(
        RespuestaPregunta,
        on_delete=models.CASCADE,
        related_name="archivos",
    )

    archivo = models.OneToOneField(
        "archivos.Archivo",
        on_delete=models.PROTECT,
        related_name="respuesta_archivo",
    )

    def __str__(self):
        return f"Archivo respuesta {self.respuesta_pregunta_id}"
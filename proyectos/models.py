import uuid

from django.conf import settings
from django.db import models
from django.db.models import Prefetch
from django.utils.functional import cached_property

from academico.models import Seccion

# Atributo donde se precargan las participaciones abiertas de cada equipo.
ATRIBUTO_PARTICIPACIONES_VIGENTES = "participaciones_vigentes"


def prefetch_socio_vigente(ruta="participaciones_socios"):
    """
    Prefetch reutilizable para mostrar el socio vigente de muchos equipos
    sin una consulta por equipo. ruta permite usarlo desde otra relación,
    p. ej. prefetch_socio_vigente("equipo__participaciones_socios").
    """
    from socios.models import ParticipacionSocio

    return Prefetch(
        ruta,
        queryset=(
            ParticipacionSocio.objects
            .filter(fecha_fin__isnull=True)
            .select_related("socio")
        ),
        to_attr=ATRIBUTO_PARTICIPACIONES_VIGENTES,
    )


class EquipoQuerySet(models.QuerySet):
    def con_socio_vigente(self):
        return self.prefetch_related(prefetch_socio_vigente())


class ProyectoAS(models.Model):
    nombre = models.CharField(max_length=220)
    descripcion = models.TextField(null=True, blank=True)
    servicio_propuesto = models.TextField(null=True, blank=True)
    estado = models.CharField(max_length=30)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    resumen_publico = models.TextField(null=True, blank=True)
    es_publico = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Proyecto A+S"
        verbose_name_plural = "Proyectos A+S"

    def __str__(self):
        return self.nombre


class Equipo(models.Model):
    seccion = models.ForeignKey(
        Seccion,
        on_delete=models.PROTECT,
        related_name="equipos",
    )
    proyecto = models.ForeignKey(
        ProyectoAS,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipos",
    )
    numero_grupo = models.IntegerField()
    informante_nombre = models.CharField(max_length=180)
    informante_correo = models.CharField(max_length=254)
    informante_entra_id = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )
    clave_idempotencia = models.UUIDField(
    null=True,
    blank=True,
    unique=True,
    editable=False,
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20)

    # El socio del equipo vive en socios.ParticipacionSocio (modelo de BD
    # aprobado: EQUIPO no tiene FK a socio). Ver socio_vigente.
    objects = EquipoQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["seccion", "numero_grupo"],
                name="unique_numero_grupo_por_seccion",
            )
        ]

    def __str__(self):
        return f"{self.seccion} - Grupo {self.numero_grupo}"

    @cached_property
    def socio_vigente(self):
        """
        Socio Comunitario actual del equipo: el de su participación abierta
        (fecha_fin vacía) en ParticipacionSocio. Usa la lista precargada por
        con_socio_vigente()/prefetch_socio_vigente() si existe (sin N+1).
        """
        if hasattr(self, ATRIBUTO_PARTICIPACIONES_VIGENTES):
            vigentes = getattr(self, ATRIBUTO_PARTICIPACIONES_VIGENTES)
            return vigentes[0].socio if vigentes else None

        if self.pk is None:
            return None

        participacion = (
            self.participaciones_socios
            .filter(fecha_fin__isnull=True)
            .select_related("socio")
            .first()
        )
        return participacion.socio if participacion else None


class IntegranteEquipo(models.Model):
    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name="integrantes",
    )
    rut = models.CharField(max_length=12)
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    correo_institucional = models.CharField(max_length=254)
    es_informante = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["equipo", "rut"],
                name="unique_rut_por_equipo",
            )
        ]

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"


class Etiqueta(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class IntegranteEtiqueta(models.Model):
    integrante = models.ForeignKey(
        IntegranteEquipo,
        on_delete=models.CASCADE,
        related_name="etiquetas_asignadas",
    )
    etiqueta = models.ForeignKey(
        Etiqueta,
        on_delete=models.PROTECT,
        related_name="integrantes_asignados",
    )
    asignado_por_docente = models.ForeignKey(
    "academico.Docente",
    on_delete=models.PROTECT,
    related_name="etiquetas_asignadas",
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["integrante", "etiqueta"],
                name="unique_etiqueta_por_integrante",
            )
        ]

class EnlaceRegistroEquipo(models.Model):
    seccion = models.ForeignKey(
        Seccion,
        on_delete=models.PROTECT,
        related_name="enlaces_registro_equipo",
    )
    creado_por_docente = models.ForeignKey(
        "academico.Docente",
        on_delete=models.PROTECT,
        related_name="enlaces_registro_equipo_creados",
    )
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    fecha_inicio = models.DateTimeField()
    fecha_expiracion = models.DateTimeField(
        null=True,
        blank=True,
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"Registro equipo - {self.seccion}"

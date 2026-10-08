import json

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from archivos.validators import get_extensiones_permitidas, validar_extension_archivo, validar_tamano_archivo
from socios.validators import validar_rut_chileno

from . import constantes as c
from . import services
from .models import BloqueFormulario

MENSAJE_OBLIGATORIA = "Esta pregunta es obligatoria."


def _json(regla):
    return json.dumps(regla) if regla else ""


def _rango(minimo, maximo, entre, desde, hasta, sin_limite):
    if minimo is not None and maximo is not None:
        return entre.format(minimo=minimo, maximo=maximo)
    if minimo is not None:
        return desde.format(minimo=minimo)
    if maximo is not None:
        return hasta.format(maximo=maximo)
    return sin_limite


def indicacion(pregunta, config):
    """
    Mensaje automático con el formato esperado según el tipo de pregunta, para
    que quien responde no tenga que adivinarlo (ej. cómo escribir el RUT).
    Se muestra además del texto de ayuda que escriba el Coordinador.
    """
    tipo = pregunta.tipo
    if tipo == c.RUT:
        return "Escríbalo con su dígito verificador, con o sin puntos y guion. Ejemplo: 12.345.678-5"
    if tipo == c.CORREO:
        return "Ejemplo: nombre@correo.cl"
    if tipo == c.FECHA:
        return "Elíjala en el calendario o escríbala como día/mes/año."
    if tipo == c.NUMERO:
        return _rango(
            config.get("minimo"), config.get("maximo"),
            "Solo números, entre {minimo} y {maximo}.", "Solo números, desde {minimo}.",
            "Solo números, hasta {maximo}.", "Solo números.",
        )
    if tipo == c.SELECCION_MULTIPLE:
        return _rango(
            config.get("min_marcadas"), config.get("max_marcadas"),
            "Marque entre {minimo} y {maximo} opciones.", "Marque al menos {minimo} opciones.",
            "Puede marcar hasta {maximo} opciones.", "Puede marcar más de una opción.",
        )
    if tipo == c.ESCALA:
        minimo = config.get("minimo", c.ESCALA_MINIMO_DEFECTO)
        maximo = config.get("maximo", c.ESCALA_MAXIMO_DEFECTO)
        if config.get("estilo") == "numeros":
            return f"Elija un número del {minimo} al {maximo}."
        return f"Elija de 1 a {maximo} estrellas."
    if tipo == c.ARCHIVO:
        extensiones = config.get("extensiones") or get_extensiones_permitidas()
        return (
            f"Formatos: {', '.join(e.upper() for e in extensiones)}. "
            f"Tamaño máximo: {settings.PRIVATE_STORAGE_MAX_FILE_SIZE_MB} MB."
        )
    return ""


# ---------------------------------------------------------------------------
# Formulario que responde la persona (se arma desde la versión)
# ---------------------------------------------------------------------------

class RespuestaFormularioForm(forms.Form):
    """
    Construye un campo por pregunta. Todos los campos son opcionales para
    Django: la obligatoriedad se valida en clean() solo para lo que quedó
    visible según el programa u opción elegida (RF-FOR-03).
    """

    def __init__(self, version, bloques, preguntas, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.version = version
        self.bloques = bloques
        self.preguntas = preguntas
        self.visibilidad = (set(), set(), {})
        self.seleccion = {}
        self.valores = {}
        self.otros = {}
        for pregunta in preguntas:
            self.fields[services.nombre_campo(pregunta)] = self._campo(pregunta)
            if any(o.es_otras for o in pregunta.opciones.all()):
                self.fields[services.nombre_campo_otro(pregunta)] = forms.CharField(
                    required=False, max_length=500,
                )

    def _campo(self, pregunta):
        config = services.configuracion(pregunta)
        tipo = pregunta.tipo
        opciones = [(o.valor, o.texto) for o in services.opciones_ordenadas(pregunta)]
        comunes = {"required": False, "label": pregunta.texto}

        if tipo == c.TEXTO_LARGO:
            return forms.CharField(widget=forms.Textarea, max_length=config.get("largo_max") or 5000, **comunes)
        if tipo == c.NUMERO:
            return forms.DecimalField(
                max_digits=18, decimal_places=4,
                min_value=config.get("minimo"), max_value=config.get("maximo"), **comunes,
            )
        if tipo == c.FECHA:
            return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **comunes)
        if tipo == c.CORREO:
            return forms.EmailField(max_length=254, **comunes)
        if tipo == c.RUT:
            return forms.CharField(max_length=14, **comunes)
        if tipo in (c.ALTERNATIVA_UNICA, c.SELECTOR_PROGRAMA):
            return forms.ChoiceField(choices=opciones, widget=forms.RadioSelect, **comunes)
        if tipo == c.LISTA:
            return forms.ChoiceField(choices=[("", "Seleccione...")] + opciones, **comunes)
        if tipo == c.SELECCION_MULTIPLE:
            return forms.MultipleChoiceField(
                choices=opciones, widget=forms.CheckboxSelectMultiple, **comunes,
            )
        if tipo == c.ESCALA:
            minimo = config.get("minimo", c.ESCALA_MINIMO_DEFECTO)
            maximo = config.get("maximo", c.ESCALA_MAXIMO_DEFECTO)
            return forms.TypedChoiceField(
                choices=[(str(n), str(n)) for n in range(minimo, maximo + 1)],
                coerce=int, empty_value=None, widget=forms.RadioSelect, **comunes,
            )
        if tipo == c.ARCHIVO:
            return forms.FileField(**comunes)
        return forms.CharField(max_length=config.get("largo_max") or 500, **comunes)

    def clean(self):
        datos = super().clean()
        self.seleccion = services.seleccion_desde_datos(self.preguntas, self.data)
        self.visibilidad = services.calcular_visibilidad(self.bloques, self.preguntas, self.seleccion)
        _, visibles, opciones_visibles = self.visibilidad

        for pregunta in self.preguntas:
            nombre = services.nombre_campo(pregunta)
            if pregunta.id not in visibles:
                # Lo que no aplica al programa elegido no se valida ni se guarda.
                for campo in (nombre, services.nombre_campo_otro(pregunta)):
                    datos.pop(campo, None)
                    self._errors.pop(campo, None)
                continue
            if nombre in self.errors:
                continue
            valor = datos.get(nombre)
            vacio = valor in (None, "", [], ())
            if vacio:
                if pregunta.obligatoria:
                    self.add_error(nombre, MENSAJE_OBLIGATORIA)
                continue
            try:
                self.valores[pregunta.id] = self._validar(pregunta, valor, opciones_visibles)
            except ValidationError as error:
                self.add_error(nombre, error)
        return datos

    def _validar(self, pregunta, valor, opciones_visibles):
        config = services.configuracion(pregunta)
        tipo = pregunta.tipo

        if tipo == c.RUT:
            return validar_rut_chileno(valor)

        if tipo == c.ARCHIVO:
            validar_tamano_archivo(valor)
            validar_extension_archivo(valor)
            permitidas = config.get("extensiones")
            extension = valor.name.rsplit(".", 1)[-1].lower() if "." in valor.name else ""
            if permitidas and extension not in permitidas:
                raise ValidationError(
                    "Formato no permitido. Solo se aceptan: "
                    + ", ".join(e.upper() for e in permitidas) + "."
                )
            return valor

        if tipo in c.TIPOS_CON_OPCIONES:
            elegidos = valor if isinstance(valor, list) else [valor]
            permitidas = {o.valor: o for o in opciones_visibles.get(pregunta.id, [])}
            if any(v not in permitidas for v in elegidos):
                raise ValidationError("Elija una opción válida.")
            if tipo == c.SELECCION_MULTIPLE:
                minimo, maximo = config.get("min_marcadas"), config.get("max_marcadas")
                if minimo and len(elegidos) < minimo:
                    raise ValidationError(f"Marque al menos {minimo} opciones.")
                if maximo and len(elegidos) > maximo:
                    raise ValidationError(f"Marque como máximo {maximo} opciones.")
            if any(permitidas[v].es_otras for v in elegidos):
                otro = (self.cleaned_data.get(services.nombre_campo_otro(pregunta)) or "").strip()
                if not otro:
                    raise ValidationError("Indique el detalle de la opción «Otros».")
                self.otros[pregunta.id] = otro
            return valor

        if isinstance(valor, str):
            return valor.strip()
        return valor

    def secciones(self):
        """
        Estructura para la plantilla: cada sección con sus preguntas, el campo
        de Django y si se muestra al cargar la página.
        """
        if self.is_bound and hasattr(self, "cleaned_data"):
            bloques_visibles, preguntas_visibles, opciones_visibles = self.visibilidad
        else:
            seleccion = services.seleccion_desde_datos(self.preguntas, self.data if self.is_bound else None)
            bloques_visibles, preguntas_visibles, opciones_visibles = services.calcular_visibilidad(
                self.bloques, self.preguntas, seleccion,
            )

        por_bloque = {}
        for pregunta in self.preguntas:
            por_bloque.setdefault(pregunta.bloque_id, []).append(pregunta)

        resultado = []
        for bloque in self.bloques:
            items = []
            for pregunta in por_bloque.get(bloque.id, []):
                config = services.configuracion(pregunta)
                reglas_opciones = config.get("visibilidad_opciones") or {}
                visibles_ids = {o.id for o in opciones_visibles.get(pregunta.id, [])}
                nombre_otro = services.nombre_campo_otro(pregunta)
                escala = []
                if pregunta.tipo == c.ESCALA:
                    escala = [
                        str(n) for n in range(
                            config.get("minimo", c.ESCALA_MINIMO_DEFECTO),
                            config.get("maximo", c.ESCALA_MAXIMO_DEFECTO) + 1,
                        )
                    ]
                valor = self[services.nombre_campo(pregunta)].value()
                items.append({
                    "escala": escala,
                    "escala_desc": list(reversed(escala)),
                    "valor": valor if isinstance(valor, list) else ("" if valor is None else str(valor)),
                    "pregunta": pregunta,
                    "config": config,
                    "indicacion": indicacion(pregunta, config),
                    "campo": self[services.nombre_campo(pregunta)],
                    "campo_otro": self[nombre_otro] if nombre_otro in self.fields else None,
                    "visible": pregunta.id in preguntas_visibles,
                    "regla_json": _json(pregunta.regla_visibilidad_json),
                    "condicionante": pregunta.tipo in c.TIPOS_CONDICIONANTES,
                    "opciones": [
                        {
                            "opcion": opcion,
                            "regla_json": _json(reglas_opciones.get(opcion.valor)),
                            "visible": opcion.id in visibles_ids,
                        }
                        for opcion in services.opciones_ordenadas(pregunta)
                    ],
                })
            resultado.append({
                "bloque": bloque,
                "regla_json": _json(bloque.regla_visibilidad_json),
                "visible": bloque.id in bloques_visibles,
                "preguntas": items,
            })
        return resultado


# ---------------------------------------------------------------------------
# Constructor del Coordinador
# ---------------------------------------------------------------------------

class EstiloPortalForm(forms.Form):
    """Agrega las clases de Bootstrap del portal a todos los campos."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
                continue
            clase = "form-select" if isinstance(widget, forms.Select) else "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {clase}".strip()


class FormularioDatosForm(EstiloPortalForm):
    titulo = forms.CharField(
        label="Título", max_length=220, widget=forms.TextInput(attrs={"placeholder": "Formulario sin título"}),
    )
    descripcion = forms.CharField(
        label="Descripción", required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Descripción del formulario"}),
    )
    proceso = forms.CharField(
        label="Proceso", max_length=60, initial="GENERAL",
        help_text="Ej.: INSCRIPCION_EMPRENDEDORES, EVALUACION, SOCIOS.",
    )
    contexto_tipo = forms.CharField(
        label="Tipo de respondente", max_length=60, required=False,
        help_text="Ej.: EMPRENDEDOR, DOCENTE, ESTUDIANTE, SOCIO_COMUNITARIO.",
    )


class ReglaMixin(EstiloPortalForm):
    """Campos 'Mostrar solo si…' comunes a secciones y preguntas."""

    regla_pregunta = forms.TypedChoiceField(
        label="Mostrar solo si la pregunta", required=False, coerce=int, empty_value=None,
    )
    regla_valores = forms.MultipleChoiceField(
        label="tiene alguna de estas respuestas", required=False, widget=forms.CheckboxSelectMultiple,
    )

    def configurar_regla(self, condicionantes, regla_actual=None):
        self.condicionantes = {p.id: p for p in condicionantes}
        self.fields["regla_pregunta"].choices = [("", "Siempre visible")] + [
            (p.id, p.texto[:90]) for p in condicionantes
        ]
        self.fields["regla_valores"].choices = [
            (o.valor, o.texto) for p in condicionantes for o in p.opciones.all()
        ]
        if regla_actual and not self.is_bound:
            self.initial["regla_pregunta"] = regla_actual.get("pregunta")
            self.initial["regla_valores"] = regla_actual.get("valores") or []

    def clean(self):
        datos = super().clean()
        pregunta_id = datos.get("regla_pregunta")
        if pregunta_id:
            pregunta = self.condicionantes.get(pregunta_id)
            validos = {o.valor for o in pregunta.opciones.all()} if pregunta else set()
            valores = [v for v in datos.get("regla_valores") or [] if v in validos]
            if not valores:
                self.add_error("regla_valores", "Elige al menos una respuesta para la condición.")
            datos["regla"] = {"pregunta": pregunta_id, "valores": valores}
        else:
            datos["regla"] = None
        return datos


class SeccionForm(ReglaMixin):
    titulo = forms.CharField(
        label="Título de la sección", max_length=220,
        widget=forms.TextInput(attrs={"placeholder": "Título de la sección"}),
    )
    descripcion = forms.CharField(
        label="Texto de la sección", required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Descripción (opcional)"}),
        help_text="Se muestra al inicio de la sección (por ejemplo, la invitación de un programa).",
    )

    field_order = ["titulo", "descripcion", "regla_pregunta", "regla_valores"]


class PreguntaForm(ReglaMixin):
    texto = forms.CharField(label="Pregunta", widget=forms.Textarea(attrs={"rows": 1, "placeholder": "Pregunta"}))
    ayuda = forms.CharField(
        label="Texto de ayuda", required=False, max_length=500,
        widget=forms.TextInput(attrs={"placeholder": "Descripción o ayuda para quien responde (opcional)"}),
    )
    tipo = forms.ChoiceField(label="Tipo de pregunta", choices=c.TIPOS_PREGUNTA)
    obligatoria = forms.BooleanField(label="Obligatoria", required=False)
    bloque = forms.ModelChoiceField(label="Sección", queryset=BloqueFormulario.objects.none(), empty_label=None)
    dato_respondente = forms.ChoiceField(
        label="Usar como dato de quien responde", choices=c.DATOS_RESPONDENTE, required=False,
    )
    largo_max = forms.IntegerField(label="Largo máximo", required=False, min_value=1, max_value=5000)
    minimo = forms.IntegerField(label="Mínimo", required=False)
    maximo = forms.IntegerField(label="Máximo", required=False)
    estilo_escala = forms.ChoiceField(
        label="Mostrar escala como", required=False,
        choices=[("estrellas", "Estrellas"), ("numeros", "Números")],
    )
    etiqueta_minimo = forms.CharField(label="Etiqueta del mínimo", required=False, max_length=60)
    etiqueta_maximo = forms.CharField(label="Etiqueta del máximo", required=False, max_length=60)
    min_marcadas = forms.IntegerField(label="Marcar al menos", required=False, min_value=1)
    max_marcadas = forms.IntegerField(label="Marcar como máximo", required=False, min_value=1)
    extensiones = forms.CharField(
        label="Formatos permitidos", required=False, max_length=120,
        help_text="Separados por coma, ej.: pdf, docx, jpg. Vacío = los del sistema.",
    )

    field_order = [
        "texto", "ayuda", "tipo", "obligatoria", "bloque", "dato_respondente",
        "largo_max", "minimo", "maximo", "estilo_escala", "etiqueta_minimo",
        "etiqueta_maximo", "min_marcadas", "max_marcadas", "extensiones",
        "regla_pregunta", "regla_valores",
    ]

    def __init__(self, *args, version=None, pregunta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.version = version
        self.pregunta = pregunta
        self.fields["bloque"].queryset = version.bloques.order_by("orden", "id")
        self.fields["bloque"].label_from_instance = lambda b: b.titulo
        self.configurar_regla(
            services.preguntas_condicionantes(version, antes_de=pregunta),
            pregunta.regla_visibilidad_json if pregunta else None,
        )
        if pregunta and not self.is_bound:
            config = services.configuracion(pregunta)
            self.initial.update(
                texto=pregunta.texto,
                tipo=pregunta.tipo,
                obligatoria=pregunta.obligatoria,
                bloque=pregunta.bloque_id,
                ayuda=config.get("ayuda", ""),
                dato_respondente=config.get("dato_respondente", ""),
                largo_max=config.get("largo_max"),
                minimo=config.get("minimo"),
                maximo=config.get("maximo"),
                estilo_escala=config.get("estilo", "estrellas"),
                etiqueta_minimo=config.get("etiqueta_minimo", ""),
                etiqueta_maximo=config.get("etiqueta_maximo", ""),
                min_marcadas=config.get("min_marcadas"),
                max_marcadas=config.get("max_marcadas"),
                extensiones=", ".join(config.get("extensiones") or []),
            )

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo")
        minimo, maximo = datos.get("minimo"), datos.get("maximo")

        if tipo == c.ESCALA:
            minimo = c.ESCALA_MINIMO_DEFECTO if minimo is None else minimo
            maximo = c.ESCALA_MAXIMO_DEFECTO if maximo is None else maximo
            if minimo not in (0, 1):
                self.add_error("minimo", "La escala parte en 0 o en 1.")
            if not (2 <= maximo <= c.ESCALA_MAXIMO_PERMITIDO):
                self.add_error("maximo", f"El máximo de la escala va de 2 a {c.ESCALA_MAXIMO_PERMITIDO}.")
            datos["minimo"], datos["maximo"] = minimo, maximo
        if minimo is not None and maximo is not None and minimo >= maximo:
            self.add_error("maximo", "El máximo debe ser mayor que el mínimo.")

        if tipo == c.SELECTOR_PROGRAMA:
            otro_selector = self.version.preguntas.filter(tipo=c.SELECTOR_PROGRAMA)
            if self.pregunta:
                otro_selector = otro_selector.exclude(pk=self.pregunta.pk)
            if otro_selector.exists():
                self.add_error("tipo", "El formulario ya tiene un selector de programa.")
            if datos.get("regla"):
                self.add_error("regla_pregunta", "El selector de programa no puede depender de otra pregunta.")
        return datos

    def configuracion(self, anterior=None):
        """Arma configuracion_json según el tipo, conservando lo que no se edita aquí."""
        datos = self.cleaned_data
        tipo = datos["tipo"]
        config = {
            k: v for k, v in (anterior or {}).items()
            if k in ("visibilidad_opciones", "opciones")
        }
        if datos.get("ayuda"):
            config["ayuda"] = datos["ayuda"].strip()
        if datos.get("dato_respondente"):
            config["dato_respondente"] = datos["dato_respondente"]
        if tipo in (c.TEXTO_CORTO, c.TEXTO_LARGO) and datos.get("largo_max"):
            config["largo_max"] = datos["largo_max"]
        if tipo in (c.NUMERO, c.ESCALA):
            for clave in ("minimo", "maximo"):
                if datos.get(clave) is not None:
                    config[clave] = datos[clave]
        if tipo == c.ESCALA:
            config["estilo"] = datos.get("estilo_escala") or "estrellas"
            for clave in ("etiqueta_minimo", "etiqueta_maximo"):
                if datos.get(clave):
                    config[clave] = datos[clave].strip()
        if tipo == c.SELECCION_MULTIPLE:
            for clave in ("min_marcadas", "max_marcadas"):
                if datos.get(clave):
                    config[clave] = datos[clave]
        if tipo == c.ARCHIVO and datos.get("extensiones"):
            config["extensiones"] = [
                e.strip().lower().lstrip(".") for e in datos["extensiones"].split(",") if e.strip()
            ]
        if tipo not in c.TIPOS_CON_OPCIONES:
            config.pop("visibilidad_opciones", None)
            config.pop("opciones", None)
        return config or None


class VigenciaForm(EstiloPortalForm):
    fecha_inicio_vigencia = forms.DateTimeField(
        label="Recibe respuestas desde", required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
    )
    fecha_fin_vigencia = forms.DateTimeField(
        label="Recibe respuestas hasta", required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
    )

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get("fecha_inicio_vigencia"), datos.get("fecha_fin_vigencia")
        if inicio and fin and fin <= inicio:
            self.add_error("fecha_fin_vigencia", "La fecha de cierre debe ser posterior al inicio.")
        return datos

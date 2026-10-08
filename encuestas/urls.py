from django.urls import path

from . import views

app_name = "encuestas"

urlpatterns = [
    # Coordinación: constructor de formularios (HU-09)
    path("", views.lista_formularios, name="lista"),
    path("nuevo/", views.crear_formulario, name="crear"),
    path("version/<int:version_id>/", views.editor, name="editor"),
    path("version/<int:version_id>/datos/", views.editar_datos, name="editar_datos"),
    path("version/<int:version_id>/secciones/nueva/", views.crear_seccion, name="crear_seccion"),
    path("version/<int:version_id>/preguntas/nueva/", views.crear_pregunta, name="crear_pregunta"),
    path("version/<int:version_id>/preguntas/ordenar/", views.ordenar_preguntas, name="ordenar_preguntas"),
    path("version/<int:version_id>/vista-previa/", views.vista_previa, name="vista_previa"),
    path("version/<int:version_id>/publicacion/", views.publicacion, name="publicacion"),
    path("version/<int:version_id>/nueva-version/", views.nueva_version, name="nueva_version"),
    path("version/<int:version_id>/copiar/", views.copiar_formulario, name="copiar"),
    path("version/<int:version_id>/respuestas/", views.respuestas, name="respuestas"),
    path("seccion/<int:bloque_id>/", views.editar_seccion, name="editar_seccion"),
    path("seccion/<int:bloque_id>/eliminar/", views.eliminar_seccion, name="eliminar_seccion"),
    path("seccion/<int:bloque_id>/mover/<str:direccion>/", views.mover_seccion, name="mover_seccion"),
    path("pregunta/<int:pregunta_id>/", views.editar_pregunta, name="editar_pregunta"),
    path("pregunta/<int:pregunta_id>/eliminar/", views.eliminar_pregunta, name="eliminar_pregunta"),
    path("pregunta/<int:pregunta_id>/duplicar/", views.duplicar_pregunta, name="duplicar_pregunta"),
    path("pregunta/<int:pregunta_id>/mover/<str:direccion>/", views.mover_pregunta, name="mover_pregunta"),

    # Público: responder por enlace o QR
    path("f/<uuid:token>/", views.responder, name="responder"),
    path("f/<uuid:token>/enviado/", views.enviado, name="enviado"),
]

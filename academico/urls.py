from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  
    #campus
    path('campus/', views.campus_list, name='campus_list'),
    path('campus/crear/', views.campus_create, name='campus_create'),
    path('campus/editar/<int:pk>/', views.campus_update, name='campus_update'),
    path('campus/eliminar/<int:pk>/', views.campus_delete, name='campus_delete'),
    #sede
    path('sede/', views.sede_list, name='sede_list'),
    path('sede/crear/', views.sede_create, name='sede_create'),
    path('sede/editar/<int:pk>/', views.sede_update, name='sede_update'),
    path('sede/eliminar/<int:pk>/', views.sede_delete, name='sede_delete'),
    #facultad
    path('facultades/', views.facultad_list, name='facultad_list'),
    path('facultades/crear/', views.facultad_create, name='facultad_create'),
    path('facultades/editar/<int:pk>/', views.facultad_update, name='facultad_update'),
    path('facultades/eliminar/<int:pk>/', views.facultad_delete, name='facultad_delete'),
    # Carreras
    path('carreras/', views.carrera_list, name='carrera_list'),
    path('carreras/crear/', views.carrera_create, name='carrera_create'),
    path('carreras/editar/<int:pk>/', views.carrera_update, name='carrera_update'),
    path('carreras/eliminar/<int:pk>/', views.carrera_delete, name='carrera_delete'),
    # Asignaturas
    path('asignaturas/', views.asignatura_list, name='asignatura_list'),
    path('asignaturas/crear/', views.asignatura_create, name='asignatura_create'),
    path('asignaturas/editar/<int:pk>/', views.asignatura_update, name='asignatura_update'),
    path('asignaturas/eliminar/<int:pk>/', views.asignatura_delete, name='asignatura_delete'),
     # Secciones / NRC
    path('secciones/', views.seccion_list, name='seccion_list'),
    path('secciones/crear/', views.seccion_create, name='seccion_create'),
    path('secciones/editar/<int:pk>/', views.seccion_update, name='seccion_update'),
    path('secciones/eliminar/<int:pk>/', views.seccion_delete, name='seccion_delete'),
    # Docentes
    path('docentes/', views.docente_list, name='docente_list'),
    path('docentes/crear/', views.docente_create, name='docente_create'),
    path('docentes/editar/<int:pk>/', views.docente_update, name='docente_update'),
    path('docentes/eliminar/<int:pk>/', views.docente_delete, name='docente_delete'),
    # Periodos
    path('periodos/', views.periodo_list, name='periodo_list'),
    path('periodos/crear/', views.periodo_create, name='periodo_create'),
    path('periodos/editar/<int:pk>/', views.periodo_update, name='periodo_update'),
    path('periodos/eliminar/<int:pk>/', views.periodo_delete, name='periodo_delete'),
]
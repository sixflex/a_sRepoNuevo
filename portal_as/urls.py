from django.contrib import admin
from django.urls import path
from core.views import inicio  # <--- Importa la vista

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', inicio, name='inicio'),  # <--- Agrega la ruta raíz
]
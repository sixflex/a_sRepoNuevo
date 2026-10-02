from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Archivo
from .services import abrir_archivo, guardar_archivo
from .validators import validar_cantidad_archivos, validar_tamano_archivo


class ArchivoServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="usuario_archivos",
            password="test-pass-123",
        )
        self.storage = InMemoryStorage()

    def test_guardar_archivo_registra_metadatos_y_binario_fuera_de_bd(self):
        contenido = b"contenido de prueba"
        subido = SimpleUploadedFile(
            "Informe.Final.PDF",
            contenido,
            content_type="application/pdf",
        )

        archivo = guardar_archivo(
            subido,
            autor=self.user,
            storage=self.storage,
        )

        self.assertEqual(archivo.nombre_original, "Informe.Final.PDF")
        self.assertEqual(archivo.extension, "pdf")
        self.assertEqual(archivo.mime_type, "application/pdf")
        self.assertEqual(archivo.tamano_bytes, len(contenido))
        self.assertEqual(archivo.cargado_por_usuario, self.user)
        self.assertEqual(len(archivo.hash_sha256), 64)
        self.assertTrue(self.storage.exists(archivo.storage_key))

        binary_fields = [
            field
            for field in Archivo._meta.fields
            if field.get_internal_type() == "BinaryField"
        ]
        self.assertEqual(binary_fields, [])

    def test_abrir_archivo_recupera_contenido_desde_storage(self):
        contenido = b"archivo privado"
        subido = SimpleUploadedFile(
            "privado.pdf",
            contenido,
            content_type="application/pdf",
        )

        archivo = guardar_archivo(
            subido,
            autor=self.user,
            storage=self.storage,
        )

        with abrir_archivo(archivo, storage=self.storage) as manejador:
            self.assertEqual(manejador.read(), contenido)
        archivo = guardar_archivo(
            subido,
            autor=self.user,
            storage=self.storage,
        )

        with abrir_archivo(archivo, storage=self.storage) as manejador:
            self.assertEqual(manejador.read(), contenido)

    def test_servicio_admite_otro_proveedor_sin_cambiar_reglas_de_negocio(self):
        otro_storage = InMemoryStorage()
        subido = SimpleUploadedFile(
            "cambio-proveedor.pdf",
            b"contenido",
            content_type="application/pdf",
        )

        archivo = guardar_archivo(
            subido,
            autor=self.user,
            storage=otro_storage,
        )

        self.assertTrue(otro_storage.exists(archivo.storage_key))

    @override_settings(PRIVATE_STORAGE_MAX_FILE_SIZE_MB=1)
    def test_rechaza_archivo_que_supera_limite_configurado(self):
        subido = SimpleUploadedFile(
            "grande.bin",
            b"x" * (1024 * 1024 + 1),
            content_type="application/octet-stream",
        )

        with self.assertRaises(ValidationError):
            validar_tamano_archivo(subido)

    @override_settings(PRIVATE_STORAGE_MAX_FILES_PER_ACTIVITY=10)
    def test_rechaza_cantidad_sobre_limite_configurado(self):
        with self.assertRaises(ValidationError):
            validar_cantidad_archivos(
                cantidad_actual=10,
                cantidad_nueva=1,
            )


class ArchivoDownloadTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.autor = User.objects.create_user(
            username="autor_archivo",
            password="test-pass-123",
        )
        self.otro_usuario = User.objects.create_user(
            username="otro_usuario",
            password="test-pass-123",
        )
        self.coordinador = User.objects.create_user(
            username="coordinador_archivos",
            password="test-pass-123",
        )

        grupo, _ = Group.objects.get_or_create(name="Coordinador")
        self.coordinador.groups.add(grupo)

        self.archivo = Archivo.objects.create(
            cargado_por_usuario=self.autor,
            nombre_original="privado.pdf",
            extension="pdf",
            storage_key="2026/09/privado.pdf",
            mime_type="application/pdf",
            tamano_bytes=7,
            hash_sha256="a" * 64,
        )

        self.url = reverse(
            "archivos:descargar",
            args=[self.archivo.pk],
        )

    def test_anonimo_no_puede_descargar(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_usuario_no_autorizado_recibe_403(self):
        self.client.force_login(self.otro_usuario)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    @patch("archivos.views.abrir_archivo")
    def test_autor_puede_descargar(self, abrir_mock):
        abrir_mock.return_value = BytesIO(b"privado")

        self.client.force_login(self.autor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            b"".join(response.streaming_content),
            b"privado",
        )

    @patch("archivos.views.abrir_archivo")
    def test_coordinador_puede_descargar(self, abrir_mock):
        abrir_mock.return_value = BytesIO(b"privado")

        self.client.force_login(self.coordinador)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_storage_privado_no_tiene_ruta_publica_directa(self):
        response = self.client.get(
            f"/private_uploads/{self.archivo.storage_key}"
        )
        self.assertEqual(response.status_code, 404)

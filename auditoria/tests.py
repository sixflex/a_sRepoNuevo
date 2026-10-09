from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from auditoria.models import AuditoriaCambio
from auditoria.services import registrar_auditoria

Usuario = get_user_model()


class AuditoriaServicioTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.usuario = Usuario.objects.create_user(
            username="test_user",
            email="test@um.cl",
            password="password123"
        )

    def test_registrar_auditoria_con_request_y_usuario(self):
        request = self.factory.get("/dummy-path/")
        request.user = self.usuario
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        auditoria = registrar_auditoria(
            request=request,
            entidad="SocioComunitario",
            entidad_id=1,
            accion="CREAR",
            valores_nuevos={"nombre_organizacion": "Organización Prueba"}
        )

        self.assertIsNotNone(auditoria.pk)
        self.assertEqual(auditoria.usuario, self.usuario)
        self.assertEqual(auditoria.entidad, "SocioComunitario")
        self.assertEqual(auditoria.entidad_id, "1")
        self.assertEqual(auditoria.accion, "CREAR")
        self.assertEqual(auditoria.ip, "127.0.0.1")
        self.assertEqual(auditoria.valores_nuevos_json["nombre_organizacion"], "Organización Prueba")

    def test_permisos_inmutabilidad_admin(self):
        from auditoria.admin import AuditoriaCambioAdmin
        from django.contrib.admin.sites import AdminSite

        site = AdminSite()
        admin_instance = AuditoriaCambioAdmin(AuditoriaCambio, site)

        self.assertFalse(admin_instance.has_add_permission(None))
        self.assertFalse(admin_instance.has_change_permission(None))
        self.assertFalse(admin_instance.has_delete_permission(None))
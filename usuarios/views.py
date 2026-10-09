from django.contrib.auth.views import LoginView


class LoginTemporalView(LoginView):
    template_name = "usuarios/login.html"
    redirect_authenticated_user = True
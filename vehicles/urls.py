# vehicles/urls.py

from django.contrib.auth.decorators import login_required
from django.urls import path
from django.views.generic import TemplateView

app_name = "vehicles"

urlpatterns = [
    # Простая HTML-страница «Мои машины» (можно использовать в будущем).
    path(
        "my/",
        login_required(
            TemplateView.as_view(template_name="vehicles/my_vehicles.html")
        ),
        name="my_vehicles",
    ),
]

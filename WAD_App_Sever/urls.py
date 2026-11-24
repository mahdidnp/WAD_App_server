"""
URL configuration for WAD_App_Sever project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from devices import views as device_views
from messaging import views as messaging_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", device_views.home, name="home"),
    path("signup/", device_views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", device_views.dashboard, name="dashboard"),
    path("telegram/link/", messaging_views.create_telegram_link, name="create_telegram_link"),
    path("telegram/unlink/", messaging_views.unlink_telegram, name="unlink_telegram"),
    path("devices/<str:device_id>/unclaim/", device_views.unclaim_device, name="unclaim_device"),
]
from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("send-otp/", views.send_otp_view, name="send_otp"),
    path("verify-otp/", views.verify_otp_view, name="verify_otp"),
    path("welcome/", views.welcome_view, name="welcome"),
    path("onboarding/<int:step>/", views.onboarding_step_view, name="onboarding_step"),
    path("edit-profile/", views.edit_profile, name="edit_profile"),
    path("photo/<uuid:photo_id>/delete/", views.delete_photo_view, name="delete_photo"),
]

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet,
    SignupView,
    LoginView,
    RefreshTokenView,
    LogoutView,
    signup_page,
    login_page,
    logout_page,
    profile_page,
    settings_page,
)

app_name = 'users'

# API Router
router = DefaultRouter()
router.register(r'', UserViewSet, basename='user')

# API URLs
api_urlpatterns = [
    path('auth/signup/', SignupView.as_view(), name='api_signup'),
    path('auth/login/', LoginView.as_view(), name='api_login'),
    path('auth/refresh/', RefreshTokenView.as_view(), name='api_refresh_token'),
    path('auth/logout/', LogoutView.as_view(), name='api_logout'),
    path('', include(router.urls)),
]

# Web URLs (template views)
urlpatterns = [
    path('signup/', signup_page, name='signup'),
    path('login/', login_page, name='login'),
    path('logout/', logout_page, name='logout'),
    path('profile/', profile_page, name='profile'),
    path('settings/', settings_page, name='settings'),
]

from django.urls import path
from .views import signup_page, login_page

app_name = 'users'

urlpatterns = [
    path('signup/', signup_page, name='signup'),
    path('login/', login_page, name='login'),
]

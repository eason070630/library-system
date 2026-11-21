
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from members.views import dashboard, landing

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', landing, name='home'),
    path('dashboard/', dashboard, name='dashboard'),
    path('members/', include('members.urls')),
    path('categories/', include('categories.urls')),
    path('appointments/', include('appointments.urls')),
    path('borrowing/', include('borrowing.urls')),
    path('accounts/', include('accounts.urls')),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )

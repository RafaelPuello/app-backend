from django.urls import path

from .views import (
    detail_nfctag,
    disconnect_nfctag,
    edit_nfctag,
    list_nfctags,
    register_nfctag,
)

app_name = "domain"

urlpatterns = [
    path('', list_nfctags, name='list_nfctags'),
    path('<uuid:nfctag_uuid>/', detail_nfctag, name='detail_nfctag'),
    path('<uuid:nfctag_uuid>/edit', edit_nfctag, name='edit_nfctag'),
    path('<uuid:nfctag_uuid>/register', register_nfctag, name='register_nfctag'),
    path('<uuid:nfctag_uuid>/disconnect', disconnect_nfctag, name='disconnect_nfctag'),
]

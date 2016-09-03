from django.conf.urls import include, url

urlpatterns = [
    url(r'^api/', include('analysis.urls')),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework'))
]

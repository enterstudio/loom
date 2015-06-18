from django.conf.urls import patterns, include, url

urlpatterns = patterns('',
    url(r'^api/', include('analyses.urls')),
    url(r'^editor$', 'editor.views.index'),
)

from django.contrib.staticfiles.urls import staticfiles_urlpatterns
urlpatterns += staticfiles_urlpatterns()

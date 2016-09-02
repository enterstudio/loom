from django.conf.urls import patterns, include, url
from rest_framework import routers

from analysis.models import *
from analysis import views


router = routers.DefaultRouter()

router.register('imported-workflows', views.ImportedWorkflowViewSet, base_name='ImportedWorkflow')
router.register('run-requests', views.RunRequestViewSet, base_name='RunRequest')
router.register('files', views.FileDataObjectViewSet, base_name='File')
router.register('imported-files', views.ImportedFileDataObjectViewSet, base_name='ImportedFile')
router.register('result-files', views.ResultFileDataObjectViewSet, base_name='ResultFile')
router.register('log-files', views.LogFileDataObjectViewSet, base_name='LogFile')

router.register('workflows', views.WorkflowViewSet, base_name='Workflow')
router.register('workflow-runs', views.WorkflowRunViewSet)
router.register('task-runs', views.TaskRunViewSet)
router.register('task-run-attempts', views.TaskRunAttemptViewSet)
router.register('task-run-attempt-outputs', views.TaskRunAttemptOutputViewSet)
#router.register('data-objects', views.DataObjectViewSet, base_name='DataObject')
router.register('file-imports', views.FileImportViewSet)
router.register('file-locations', views.FileLocationViewSet)


file_provenance_detail = views.FileProvenanceViewSet.as_view({'get':'retrieve'})

urlpatterns = patterns(
    '',
    url(r'^', include(router.urls)),
    url(r'^file-data-objects/(?P<pk>[a-zA-Z0-9]+)/provenance/$', file_provenance_detail, name='file_provenance_detail'),
    url(r'^status/$', 'analysis.views.status'),
    url(r'^info/$', 'analysis.views.info'),
    url(r'^filehandler-settings/$', 'analysis.views.filehandler_settings'),
    url(r'^task-run-attempts/(?P<id>[a-zA-Z0-9_\-]+)/worker-settings/$', 'analysis.views.worker_settings'),
    #url(r'^controls/refresh/$', 'analysis.views.refresh'),
    url(r'^task-run-attempts/(?P<id>[a-zA-Z0-9_\-]+)/task-run-attempt-log-files/$', 'analysis.views.create_task_run_attempt_log_file')
)

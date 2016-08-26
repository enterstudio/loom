from django.conf.urls import patterns, include, url
from rest_framework import routers

from analysis.models import *
from analysis import views


router = routers.DefaultRouter()

router.register('abstract-workflow-runs', views.WorkflowRunViewSet)
router.register(FileDataObject.get_class_name(plural=True, hyphen=True), views.FileDataObjectViewSet, base_name='FileDataObject')
router.register(DataObject.get_class_name(plural=True, hyphen=True), views.DataObjectViewSet, base_name='DataObject')
router.register('imported-file-data-objects', views.ImportedFileDataObjectViewSet)
router.register('result-file-data-objects', views.ResultFileDataObjectViewSet)
router.register('log-file-data-objects', views.LogFileDataObjectViewSet)
router.register(FileImport.get_class_name(plural=True, hyphen=True), views.FileImportViewSet)
router.register(FileLocation.get_class_name(plural=True, hyphen=True), views.FileLocationViewSet)
router.register(RunRequest.get_class_name(plural=True, hyphen=True), views.RunRequestViewSet, base_name='RunRequest')
router.register(TaskRun.get_class_name(plural=True, hyphen=True), views.TaskRunViewSet)
router.register(TaskRunAttempt.get_class_name(plural=True, hyphen=True), views.TaskRunAttemptViewSet)
router.register(TaskRunAttemptOutput.get_class_name(plural=True, hyphen=True), views.TaskRunAttemptOutputViewSet)
router.register(UnnamedFileContent.get_class_name(plural=True, hyphen=True), views.UnnamedFileContentViewSet)
router.register('abstract-workflows', views.WorkflowViewSet, base_name='Workflow')
router.register('imported-workflows', views.ImportedWorkflowViewSet, base_name='ImportedWorkflow')

urlpatterns = patterns(
    '',
    url(r'^', include(router.urls)),
    url(r'^status/$', 'analysis.views.status'),
    url(r'^info/$', 'analysis.views.info'),
    url(r'^filehandler-settings/$', 'analysis.views.filehandler_settings'),
    url(r'^%s/(?P<id>[a-zA-Z0-9_\-]+)/worker-settings/$' % TaskRunAttempt.get_class_name(plural=True, hyphen=True), 'analysis.views.worker_settings'),
    #url(r'^controls/refresh/$', 'analysis.views.refresh'),
    url(r'^%s/(?P<id>[a-zA-Z0-9_\-]+)/%s/$' %
        (TaskRunAttempt.get_class_name(plural=True, hyphen=True),
         TaskRunAttemptLogFile.get_class_name(plural=True, hyphen=True)),
        'analysis.views.create_task_run_attempt_log_file')
)

"""
urlpatterns.append(url(r'^%s/(?P<id>[a-zA-Z0-9_\-]+)/file-locations/$' % FileDataObject.get_class_name(plural=True, hyphen=True), 'analysis.views.locations_by_file'))
urlpatterns.append(url(r'^%s/(?P<id>[a-zA-Z0-9_\-]+)/file-imports/$' % FileDataObject.get_class_name(plural=True, hyphen=True), 'analysis.views.file_imports_by_file'))
urlpatterns.append(url(r'^%s/(?P<id>[a-zA-Z0-9_\-]+)/source-runs/$' % FileDataObject.get_class_name(plural=True, hyphen=True), 'analysis.views.file_data_source_runs'))
urlpatterns.append(url(r'^imported-file-data-objects/$', 'analysis.views.imported_file_data_objects'))
urlpatterns.append(url(r'^result-file-data-objects/$', 'analysis.views.result_file_data_objects'))
"""

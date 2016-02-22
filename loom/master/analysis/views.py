import logging
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from analysis.models import WorkflowRun, FileDataObject

logger = logging.getLogger('loom')

class Helper:

    @classmethod
    def create(cls, request, model_class):
        data_json = request.body
        try:
            model = model_class.create(data_json)
            return JsonResponse({"message": "created %s" % model_class.get_class_name(), "_id": str(model._id), "object": model.to_struct()}, status=201)
        except Exception as e:
            logger.error('Failed to create %s with data "%s". %s' % (model_class, data_json, e.message))
            return JsonResponse({"message": e.message}, status=400)

    @classmethod
    def index(cls, request, model_class):
        query_string = request.GET.get('q')
        if query_string is None:
            model_list = model_class.objects.all()
        else:
            model_list = model_class.get_by_name_or_id(query_string)
        return JsonResponse(
            {
                model_class.get_class_name(plural=True):
                [model.to_struct() for model in model_list]
            },
            status=200)

    @classmethod
    def show(cls, request, id, model_class):
        try:
            model = model_class.get_by_id(id)
        except ObjectDoesNotExist:
            return JsonResponse({"message": "Not Found"}, status=404)
        return JsonResponse(model.to_struct(), status=200)

    @classmethod
    def update(cls, request, id, model_class):
        model = model_class.get_by_id(id)
        data_json = request.body
        try:
            model.update(data_json)
            return JsonResponse({"message": "updated %s _id=%s" % (model_class.get_class_name(), model._id)}, status=201)
        except Exception as e:
            logger.error('Failed to update %s with data "%s". %s' % (model_class, data_json, e.message))
            return JsonResponse({"message": e.message}, status=400)

@require_http_methods(["GET"])
def status(request):
    return JsonResponse({"message": "server is up"}, status=200)

@require_http_methods(["GET"])
def servertime(request):
    return JsonResponse({"time": timezone.now().isoformat()}, status=200)

@require_http_methods(["GET"])
def workerinfo(request):
    workerinfo = {
        'FILE_SERVER_FOR_WORKER': settings.FILE_SERVER_FOR_WORKER,
        'FILE_ROOT_FOR_WORKER': settings.FILE_ROOT_FOR_WORKER,
        'WORKER_LOGFILE': settings.WORKER_LOGFILE,
        'LOG_LEVEL': settings.LOG_LEVEL,
        }
    return JsonResponse({'workerinfo': workerinfo})

@require_http_methods(["GET"])
def filehandlerinfo(request):
    filehandlerinfo = {
        'FILE_SERVER_FOR_WORKER': settings.FILE_SERVER_FOR_WORKER,
        'FILE_SERVER_TYPE': settings.FILE_SERVER_TYPE,
        'FILE_ROOT': settings.FILE_ROOT,
        'IMPORT_DIR': settings.IMPORT_DIR,
        'STEP_RUNS_DIR': settings.STEP_RUNS_DIR,
        'BUCKET_ID': settings.BUCKET_ID,
        'PROJECT_ID': settings.PROJECT_ID,
        }
    return JsonResponse({'filehandlerinfo': filehandlerinfo})
"""
@csrf_exempt
@require_http_methods(["POST"])
def submitworkflow(request):
    data_json = request.body
    try:
        workflow = Workflow.create(data_json)
        logger.info('Created workflow %s' % workflow._id)
        return JsonResponse({"message": "created %s" % workflow.get_class_name(), "_id": str(workflow._id)}, status=201)
    except Exception as e:
        logger.error('Failed to create workflow with data "%s". %s' % (data_json, e.message))
        return JsonResponse({"message": e.message}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def submitresult(request):
    data_json = request.body
    try:
        result = StepRun.submit_result(data_json)
        return JsonResponse({"message": "created new %s" % result.get_class_name(), "_id": str(result._id)}, status=201)
    except Exception as e:
        logger.error('Failed to create result with data "%s". %s' % (data_json, e.message))
        return JsonResponse({"message": e.message}, status=500)
"""

@csrf_exempt
@require_http_methods(["GET", "POST"])
def create_or_index(request, model_class):
    if request.method == "POST":
        return Helper.create(request, model_class)
    else:
        return Helper.index(request, model_class)
   
@csrf_exempt
@require_http_methods(["GET", "POST"])
def show_or_update(request, id, model_class):
    if request.method == "POST":
        return Helper.update(request, id, model_class)
    else:
        return Helper.show(request, id, model_class)

"""
@csrf_exempt
@require_http_methods(["GET"])
def show_input_port_bundles(request, id):
    step_run = StepRun.get_by_id(id)
    input_port_bundles = step_run.get_input_bundles()
    return JsonResponse({"input_port_bundles": input_port_bundles}, status=200)

"""

@require_http_methods(["GET"])
def storage_locations_by_file(request, id):
    try:
        file = FileDataObject.get_by_id(id)
    except ObjectDoesNotExist:
        return JsonResponse({"message": "Not Found"}, status=404)
    return JsonResponse({"file_storage_locations": [o.to_struct() for o in file.file_contents.file_storage_locations.all()]}, status=200)

@require_http_methods(["GET"])
def data_source_records_by_file(request, id):
    try:
        file = FileDataObject.get_by_id(id)
    except ObjectDoesNotExist:
        return JsonResponse({"message": "Not Found"}, status=404)
    return JsonResponse({"data_source_records": [o.to_struct() for o in file.data_source_records.all()]}, status=200)

@csrf_exempt
@require_http_methods(["GET"])
def dashboard(request):
    # Display all active Workflows plus the last n closed Workflows

    def _get_count(request):
        DEFAULT_COUNT_STR = '10'
        count_str = request.GET.get('count', DEFAULT_COUNT_STR)
        try:
            count = int(count_str)
        except ValueError as e:
            count = int(DEFAULT_COUNT_STR)
        if count < 0:
            count = int(DEFAULT_COUNT_STR)
        return count

    def _get_step_info(step_model):
        # Render model as an object to make sure nonserializable types are converted.
        step = step_model.to_struct()
        return {
            'id': step['_id'],
            'name': step['name'],
            'are_results_complete': step['are_results_complete'],
            'command': step['command'],
            }

    def _get_workflow_info(w):
        # Render model as an object to make sure nonserializable types are converted.
        workflow = w.to_struct()
        return {
            'id': workflow['_id'],
            'name': workflow['name'],
            'are_results_complete': workflow['are_results_complete'],
            'steps': [
                # ...but we use the model here since it is easier to order steps.
                _get_step_info(s) for s in w.steps.order_by('datetime_created').reverse().all()
                ]
            }

    count = _get_count(request)
    workflows = WorkflowRun.get_sorted(count=count)
    if len(workflows) == 0:
        workflows = []
    workflow_info = [_get_workflow_info(wf) for wf in workflows]

    return JsonResponse({'workflows': workflow_info}, status=200)

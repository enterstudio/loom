from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

#from apps.pipelines.models import Pipeline

def status(request):
    return JsonResponse({}, status=200)

@csrf_exempt
def run(request):
#    pipeline = Pipeline.create_from_json(request.body)
    # TODO run pipeline
    return JsonResponse({}, status=200)

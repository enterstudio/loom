import copy
from django.test import TestCase

from . import fixtures
from api.serializers.run_requests import *
from api.serializers.templates import TemplateSerializer
from api.models.data_trees import DataNode


class TestRunRequestSerializer(TestCase):

    def testCreate(self):
        s = TemplateSerializer(data=fixtures.templates.flat_workflow)
        s.is_valid(raise_exception=True)
        workflow = s.save()
        workflow_id = '%s@%s' % (workflow.name, workflow.id)

        run_request_data = {
            'template': workflow_id,
            'inputs': [
                fixtures.run_requests.run_request_input,
            ]
        }

        s = RunRequestSerializer(
            data=run_request_data)
        s.is_valid(raise_exception=True)
        
        with self.settings(WORKER_TYPE='MOCK'):
            rr = s.save()

        self.assertEqual(
            rr.inputs.first().get_data_as_scalar().substitution_value,
            fixtures.run_requests.run_request_input['data']['contents'])

        data_tree = DataNode.objects.get(id=RunRequestSerializer(rr).data['inputs'][0]['data']['id'])
        self.assertEqual(
            data_tree.data_object.substitution_value,
            fixtures.run_requests.run_request_input['data']['contents'])

        self.assertEqual(
            RunRequestSerializer(rr).data['template']['id'],
            rr.template.id)

        self.assertEqual(rr.run.template.id, rr.template.id)

    def testCreateNested(self):
        s = TemplateSerializer(data=fixtures.templates.nested_workflow)
        s.is_valid(raise_exception=True)
        workflow = s.save()
        workflow_id = '%s@%s' % (workflow.name, workflow.id)

        run_request_data = {'template': workflow_id}

        s = RunRequestSerializer(
            data=run_request_data)
        s.is_valid(raise_exception=True)

        with self.settings(WORKER_TYPE='MOCK'):
            rr = s.save()

        self.assertEqual(rr.run.template.name, workflow.name)
        self.assertEqual(rr.run.steps.first().template.name,
                         workflow.steps.first().name)


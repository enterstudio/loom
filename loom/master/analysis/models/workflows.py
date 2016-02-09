from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .common import AnalysisAppBaseModel
from .files import DataObject
from .input_sets import InputSetManagerFactory
from .step_definitions import StepDefinition, StepDefinitionOutputPort
from .step_runs import StepRun
from .template_helper import StepTemplateHelper, StepTemplateContext
from universalmodels import fields
from universalmodels.models import InstanceModel


"""
This module contains Workflows and other classes related to
receiving a request for analysis from a user.
"""

class Workflow(InstanceModel, AnalysisAppBaseModel):
    """Each workflow may contain many processing steps, with results from one
    step optionally feeding into another step as input.
    """

    _class_name = ('workflow', 'workflows')

    name = fields.CharField(max_length = 256, null=True)
    constants = fields.JSONField(null=True)
    steps = fields.OneToManyField('Step', related_name='workflow')
    data_bindings = fields.OneToManyField('RequestDataBinding')
    data_pipes = fields.OneToManyField('RequestDataPipe')
    are_results_complete = fields.BooleanField(default=False)
    
    @classmethod
    def update_and_run(cls):
        cls.update_all_statuses()
        StepRun.run_all()

    @classmethod
    def update_and_dry_run(cls):
        cls.update_all_statuses()

    @classmethod
    def update_all_statuses(cls):
        for workflow in cls.objects.filter(are_results_complete=False):
            workflow._update_status()

    def _update_status(self):
        for step in self.steps.filter(are_results_complete=False):
            step._update_status()
        if self.steps.filter(are_results_complete=False).count() == 0:
            self.update({'are_results_complete': True})

    def _reset_status(self):
        for step in self.steps.filter(are_results_complete=True):
            step.reset_status()

    @classmethod
    def get_sorted(cls, count=None):
        workflows = cls.objects.order_by('datetime_created').reverse()
        if count is not None and (workflows.count() > count):
            workflows = workflows[:count]
        return [wf for wf in workflows]

    def get_step(self, name):
        return self.steps.get(name=name)

    def get_connector(self, step_name, destination_port_name):
        return self.get_step(step_name).get_connector(destination_port_name)

    def _get_data_binding(self, step_name, port_name):
        bindings = self.data_bindings.filter(destination__step=step_name, destination__port=port_name)
        if bindings.count() > 1:
            raise Exception("Multiple bindings were found on workflow %s for step %s, port %s" % (self, step_name, port_name))
        elif bindings.count() == 1:
            return bindings.first()
        else:
            return None

    def _get_data_pipe(self, step_name, port_name):
        data_pipes = self.data_pipes.filter(destination__step=step_name, destination__port=port_name)
        if data_pipes.count() > 1:
            raise Exception('Multiple data_pipes were found on workflow %s for step %s, port %s.' % (self, step_name, port_name))
        elif data_pipes.count() == 1:
            return data_pipes.first()
        else:
            return None

    def validate_model(self):
        self._validate_port_identifiers()

    def _validate_port_identifiers(self):
        for data_binding in self.data_bindings.all():
            self._validate_destination(data_binding.destination)
        for data_pipe in self.data_pipes.all():
            self._validate_destination(data_pipe.destination)
            self._validate_source(data_pipe.source)

    def _validate_destination(self, destination):
        step = self.get_step(destination.step)
        if step is None:
            raise ValidationError("No step named %s" % destination.step)
        port = step.get_input_port(destination.port)
        if port is None:
            raise ValidationError("No port named %s on step %s" % (destination.port, destination.step))

    def _validate_source(self, source):
        step = self.get_step(source.step)
        if step is None:
            raise ValidationError("No step named %s" % source.step)
        port = step.get_output_port(source.port)
        if port is None:
            raise ValidationError("No port named %s on step %s" % (source.port, source.step))


class Step(InstanceModel, AnalysisAppBaseModel):
    """A step is the template for a task to be run. However it may represent many StepRuns
    in a workflow with parallel steps.
    """

    _class_name = ('step', 'steps')

    name = fields.CharField(max_length = 256)
    command = fields.CharField(max_length = 256)
    constants = fields.JSONField(null=True)
    environment = fields.OneToOneField('RequestEnvironment')
    input_ports = fields.OneToManyField('RequestInputPort')
    output_ports = fields.OneToManyField('RequestOutputPort')
    resources = fields.OneToOneField('RequestResourceSet')
    step_definition = fields.OneToManyField('StepDefinition')
    step_run = fields.OneToManyField('StepRun')
    are_results_complete = fields.BooleanField(default=False)

    def get_input_set_manager(self):
        return InputSetManagerFactory.get_input_set_manager(self)

    def _update_status(self):
        self._update_existing_step_runs()
        waiting_for_files = not self.is_bound_data_ready()
        self._update_new_step_runs()
        if not self.are_step_runs_pending():
            if not waiting_for_files:
                self.update({'are_results_complete': True})

    def are_step_runs_pending(self):
        """Are any step_runs yet to be created or any existing step_runs incomplete"""
        if self.are_results_complete:
            return False
        elif self.step_runs.filter(are_results_complete=False).exists():
            return True
        elif self.get_input_set_manager().are_previous_steps_pending():
            return True
        elif self._are_any_input_sets_unassigned():
            return True
        else:
            return False

    def _update_existing_step_runs(self):
        for step_run in self.step_runs.filter(are_results_complete=False):
            step_run._update_status()

    def _update_new_step_runs(self):
        for input_set in self.get_input_set_manager().get_available_input_sets():
            if input_set.is_data_ready():
                self.create_or_get_step_run(input_set)

    def _are_any_input_sets_unassigned(self):
        for input_set in self.get_input_set_manager()\
                .get_available_input_sets():
            if input_set.is_data_ready():
                if self._is_input_set_unassigned(input_set):
                    return True
        return False

    def _is_input_set_unassigned(self, input_set):
        """True if input_set does not have a StepRun attached to 
        this Step
        """
        step_definition = self.create_step_definition(input_set)
        return not step_definition.does_attached_step_run_exist(
            self, input_set)

    def _reset_status(self):
        for step_run in self.step_runs.filter(are_results_complete=True):
            step_run.reset_status()
        self.update({'are_results_complete': False})

    def get_input_port(self, name):
        try:
            return self.input_ports.get(name=name)
        except ObjectDoesNotExist:
            return None

    def get_output_port(self, name):
        try:
            return self.output_ports.get(name=name)
        except ObjectDoesNotExist:
            return None

    def get_connector(self, destination_port_name):
        connectors = filter(lambda c: c.destination.port==destination_port_name, self.get_connectors())
        if not connectors:
            return None
        if len(connectors) == 1:
            return connectors[0]
        else:
            raise Exception("Found multiple connectors with port name %s" % destination_port_name)

    def get_connectors(self):
        return [c for c in self.get_bindings()] + \
            [c for c in self.get_data_pipes()]

    def get_bindings(self):
        return self.workflow.data_bindings.filter(destination__step=self.name)

    def is_bound_data_ready(self):
        return all([binding.is_data_ready()
                    for binding in self.get_bindings().all()])

    def get_data_pipes(self):
        return self.workflow.data_pipes.filter(destination__step=self)

    def create_or_get_step_run(self, input_set):
        step_definition = self.create_step_definition(input_set)
        step_run = step_definition.attach_step_run_if_one_exists(self, input_set)
        if step_run is None:
            step_run = self.create_step_run(input_set)
        return step_run

    def create_step_run(self, input_set):
        return StepRun.create({
            'step_definition': self._render_step_definition(input_set),
            'steps': [self.to_struct()],
            'output_ports': [port._render_step_run_output_port(input_set) for port in self.output_ports.all()],
            'input_ports': [self.get_input_port(input_port_name)._render_step_run_input_port(source, input_set) 
                            for input_port_name, source in input_set.inputs.iteritems()]
            })

    def create_step_definition(self, input_set):
        return StepDefinition.create(self._render_step_definition(input_set))

    def _render_step_definition(self, input_set):
        assert input_set.is_data_ready(), "Refusing to create StepDefinition until all DataObjects are available for this InputSet"
        return {
                'command': self._render_command(input_set),
                'environment': self.get('environment')._render_step_definition_environment(),
                'output_ports': [port._render_step_definition_output_port(input_set) for port in self.output_ports.all()],
                'input_ports': [self.get_input_port(port_name)._render_step_definition_input_port(source.get_data_object(), input_set)
                                for port_name, source in input_set.inputs.iteritems()],
                }

    def _render_command(self, input_set):
        return StepTemplateHelper(self, input_set).render(self.command)

    def _render_step_definition_data_bindings(self):
        return [c._render_step_definition_data_bindings(self) for c in self.get_connectors()]


class RequestEnvironment(InstanceModel, AnalysisAppBaseModel):

    _class_name = ('request_environment', 'request_environments')


class RequestDockerImage(RequestEnvironment):

    _class_name = ('request_docker_image', 'request_docker_images')

    docker_image = fields.CharField(max_length = 100)

    def _render_step_definition_environment(self):
        # TODO translate a docker image name into an ID
        return {'docker_image': self.docker_image}


class RequestResourceSet(InstanceModel, AnalysisAppBaseModel):

    _class_name = ('request_resource_set', 'request_resource_sets')

    memory = fields.CharField(max_length = 20)
    cores = fields.IntegerField()


class RequestOutputPort(InstanceModel, AnalysisAppBaseModel):

    _class_name = ('request_output_port', 'request_output_ports')

    name = fields.CharField(max_length = 256)
    is_array = fields.BooleanField(default = False)
    file_name = fields.CharField(max_length = 256, null=True)
    glob = fields.CharField(max_length = 256, null=True)

    def is_data_object(self):
        return False

    def get_step_run_ports(self):
        return [step_run.get_output_port(self.name) for step_run in self.step.step_runs.all()]

    def _render_step_definition_output_port(self, input_set):
        return {
            'file_name': StepTemplateHelper(self.step, input_set).render(self.file_name),
            'glob': StepTemplateHelper(self.step, input_set).render(self.glob),
            'is_array': self.is_array
            }

    def _render_step_run_output_port(self, input_set):
        return {
            'name': self.name,
            'step_definition_output_port': self._render_step_definition_output_port(input_set)
            }


class RequestInputPort(InstanceModel, AnalysisAppBaseModel):

    _class_name = ('request_input_port', 'request_input_ports')

    name = fields.CharField(max_length = 256)
    file_name = fields.CharField(max_length = 256)
    is_array = fields.BooleanField(default = False)

    def get_connector(self):
        connector = self._get_data_binding()
        if connector is None:
            connector = self._get_data_pipe()
        return connector

    def is_source_an_array(self):
        return self.get_connector().is_source_an_array()

    def get_source(self):
        return self.get_connector().get_source()

    def get_source_step(self):
        source = self.get_source()
        if source.is_data_object():
            return None
        else:
            return source.step

    def is_from_same_source_step(self, other_port):
        try:
            return other_port.get_source_step()._id \
                == self.get_source_step()._id
        except AttributeError:
            # Happens if step is None, e.g. for a port with DataBinding
            return False

    def has_parallel_inputs(self):
        step = self.get_source_step()
        if step is None:
            return False
        else:
            return step.step_runs.count() > 1

    def _get_data_binding(self):
        if not self.step.workflow:
            return None
        return self.step.workflow._get_data_binding(port_name=self.name, step_name=self.step.name)

    def _get_data_pipe(self):
        if not self.step.workflow:
            return None
        return self.step.workflow._get_data_pipe(
            port_name=self.name, step_name=self.step.name)

    def has_data_binding(self):
        return self._get_data_binding() is not None

    def _render_step_definition_input_port(self, data_object, input_set):
        return {
            'file_names': self._render_file_names(data_object, input_set),
            'is_array': self.is_array,
            'data_object': data_object.to_struct()
            }

    def _render_file_names(self, data_object, input_set):
        return [
            {'name': StepTemplateHelper(self.step, input_set).render(name)}
            for name in StepTemplateContext.get_file_name_list(data_object, self.file_name)
            ]

    def _render_step_run_input_port(self, source, input_set):
        return {
            'name': self.name,
            'step_definition_input_port': self._render_step_definition_input_port(source.get_data_object(), input_set)
            }


class RequestDataBinding(InstanceModel, AnalysisAppBaseModel):
    """Connects an already existing DataObject to the input port of a step"""

    _class_name = ('request_data_binding', 'request_data_bindings')

    data_object = fields.ForeignKey('DataObject')
    destination = fields.ForeignKey('RequestDataBindingDestinationPortIdentifier')

    def is_data_pipe(self):
        return False

    def is_data_ready(self):
        return self.get_data_object().is_available()

    def get_data_object(self):
        return self.get('data_object', downcast=True)

    def get_source(self):
        return self.get_data_object()

    def is_source_an_array(self):
        return self.get_source().is_array()

    def is_destination_an_array(self):
        return self.get_destination_step().get_input_port(self.destination.port).is_array

    def get_destination_step(self):
        if not self.workflow:
            raise Exception("No workflow defined for RequestDataBinding %s" % self.to_struct())
        return self.workflow.get_step(self.destination.step)

    def get_destination_port(self):
        return self.get_destination_step().get_input_port(self.destination.port)

    def has_multiple_runs(self):
        return False

    def _render_step_definition_data_bindings(self, step):
        return {
            'data_object': self.data_object.to_struct(),
            'input_port': self.get_destination_port()._render_step_definition_input_port()
            }


class RequestDataPipe(InstanceModel, AnalysisAppBaseModel):
    """Connects an output port of a previous step to an input port
    of the current step.
    """

    _class_name = ('request_data_pipe', 'request_data_pipes')

    source = fields.ForeignKey('RequestDataPipeSourcePortIdentifier')
    destination = fields.ForeignKey('RequestDataPipeDestinationPortIdentifier')

    def is_data_pipe(self):
        return True

    def get_source_step(self):
        return self.workflow.get_step(self.source.step)

    def get_destination_step(self):
        return self.workflow.get_step(self.destination.step)

    def get_source(self):
        return self.get_source_step().get_output_port(self.source.port)

    def is_source_an_array(self):
        return self.get_source().is_array

    def is_destination_an_array(self):
        return self.get_destination_step().get_input_port(self.destination.port).is_array

    def _render_step_definition_data_bindings(self, step):
        port = step.get_input_port(self.destination.port)
        return {
            'data_object': self.get_data_object().to_struct(),
            'input_port': port._render_step_definition_input_port()
            }


class RequestPortIdentifier(InstanceModel, AnalysisAppBaseModel):

    step = fields.CharField(max_length = 256)
    port = fields.CharField(max_length = 256)

    class Meta:
        abstract = True


class RequestDataBindingDestinationPortIdentifier(RequestPortIdentifier):

    _class_name = ('request_data_binding_port_identifier', 'request_data_binding_port_identifiers')


class RequestDataPipeSourcePortIdentifier(RequestPortIdentifier):

    _class_name = ('request_data_pipe_source_port_identifier', 'request_data_pipe_source_port_identifiers')


class RequestDataPipeDestinationPortIdentifier(RequestPortIdentifier):

    _class_name = ('request_data_pipe_destination_port_identifier', 'request_data_pipe_destination_port_identifiers')

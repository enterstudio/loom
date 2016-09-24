from copy import deepcopy
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.dispatch import receiver
import os
import uuid

from .base import BaseModel, BasePolymorphicModel, render_from_template
from api.models.task_definitions import *
from api.models.data_objects import DataObject, FileDataObject
from api.models.workflows import Step, RequestedResourceSet
from api import get_setting
from api.task_manager.factory import TaskManagerFactory


class TaskRun(BaseModel):

    """One instance of executing a TaskDefinition, i.e. executing a Step on a 
    particular set of inputs.
    """
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    step_run = models.ForeignKey('StepRun',
                                 related_name='task_runs',
                                 on_delete=models.CASCADE)
    status = models.CharField(
        max_length=255,
        default='not_started',
        choices=(('not_started', 'Not started'),
                 ('provisioning_host', 'Provisioning host'),
                 ('gathering_input_files', 'Gathering input files'),
                 ('preparing_runtime_environment', 'Preparing runtime environment'),
                 ('running', 'Running'),
                 ('saving_output_files', 'Saving output files'),
                 ('finished', 'Finished'),
        )
    )
    status_message = models.TextField(null=True, blank=True)
        
    # No 'environment' field, because this is in the TaskDefinition.
    # 'resources' field included (by FK) since this is not in TaskDefinition.

    @property
    def name(self):
        return self.step_run.name
                    
    @classmethod
    def create_from_input_set(cls, input_set, step_run):
        task_run = TaskRun.objects.create(step_run=step_run)
        for input in input_set:
            step_run_input = step_run.get_input(input.channel)
            TaskRunInput.objects.create(
                step_run_input=step_run_input,
                task_run=task_run,
                data_object = input.data_object)
        for step_run_output in step_run.outputs.all():
            TaskRunOutput.objects.create(
                step_run_output=step_run_output,
                task_run=task_run)
        TaskDefinition.create_from_task_run(task_run)
        return task_run
        
    def run(self):
        task_manager = TaskManagerFactory.get_task_manager()
        task_manager.run(self)

    def get_input_context(self):
        context = {}
        for input in self.inputs.all():
            context[input.channel] = input.data_object\
                                            .get_substitution_value()
        return context
        
    def get_output_context(self):
        context = {}
        for output in self.outputs.all():
            # This returns a value only for Files, where the filename
            # is known beforehand and may be used in the command.
            # For other types, nothing is added to the context.
            if output.type == 'file':
                context[output.channel] = output.filename
        return context

    def get_full_context(self):
        context = self.get_input_context()
        context.update(self.get_output_context())
        return context

    def render_command(self):
        return render_from_template(
            self.step_run.template.command,
            self.get_full_context())

    def update_status(self):
        if self.task_run_attempts.count() > 0:
            if self.status != self.task_run_attempts.first().status \
               or self.status_message != self.task_run_attempts.first().status_message:
                self.status = self.task_run_attempts.first().status
                self.status_message = self.task_run_attempts.first().status_message
                self.save()
        self.step_run.update_status()


class TaskRunInput(BaseModel):

    task_run = models.ForeignKey('TaskRun',
                                 related_name='inputs',
                                 on_delete=models.CASCADE)
    data_object = models.ForeignKey('DataObject', on_delete=models.PROTECT)
    step_run_input = models.ForeignKey('AbstractStepRunInput',
                                       related_name='task_run_inputs',
                                       null=True,
                                       on_delete=models.PROTECT)

    @property
    def channel(self):
        return self.step_run_input.channel
    
    @property
    def type(self):
        return self.step_run_input.type


class TaskRunOutput(BaseModel):

    step_run_output = models.ForeignKey('StepRunOutput',
                                        related_name='task_run_outputs',
                                        on_delete=models.CASCADE,
                                        null=True)
    task_run = models.ForeignKey('TaskRun',
                                 related_name='outputs',
                                 on_delete=models.CASCADE)
    data_object = models.ForeignKey('DataObject',
                                    null=True,
                                    on_delete=models.PROTECT)

    @property
    def filename(self):
        # This will raise ObjectDoesNotExist if task_definition_output
        # is not yet attached.
        return self.task_definition_output.filename

    @property
    def channel(self):
        return self.step_run_output.step_output.channel

    @property
    def type(self):
        return self.step_run_output.step_output.type

    def push(self, data_object):
        if self.data_object is None:
            self.data_object=data_object
            self.save()
        self.step_run_output.push(data_object)


class TaskRunResourceSet(BaseModel):
    task_run = models.OneToOneField('TaskRun',
                                on_delete=models.CASCADE,
                                related_name='resources')
    memory = models.CharField(max_length=255, null=True)
    disk_size = models.CharField(max_length=255, null=True)
    cores = models.CharField(max_length=255, null=True)


class TaskRunAttempt(BasePolymorphicModel):

    skip_post_save = False
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_run = models.ForeignKey('TaskRun',
                                 related_name='task_run_attempts',
                                 on_delete=models.CASCADE)
    task_run_as_accepted_attempt = models.OneToOneField(
        'TaskRun',
        related_name='accepted_task_run_attempt',
        on_delete=models.CASCADE,
        null=True)
    container_id = models.CharField(max_length=255, null=True)
    last_update = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=255,
        default='not_started',
    )
    status_message = models.TextField(null=True, blank=True)
    host_status = models.CharField(
        max_length=255,
        default='not_started',
        choices=(('not_started', 'Not started'),
                 ('provisioning_host', 'Provisioning host'),
                 ('active', 'Active'),
                 ('deleted', 'Deleted'),
        )
    )
    process_status = models.CharField(
        max_length=255,
        default='not_started',
        choices=(('not_started', 'Not started'),
                 ('running', 'Running'),
                 ('failed_without_completing', 'Failed without completing'),
                 ('finished_successfully', 'Finished successfully'),
                 ('finished_with_error', 'Finished with error'),
        )
    )
    process_status_message = models.TextField(null=True, blank=True)
    monitor_status = models.CharField(
        max_length=255,
        default='not_started',
        choices=(('not_started', 'Not started'),
                 ('initializing', 'Initializing'),
                 ('failed_to_initialize', 'Failed to initialize'),
                 ('copying_input_files', 'Gathering input files'),
                 ('failed_to_copy_input_files', 'Failed to copy input files'),
                 ('getting_runtime_environment_image', 'Getting runtime environment image'),
                 ('failed_to_get_runtime_environment_image', 'Failed to get runtime environment image'),
                 ('creating_runtime_environment', 'Creating runtime environment'),
                 ('failed_to_create_runtime_environment', 'Failed to create runtime environment'),
                 ('starting_run', 'Starting run'),
                 ('failed_to_start_run', 'Failed to start run'),
                 ('waiting_for_run', 'Waiting for run'),
                 ('waiting_for_cleanup', 'Waiting for cleanup'),
                 ('finished', 'Finished'),
        )
    )
    monitor_status_message = models.TextField(null=True, blank=True)
    save_outputs_status = models.CharField(
        max_length=255,
        default='not_started',
        choices=(('not_started', 'Not started'),
                 ('saving_outputs', 'Saving outputs'),
                 ('failed_to_save_outputs', 'Failed to save outputs'),
                 ('finished_successfully', 'Finished successfully'),
        )
    )
    save_outputs_status_message = models.TextField(null=True, blank=True)

    @property
    def task_definition(self):
        return self.task_run.task_definition

    @property
    def name(self):
        return self.task_run.name

    @classmethod
    def create_from_task_run(cls, task_run):
        return cls.objects.create(task_run=task_run)

    def _post_save(self):
        if self.skip_post_save:
            return
        self._idempotent_initialize()
        self.update_status()
        if self.status == 'finished_successfully':
            self.push_outputs()
        self.task_run.update_status()

    def _idempotent_initialize(self):
        if self.inputs.count() == 0:
            self._initialize_inputs()

        if self.outputs.count() == 0:
            self._initialize_outputs()

    def _initialize_inputs(self):
        for input in self.task_run.inputs.all():
            TaskRunAttemptInput.objects.create(
                task_run_attempt=self,
                task_run_input=input,
                data_object=input.data_object)

    def _initialize_outputs(self):
        for output in self.task_run.outputs.all():
            TaskRunAttemptOutput.objects.create(
                task_run_attempt=self,
                task_run_output=output)

    def get_working_dir(self):
        return os.path.join(get_setting('FILE_ROOT_FOR_WORKER'),
                            'runtime_volumes',
                            self.id.hex,
                            'work')

    def get_log_dir(self):
        return os.path.join(get_setting('FILE_ROOT_FOR_WORKER'),
                            'runtime_volumes',
                            self.id.hex,
                            'logs')

    def get_worker_log_file(self):
        return os.path.join(self.get_log_dir(), 'worker.log')

    def get_stdout_log_file(self):
        return os.path.join(self.get_log_dir(), 'stdout.log')

    def get_stderr_log_file(self):
        return os.path.join(self.get_log_dir(), 'stderr.log')

    def update_status(self):
        if self.monitor_status == 'waiting_for_run':
            status, status_message = self._get_status_from_process()
        elif self.monitor_status == 'waiting_for_cleanup':
            status, status_message = self._get_status_from_cleanup()
        elif self.monitor_status == 'finished':
            self._get_terminal_status()
        else:
            status, status_message = self._get_status_from_monitor()

        self.status = status
        self.status_message = status_message
        self.skip_post_save = True # To prevent infinite recursion
        self.save()

    def _get_status_from_monitor(self):
        if not self.monitor_status_message:
            self.monitor_status_message = self.get_monitor_status_display()
        return self.monitor_status, self.monitor_status_message
        
    def _get_status_from_process(self):
        if not self.process_status_message:
            self.process_status_message = self.get_process_status_display()
        return self.process_status, self.process_status_message

    def _get_status_from_cleanup(self):
        if not self.save_outputs_status_message:
            self.save_outputs_status_message = self.get_save_outputs_status_display()
        return self.save_outputs_status, self.save_outputs_status_message

    def _get_terminal_status(self):
        if self.process_status != 'finished_successfully':
            return self._get_status_from_process()
        elif self.save_outputs_status != 'finished_successfully':
            return self._get_status_from_cleanup()
        else:
            # Successful process and cleanup. Take success status from process
            return self._get_status_from_process()

    def get_provenance_data(self, files=None, tasks=None, edges=None):
        if files is None:
            files = set()
        if tasks is None:
            tasks = set()
        if edges is None:
            edges = set()

        tasks.add(self)

        for input in self.task_run.inputs.all():
            data = input.data_object
            if data.type == 'file':
                files.add(data)
                edges.add((data.id.hex, self.id.hex))
                data.get_provenance_data(files, tasks, edges)
            else:
                # TODO
                pass

        return files, tasks, edges

    def push_outputs(self):
        for output in self.outputs.all():
            output.push()

@receiver(models.signals.post_save, sender=TaskRunAttempt)
def _post_save_task_run_attempt_signal_receiver(sender, instance, **kwargs):
    instance._post_save()


class TaskRunAttemptInput(BaseModel):

    task_run_attempt = models.ForeignKey(
        'TaskRunAttempt',
        related_name='inputs',
        on_delete=models.CASCADE)
    data_object = models.ForeignKey(
        'DataObject',
        null=True,
        related_name='task_run_attempt_inputs',
        on_delete=models.PROTECT)
    task_run_input = models.ForeignKey(
        'TaskRunInput',
        related_name='task_run_attempt_inputs',
        null=True, on_delete=models.PROTECT)
    
    
    @property
    def type(self):
        return self.task_run_input.type

    @property
    def channel(self):
        return self.task_run_input.channel


class TaskRunAttemptOutput(BaseModel):

    task_run_attempt = models.ForeignKey(
        'TaskRunAttempt',
        related_name='outputs',
        on_delete=models.CASCADE)
    data_object = models.OneToOneField(
        'DataObject',
        null=True,
        related_name='task_run_attempt_output',
        on_delete=models.PROTECT)
    task_run_output = models.ForeignKey(
        'TaskRunOutput',
        related_name='task_run_attempt_outputs',
        on_delete=models.PROTECT)

    @property
    def type(self):
        return self.task_run_output.type

    @property
    def channel(self):
        return self.task_run_output.channel

    @property
    def filename(self):
        return self.task_run_output.filename

    def push(self):
        if self.data_object is not None:
            self.task_run_output.push(self.data_object)


class TaskRunAttemptLogFile(BaseModel):

    task_run_attempt = models.ForeignKey(
        'TaskRunAttempt',
        related_name='log_files',
        on_delete=models.CASCADE)
    log_name = models.CharField(max_length=255)
    file_data_object = models.OneToOneField(
        'FileDataObject',
        null=True,
        related_name='task_run_attempt_log_file',
        on_delete=models.PROTECT)

    def _post_save(self):
        if self.file_data_object is None:
            self.file_data_object = FileDataObject.objects.create(source_type='log')
            self.save()

@receiver(models.signals.post_save, sender=TaskRunAttemptLogFile)
def _post_save_task_run_attempt_log_file_signal_receiver(sender, instance, **kwargs):
    instance._post_save()

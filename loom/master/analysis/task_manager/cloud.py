import errno 
import json
import logging
import multiprocessing
import os
import requests
import subprocess

import oauth2client.contrib.gce

from django.conf import settings
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver

logger = logging.getLogger('LoomDaemon')


class CloudTaskManager:

    @classmethod
    def run(cls, task_run):
        # Don't want to block while waiting for VM to come up, so start another process to finish the rest of the steps.
        process = multiprocessing.Process(target=CloudTaskManager._run, args=(task_run))
        process.start()

    @classmethod
    def _run(cls, task_run):
        """Create a VM, deploy Docker and Loom, and pass command to task runner."""
        resources = CloudTaskManager._get_resource_requirements(task_run)
        instance_type = CloudTaskManager._get_cheapest_instance_type(cores=resources.cores, memory=resources.memory)
        task_id = task_run.id # TODO: point to actual TaskRun id after merging
        node_started = CloudTaskManager._start_node(instance_type, task_id)

        if not node_started:
            raise CloudTaskManagerError('Node failed to start')

        # TODO: format and mount scratch disk, install pip, deploy Loom, and run a command
        CloudTaskManager._setup_credentials()
        CloudTaskManager._setup_scratch_disk(node_name=task_id, device_name=settings.WORKER_DISK_DEVICE_NAME, mount_point=settings.WORKER_DISK_MOUNT_POINT)

    @classmethod
    def _setup_scratch_disk(node_name, device_name, mount_point):
        import stat
        os.chmod('ansible_gce_inventory.py', stat.S_IXOTH)
        subprocess.call('ansible', '-i', 'ansible_gce_inventory.py', node_name, '-m', 'filesystem', '-a', 'fstype=ext4 dev=/dev/disk/by-id/google-'+device_name+' opts="-F"')
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)
        subprocess.call('ansible', '-i', 'ansible_gce_inventory.py', node_name, '-m', 'mount', '-a', 'name='+mount_point+' fstype=ext4 src=/dev/disk/by-id/google-'+device_name+' state=mounted')

    @classmethod
    def _setup_credentials(cls):
        if settings.MASTER_TYPE != 'GOOGLE_CLOUD':
            raise CloudTaskManagerError('Unsupported cloud type: ' + settings.MASTER_TYPE)
        else:
            gce_credentials = oauth2client.contrib.gce.AppAssertionCredentials([])
            credentials = { 'service_account_email': gce_credentials.service_account_email,
                            'pem_file': settings.ANSIBLE_PEM_FILE,
                            'project_id': settings.PROJECT_ID }
            # Write a secrets.py somewhere on the Python path for Ansible to import.
            # Assumes loom is on the Python path.
            import loom
            loomparentdir = os.path.dirname(os.path.dirname(loom.__file__))
            with open(os.path.join(loomparentdir, 'secrets.py'), 'w') as outfile:
                outfile.write("GCE_PARAMS=('"+credentials['service_account_email']+"', '"+credentials['pem_file']+"')\n")
                outfile.write("GCE_KEYWORD_PARAMS={'project': '"+credentials['project_id']+"'}")
            try:
                import secrets
            except ImportError:
                raise CloudTaskManagerError("Couldn't write secrets.py to the Python path")

    @classmethod
    def _start_node(cls, instance_type, task_id):
        driver = CloudTaskManager._get_cloud_driver()
        if settings.MASTER_TYPE != 'GOOGLE_CLOUD':
            raise CloudTaskManagerError('Unsupported cloud type: ' + settings.MASTER_TYPE)
        else:
            volume = driver.create_volume(size=settings.WORKER_DISK_SIZE, name=task_id+'-disk', location=settings.WORKER_LOCATION, ex_disk_type=settings.WORKER_DISK_TYPE)
            # This will come in handy when instances need more cloud permissions:
            #service_account_scopes = [{'email':'default', 'scopes': ['devstorage.read_write', 'compute', 'logging.write', 'monitoring.write', 'cloud-platform', 'cloud.useraccounts.readonly'] }]
            #node = driver.create_node(name=task_id, size=instance_type, image=settings.WORKER_VM_IMAGE, location=settings.WORKER_LOCATION, external_ip='ephemeral', ex_boot_disk=volume, ex_service_accounts=service_account_scopes)

            node = driver.create_node(name=task_id, size=instance_type, image=settings.WORKER_VM_IMAGE, location=settings.WORKER_LOCATION)
            driver.attach_volume(node, volume, device=settings.WORKER_DISK_DEVICE_NAME, ex_auto_delete=True)
            node_started = driver.ex_start_node(node)
            return node_started
    
    @classmethod
    def _get_resource_requirements_django(cls, task_run):
        # TODO: use this again when we have a TaskRun Django model
        # Retrieve resource requirements
        # If step_run has more than one step, requirements
        # should be identical in all steps.
        resources = None
        last_resources = None
        for task in task_run.tasks.all():
            resources = task.resources
            resources_json = resources.to_json()
            if last_resources is None:
                pass
            else:
                assert resources_json == last_resources, \
                    "Steps with different resource requirements were attached"\
                    " to the same StepRun. This indicates a bug in the code and"\
                    " should be avoided when attaching a Step to an existing"\
                    " StepRun."
            last_resources = resources_json
        return resources

    @classmethod
    def _get_resource_requirements(cls, task_run):
        """ Just return the resources for the first task for now."""
        return task_run.tasks[0]

    @classmethod
    def _get_cheapest_instance_type(cls, cores, memory):
        """ Determine the cheapest instance type given a minimum number of cores and minimum amount of RAM (in GB). """

        if settings.MASTER_TYPE != 'GOOGLE_CLOUD': #TODO: support other cloud providers
            raise CloudTaskManagerError('Not a recognized cloud provider: ' + settings.MASTER_TYPE)
        else:
            pricelist = CloudTaskManager._get_gcloud_pricelist()

            # Filter out preemptible, shared-CPU, and non-US instance types
            us_instance_types = {k:v for k,v in pricelist.items()\
                if k.startswith('CP-COMPUTEENGINE-VMIMAGE-') and not k.endswith('-PREEMPTIBLE') and 'us' in v and v['cores'] != 'shared'}

            # Convert to array and add keys (instance type names) as type names
            price_array = []
            for key in us_instance_types:
                value = us_instance_types[key] 
                value.update({'name':key.replace('CP-COMPUTEENGINE-VMIMAGE-', '').lower()})
                price_array.append(value)

            # Sort by price in US
            price_array.sort(None, lambda x: x['us'])

            # Look for an instance type that satisfies requested cores and memory; first will be cheapest
            for instance_type in price_array:
                if int(instance_type['cores']) >= int(cores) and float(instance_type['memory']) >= float(memory):
                    return instance_type['name']

            # No instance type found that can fulfill requested cores and memory
            raise CloudTaskManagerError('No instance type found with at least %d cores and %f GB of RAM.' % (cores, memory))
        
    @classmethod
    def _get_gcloud_pricelist(cls):
        """ Retrieve latest pricelist from Google Cloud, or use cached copy if not reachable. """
        try:
            r = requests.get('http://cloudpricingcalculator.appspot.com/static/data/pricelist.json')
            content = json.loads(r.content)
        except ConnectionError:
            logger.warning("Couldn't get updated pricelist from http://cloudpricingcalculator.appspot.com/static/data/pricelist.json. Falling back to cached copy, but prices may be out of date.")
            with open('pricelist.json') as infile:
                content = json.load(infile)

        logger.debug('Using pricelist ' + content['version'] + ', updated ' + content['updated'])
        pricelist = content['gcp_price_list']
        return pricelist

    @classmethod
    def _get_cloud_driver(cls):
        if settings.MASTER_TYPE != 'GOOGLE_CLOUD': #TODO: support other cloud providers
            raise CloudTaskManagerError('Not a recognized cloud provider: ' + settings.MASTER_TYPE)
        else:
            provider = Provider.GCE 
            args = ['','']  # master is running in GCE; get credentials from metadata service
                            # (more info: http://libcloud.readthedocs.org/en/latest/compute/drivers/gce.html#using-gce-internal-authorization)
            kwargs = {'project': settings.PROJECT_ID}
        driver_factory = get_driver(provider)
        driver = driver_factory(*args, **kwargs)
        return driver







    @classmethod
    def old_deploy(cls):
    	CloudTaskManager._create_file_root_on_worker()

        # Construct command to run on worker node
        cmd = '%s %s --run_id %s --master_url %s' % (
            PYTHON_EXECUTABLE,
            STEP_RUNNER_EXECUTABLE,
            step_run.id,
            settings.MASTER_URL_FOR_WORKER,
            )
        if step_run.steps.count() == 0:
            raise Exception("No Step found for StepRun %s" % step_run.id)

        # Use Slurm to call the step runner on a worker node
        cmd = "sbatch -D %s -n %s --mem=%s --wrap='%s'" % (
	    settings.FILE_ROOT_FOR_WORKER,
            resources.cores,
            resources.memory,
            cmd
            )
        logger.debug(cmd)
        proc = subprocess.Popen(cmd, shell=True)
        step_run.update({'is_running': True})
        #TODO save proc.pid for follow-up
        # For now, return process so caller can follow up
        # However, this is just the job submit process (sbatch), not the step runner!
	return proc

    @classmethod
    def _create_file_root_on_worker(cls):
        try:
            os.makedirs(settings.FILE_ROOT_FOR_WORKER)
        except OSError as e:
            if e.errno == errno.EEXIST and os.path.isdir(settings.FILE_ROOT_FOR_WORKER):
                pass
            else:
                raise

    @classmethod
    def _run_command_on_worker(cls, cmd):
        # Location of Python in virtualenv on worker node
        PYTHON_EXECUTABLE = os.path.abspath(
            os.path.join(
                settings.BASE_DIR,
                '../../../bin/python',
                ))

        # Location of step runner on worker node
        STEP_RUNNER_EXECUTABLE = os.path.abspath(
            os.path.join(
                settings.BASE_DIR,
                '../../worker/step_runner.py',
                ))


class CloudTaskManagerError(Exception):
    pass

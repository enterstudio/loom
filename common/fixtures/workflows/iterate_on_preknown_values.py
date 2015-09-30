#!/usr/bin/env python
import uuid
import json

def _make_request():
    CHROMOSOME_LIST = ['chr1', 'chr2', 'chr3']
    env = {
        'docker_image': 'ubuntu',
        }
    
    resources = {
        'memory': '1GB',
        'cores': '1',
        }
    
    split_step = {
        'name': 'split_step',
        'command': 'for chr in {{ input_ports.chromosome_list }}; do samtools view {{ input.bam }} $chr > $chr.bam; done',
        'environment': env,
        'resources': resources,
        'input_ports': [
            {
                'name': 'chromosome_list',
                'type': 'string_array',
                },
            {
                'data_type': 'file',
                'name': 'bam',
                'file_name': 'input.bam',
                }
            ],
        'output_ports': [
            {
                'data_type': 'file_array',
                'name': 'bam_array',
                'glob': 'chr*.bam',
                }
            ]
        }

    process_step = {
        'name': 'process_step',
        'command': 'process_chromosome {{ input_ports.bam }} > {{ output_ports.bam }}',
        'environment': env,
        'resources': resources,
        'input_ports': [
            {
                'name': 'bam',
                'type': 'file',
                'filename': '{{ input_ports.chr }}.bam',
                },
            {
                'name': 'chr',
                'type': 'string',
                }
            ],
        'output_ports': [
            {
                'name': 'bam',
                'type': 'file',
                'filename': '{{ input_ports.chr }}_out.bam'
                }
            ]
        }
    
    merge_step = {
        'name': 'merge_step',
        'command': 'samtools merge {{ output_ports.merged_bam }}{% for bam in input_ports.bam_array %} {{ bam }}{% endfor %}',
        'environment': env,
        'resources': resources,
        'input_ports': [
            {
                'name': 'bam_array',
                'data_type': 'file_array',
                'file_name': '{{ input_ports.chromosome_list[i] }}.bam'
                },
            {
                'input_ports': 'chromosome_list',
                'data_type': 'string_array'
                }
            ],
        'output_ports': [
            {
                'name': 'merged_bam',
                'file_name': 'out.bam',
                'data_type': 'file'
                }
            ]
        }
    
    split_merge_workflow = {
        'name': 'split_merge',
        'steps': [
            split_step,
            process_step,
            merge_step,
            ],
        "data_bindings": [
            {
                "destination": {
                    "step": "split_step",
                    "port": "bam"
                    }, 
                "data": {
                    "type": "file",
                    "hash_value": "???",
                    "hash_function": "md5"
                    }
                },
            {
                "destination": {
                    "step": "split_step",
                    "port": "chromosome_list"
                    },
                "data": {
                    "type": "string_array",
                    "strings": CHROMOSOME_LIST
                    }
                },
            {
                "destination": {
                    "step": "process_step",
                    "port": "chr"
                    },
                "data": {
                    "type": "string_array",
                    "strings": CHROMOSOME_LIST
                    }
                }
            ], 
        'data_pipes': [
            {
                'source': {
                    'step': 'split_step',
                    'port': 'bam_array',
                    },
                'destination': {
                    'step': 'process_step',
                    'port': 'bam',
                    }
                },
            {
                'source': {
                    'step': 'process_step',
                    'port': 'bam',
                    },
                'destinations': 
                {
                    'step': 'merge_step',
                    'port': 'bam_array',
                    }
                }
            ]
        }
    
    request_run = {
        'workflows': [split_merge_workflow],
        'requester': 'someone@example.net',
        }

    return request_run

iterate_on_preknown_values = _make_request()

if __name__=='__main__':
    print json.dumps(iterate_on_preknown_values, indent=2)

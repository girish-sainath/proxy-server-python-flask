import os
import json

class CloudFoundryEnv:
    def __init___(self):
        vcap_application_env = os.getenv('VCAP_APPLICATION', None)
        if vcap_application_env:
            vcap_application_str = str(vcap_application_env)
            if vcap_application_str:
                self.vcap_application = json.loads(vcap_application_str)
        self.application_id = None
        if self.vcap_application:
            self.application_id = self.vcap_application.get('application_id', None)

    def get_service_instances(self, service_name=None, service_plan=None, service_instance_name=None):
        service_instances = []
        service_instance_list = []
        vcap_service_env = os.getenv('VCAP_SERVICES', None)
        if vcap_service_env:
            vcap_service_str = str(vcap_service_env)
            if vcap_service_str:
                self.vcap_service = json.loads(vcap_service_str)
        if self.vcap_service:
            if (not service_name) and (not service_instance_name):
                for instance_name, instances in self.vcap_service.items():
                    if instances and (len(instances) > 0):
                        for instance in instances:
                            service_instances.append(instance)
                return service_instances
            if service_name:
                if service_name in self.vcap_service.keys():
                    service_instance_all_plan_list = self.vcap_service.get(service_name)
                    if service_plan and len(service_instance_all_plan_list) > 0:
                        for service_instance in service_instance_all_plan_list:
                            if service_instance.get('plan', None) == service_plan:
                                service_instance_list.append(service_instance)
                    else:
                        service_instance_list = service_instance_all_plan_list
            else:
                for service_name, service_instance in self.vcap_service.items():
                    service_instance_list.append(service_instance)

            if service_instance_name:
                for service_instance in service_instance_list:
                    if service_instance.get('name', None) == service_instance_name:
                        service_instances.append(service_instance)
            else:
                service_instances = service_instance_list
        return service_instances

    def get_env_var_value(self, var):
        return str(os.getenv(var, None))
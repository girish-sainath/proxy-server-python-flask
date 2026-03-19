import time
import jwt
import datetime
from cfenv import CloudFoundryEnv

class UserInfo:
    def __init__(self, token):
        token_split = token.split('Bearer ')
        if len(token_split) == 2:
	        token = token_split[1] 
        self.token = token
        self.__parse_token()

    def __parse_token(self):
        self.jwt_token = jwt.decode(self.token, verify=False)
        #print(self.jwt_token)
        self.scopes = self.jwt_token.get('scope', None)
        self.provider_credentials = self.__get_provider_credentials()

    def __get_provider_credentials(self):
        provider_credentials = None
        cf_env = CloudFoundryEnv()
        xsuaa_instances = cf_env.get_service_instances('xsuaa')
        if xsuaa_instances is not None and len(xsuaa_instances) > 0:
            xsuaa_instance = xsuaa_instances[0]
            if xsuaa_instance is not None:
                provider_credentials = xsuaa_instance.get('credentials', None)
        return provider_credentials

    def get_grant_type(self):
        return self.jwt_token.get('grant_type', 'client_credentials')

    def get_expiration_time(self):
        return self.jwt_token.get('exp', time.time())

    def get_expiration_datetime(self):
        return datetime.datetime.fromtimestamp(get_expiration_time()).strftime('%Y-%m-%dT%H:%M:%S')

    def get_client_id(self):
        return self.jwt_token.get('cid', self.jwt_token.get('client_id', None))

    def get_clone_service_instance_id(self):
        service_instance_id = None
        ext_attr = self.jwt_token.get('ext_attr', None)
        if ext_attr:
            service_instance_id = ext_attr.get('serviceinstanceid', None)
        return service_instance_id

    def check_scope(self, scope):
        has_scope = False
        if self.scopes and (scope in self.scopes):
            has_scope = True
        return has_scope

    def check_local_scope(self, scope):
        if self.provider_credentials is not None:
            xsappname = self.provider_credentials.get('xsappname', None)
            if xsappname is not None:
                scope = xsappname + '.' + scope
        return self.check_scope(scope)

    def get_attribute(self, attr):
        return self.token.get(str(attr), None)

    def get_additional_auth_attribute(self, attr):
        return None

    def get_app_token(self):
        return self.jwt_token

    def get_hdb_token(self):
        return self.jwt_token

    def get_identity_zone(self):
        return self.jwt_token.get('zid', None)

    def get_subdomain(self):
        subdomain = None
        uaa_url = self.jwt_token.get('iss', None)
        if uaa_url:
            subdomain = uaa_url.split('://')[1].split('.')[0]
        return subdomain

    def get_email(self):
        return self.token.get('email', None)

    def get_given_name(self):
        return self.token.get('given_name', None)

    def get_family_name(self):
        return self.token.get('family_name', None)

    def get_logon_name(self):
        return self.token.get('user_name', None)
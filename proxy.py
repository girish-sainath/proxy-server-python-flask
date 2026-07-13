from flask import Flask
from flask import request
from flask import jsonify
from flask import Response
import os
import json
import copy
import http.client
from urllib.parse import quote, unquote, urlsplit
import base64
import time
from functools import wraps
from cfenv import CloudFoundryEnv
from userinfo import UserInfo

app = Flask(__name__)

config = None
tokens = {}
cf_env = CloudFoundryEnv()

# Get port from environment variable or choose 9099 as local default
port = int(os.getenv("PORT", 9099))

@app.route('/')
def welcome():
    return 'Welcome to the Proxy Server written in Python using Flask Framework!'

def auth_required(local_scopes=None, scopes=None):
    def decorator(f):
        @wraps(f)
        def check_for_auth(*args, **kwargs):
            headers = request.headers
            authorization = None
            user_info = None
            if cf_env.get_env_var_value("env") == 'cloud':
                if 'Authorization' in headers.keys():
                    authorization = headers.get('Authorization', None)
                else:
                    exp =  "<UnauthorizedException><error>unauthorized</error><error_description>Full authentication is required to access this resource</error_description></UnauthorizedException>"
                    return Response(exp, mimetype='application/xml', status=http.client.UNAUTHORIZED)
                if authorization is not None:
                    user_info = UserInfo(authorization)
                else:
                    exp = "Failed to get the security details"
                    return Response(exp, mimetype='text/plain', status=http.client.INTERNAL_SERVER_ERROR)
                if user_info is not None:
                    if scopes is not None and len(scopes) > 0:
                        for scope in scopes:
                            if not (user_info.check_scope(scope)):
                                exp = "Unauthorized"
                                return Response(exp, mimetype='text/plain', status=http.client.FORBIDDEN)
                                break
                    if local_scopes is not None and len(local_scopes) > 0:
                        for scope in local_scopes:
                            if not (user_info.check_local_scope(scope)):
                                exp = "Unauthorized"
                                return Response(exp, mimetype='text/plain', status=http.client.FORBIDDEN)
                                break
            return f(*args, **kwargs)
        return check_for_auth
    return decorator

@app.route('/admin/env/services')
@auth_required(['Administrator'])
def vcap_services():
    service_instances = cf_env.get_service_instances()
    return json.dumps(service_instances)

@app.route('/onboarding/saas-registry/saas/dependencies')
@auth_required(['Callback'])
def get_dependencies():
    dependencies = []
    black_listed = ["saas-registry", "xsuaa", "hana", "managed-hana", "user-provided"]
    service_instances = cf_env.get_service_instances()
    if service_instances is not None and len(service_instances) > 0:
        for service_instance in service_instances:
            label = service_instance.get('label', None)
            if label is not None:
                black_list_index = -1
                try:
                    black_list_index = black_listed.index(label)
                except ValueError:
                    black_list_index = -1
                if black_list_index > -1:
                    credentials = service_instance.get('credentials', None)
                    if credentials is not None:
                        uaa = credentials.get('uaa', None)
                        if uaa is not None:
                            dependency = {'appId': uaa.get('xsappname', ''), 'appName': label}
                            dependencies.append(dependency)
    dependencies_json = json.dumps(dependencies)
    print(dependencies_json)
    return dependencies_json

@app.route('/onboarding/saas-registry/saas/register/tenants/<tenant_id>')
@auth_required(['Callback'])
def subscription_callback(tenant_id):
    print('Tenant ' + tenant_id + ' being subscribed')
    return 'Tenant ' + tenant_id + ' subscribed successfully'

@app.route('/admin/tokens')
@auth_required(['Administrator'])
def get_tokens():
    global tokens
    resp = Response(str(json.dumps(tokens)), mimetype='application/json')
    return resp

@app.route('/admin/token/<subdomain>/<landscape_host>/clear', methods = ['GET'])
@auth_required(['Administrator'])
def clear_token(subdomain, landscape_host):
    global tokens
    token_key = subdomain + ".authentication." + landscape_host
    token = tokens.get(token_key, None)
    if token is not None:
        del tokens[token_key]
    resp = Response(str(json.dumps(token)), mimetype='application/json')
    return resp

@app.route('/public/user-info-display')
@auth_required()
def display_user_info_display():
    authorization = None
    headers = request.headers
    print_request_headers(headers)
    response_str = 'Token Details: ';
    if 'Authorization' in headers.keys():
         authorization = headers.get('Authorization', None)
    if authorization:
        user_info = UserInfo(authorization)
        response_str += '  => Tenant ID: ' + user_info.get_identity_zone()
        response_str += '  => Subdomain ID: ' + user_info.get_subdomain()
        response_str += '  => Client ID: ' + user_info.get_client_id()
        response_str += '  => Is PDM User: ' + str(user_info.check_local_scope('PersonalDataManagerUser'))
        response_str += '  => Is Admin User: ' + str(user_info.check_local_scope('Administrator'))
        response_str += '  => Is Callback User: ' + str(user_info.check_local_scope('Callback'))
    else:
        return 'No Authorization provided in the request'
    return response_str

def check_for_allowed_request_methods(method):
    method_allowed = True
    if method == 'PUT':
        if cf_env.get_env_var_value('allow-update') == 'false':
            method_allowed = False
    elif method == 'POST':
        if cf_env.get_env_var_value('allow-update') == 'false':
            method_allowed = False
    elif method == 'DELETE':
        if cf_env.get_env_var_value('allow-delete') == 'false':
            method_allowed = False
    return method_allowed

@app.route('/proxy/<app>/<component>/<subdomain>/<path:path>', methods = ['HEAD', 'GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@auth_required(['ConsumingServiceUser'])
def call_service(app, component, subdomain, path):
    if not check_for_allowed_request_methods(request.method):
        return Response(str("Method not permitted"), mimetype='text/plain', status=http.client.BAD_REQUEST)
    status_code = http.client.OK
    headers = None
    format = request.args.get('$format')
    request_body = request.get_data().decode()
    if format == None:
        format = 'application/xml'
    else:
        format = 'application/json'
    service_config = get_service_config(app, component, subdomain)
    #resp = Response(str(json.dumps(service_config)), mimetype=format)
    url_splits = request.url.split('?')
    if len(url_splits) == 2:
        query_string = unquote(url_splits[1])
        #query_string = quote(url_splits[1], safe='~@#$&()*!+=:;,.?/\'')
        #query_string = quote(url_splits[1], safe='~()*!.\'')
    else:
        query_string = None
    full_path = service_config.get("serviceURI", "") + path
    if query_string is not None:
        full_path = full_path + '?' + query_string
    application_url = service_config.get("applicationURL","")
    application_url = process_application_url(application_url, service_config.get("landscapeHost",""))
    access_token = get_access_token(service_config)
    if access_token is None:
        data = "Failed to get the access token"
        status_code = http.client.BAD_REQUEST
        format = "text/plain"
    else:
        auth_header = 'Bearer ' + access_token
        headers = {'Authorization': auth_header}
        connection = http.client.HTTPSConnection(application_url)
        full_path = quote(full_path, safe='~@#$&()*!+=:;,.?/\'')
        connection.request(request.method, full_path, request_body, headers)
        response = connection.getresponse()
        status_code = response.status
        data = response.read().decode()
        if status_code == http.client.OK:
            headers = response.getheaders()
        else:
            print("Call to URL '" + application_url + full_path + "' failed with status '" + str(response.status) + "' with reason '" + response.reason + "'")
            print("Error Response Body:")
            print(data)
            content_type = get_response_header(response.getheaders(), "Content-Type")
            if content_type is not None:
                format = content_type
        connection.close()
    resp = Response(str(data), mimetype=format, status=status_code)
    if headers is not None:
        copy_response_headers(headers, resp)
        content_type = get_response_header(response.getheaders(), "Content-Type")
        if content_type is not None:
            format = content_type
    return resp

def print_request_headers(headers):
    print(headers)

def copy_response_headers(headers, response):
    white_list = ['Content-Type','Content-Length']
    for header in headers:
        index = -1
        try:
            index = white_list.index(header[0])
        except:
            index = -1
        if index > -1:
	        response.headers[header[0]] = header[1]

def get_response_header(headers, key):
    value = None
    for header in headers:
        if header[0] == key:
            value = header[1]
            break
    return value

def process_application_url(app_url, landscape_host):
    url = None
    splitresult = urlsplit(app_url)
    url = splitresult.path
    if not url.find(landscape_host):
        url += '.cfapps.' +  landscape_host
    return url

def get_access_token(service_config):
    access_token = None;
    uaa_url = service_config.get("subdomainId","") + ".authentication." + service_config.get("landscapeHost","");
    access_token = get_token_from_cache(uaa_url)
    if access_token is None:
        user_password = service_config.get("clientId","") + ":" + service_config.get("clientSecret","")
        basic_auth = base64.b64encode(user_password.encode())
        auth_header = 'Basic ' + basic_auth.decode()
        headers = {'Authorization': auth_header}
        token_uri = "/oauth/token?grant_type=client_credentials&response_type=token"
        connection = http.client.HTTPSConnection(uaa_url)
        connection.request("GET", token_uri, None, headers)
        response = connection.getresponse()
        if response.status == http.client.OK:
            data = response.read().decode()
            token = json.loads(data)
            access_token = token.get("access_token","")
            set_token_to_cache(uaa_url, token)
        else:
            print("Call to URL '" + uaa_url + token_uri + "' failed with status '" + str(response.status) + "' with reason '" + response.reason + "'")
            print("Error Response Body:")
            print(response.read().decode())
        connection.close()
    return access_token

def set_token_to_cache(key, token):
    global tokens
    token_offset_in_secs = 300
    if tokens is None:
        tokens = {}
    token["expires_at"] = (int)(time.time() + token.get("expires_in", token_offset_in_secs) - token_offset_in_secs)
    if check_token_validity(token):
        tokens[key] = token

def get_token_from_cache(key):
    global tokens
    access_token = None
    token = None
    if tokens is not None:
        token = tokens.get(key, None)
        if token is not None and check_token_validity(token):
            access_token = token.get("access_token", None)
    return access_token

def check_token_validity(token):
    is_valid = False
    if token is not None:
        if time.time() < token.get("expires_at", 0):
            is_valid = True
    return is_valid

def get_service_config(app, service, subdomain):
    global config
    apps = copy.deepcopy(config)
    service_config = None
    if apps is not None:
        app_config = apps[app]
        if app_config is not None:
            service_config = app_config.get("endPoints", {}).get(service, None)
            if service_config is not None:
                del app_config["endPoints"]
                service_config.update(app_config)
                tenant_config = service_config.get("tenants", {}).get(subdomain, {})
                service_config.update(tenant_config)
                del service_config["tenants"]
    return service_config

def initialize():
    global config
    config_str = None
    config_file = open("config/app-config.json","r")
    if config_file.mode == 'r':
        config_str = config_file.read()
    if config_str is not None:
        config = json.loads(config_str)

if __name__ == '__main__':
    initialize()
    # Run the app, listening on all IPs with our chosen port number
    app.run(host='0.0.0.0', port=port)

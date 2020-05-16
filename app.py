from flask import Flask, jsonify, make_response,request, session
from flask_swagger_ui import get_swaggerui_blueprint
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Date, cast, DateTime, Time, extract
from flask_cors import CORS, cross_origin

import json
import jwt
import time
import datetime
from pytz import timezone
from datetime import date, timedelta
from functools import wraps
from flask_session import Session
from six.moves.urllib.request import urlopen
from jose import jwt
import pytz
import requests

SESSION_TYPE = 'filesystem'
app = Flask(__name__)
app.config['CLIENT_ID'] = 'xMyRktEjNm1MJz2W6KO2bTeBImCjZRjg'
app.config['CLIENT_SECRET'] = '2rWdiq9DDhIjfz_zeswEvgTmztGxPos6T-TkMf-QhpExttiX6LqkUd5y68qJkdwD'
app.config['TOKEN_ENDPOINT'] = 'https://arlo-aq-api.auth0.com/oauth/token'
app.config['AUDIENCE'] = 'https://ARLO-AQ/api'
app.config['SECRET_KEY'] = '2rWdiq9DDhIjfz_zeswEvgTmztGxPos6T-TkMf-QhpExttiX6LqkUd5y68qJkdwD'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Zh6Q6C97@database-issp-air-quality-instance.cmamvcvbojfv.us-west-2.rds.amazonaws.com/airQualityApiDb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['CORS_HEADERS'] = 'Content-Type'
db = SQLAlchemy(app)

ALGORITHMS = ["RS256"]
# cors = CORS(app, resources={r"/readings": {"origins": "http://localhost:3000"}})
cors = CORS(app, resources={r"/*": {"origins": "*"}})


### swagger specific ###
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'
SWAGGERUI_BLUEPRINT = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "ARLO-Air-Quality-API"
    }
)
app.register_blueprint(SWAGGERUI_BLUEPRINT, url_prefix=SWAGGER_URL)
### end swagger specific ###

#Create Device object 
class Device_Info(db.Model):
    __tablename__ = 'device_info'
    device_id = db.Column(db.Integer, primary_key=True)
    device_name = db.Column(db.String(100))
    location_name = db.Column(db.String(100))
    active = db.Column(db.Boolean)

# Create Records object 
class Records(db.Model):
    __tablename__ = 'records'
    record_id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100))
    temp = db.Column(db.Float)
    humidity = db.Column(db.Float)
    co2 = db.Column(db.Float)
    tvoc = db.Column(db.Float)
    timestamp = db.Column(db.DateTime(timezone=True))

class User_Info(db.Model):
    __tablename__ = 'user'
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255))
    password = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    student_number = db.Column(db.String(255))
    access_token = db.Column(db.String(1000))
    token_expires = db.Column(db.String(255))

class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response


def get_token_auth_header():
    """Obtains the access token from the Authorization Header
    """
    auth = request.headers.get("Authorization", None)
    if not auth:
        raise AuthError({"code": "authorization_header_missing",
                        "description":
                            "Authorization header is expected"}, 401)

    parts = auth.split()

    if parts[0].lower() != "bearer":
        raise AuthError({"code": "invalid_header",
                        "description":
                            "Authorization header must start with"
                            " Bearer"}, 401)
    elif len(parts) == 1:
        raise AuthError({"code": "invalid_header",
                        "description": "Token not found"}, 401)
    elif len(parts) > 2:
        raise AuthError({"code": "invalid_header",
                        "description":
                            "Authorization header must be"
                            " Bearer token"}, 401)

    token = parts[1]
    return token

##setup flask jwt token
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_auth_header()

        
        jsonurl = urlopen("https://arlo-aq-api.auth0.com/.well-known/jwks.json")
        jwks = json.loads(jsonurl.read())
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.JWTError:
            raise AuthError({"code": "invalid_header",
                            "description":
                                "Invalid header. "
                                "Use an RS256 signed JWT Access Token"}, 401)
        if unverified_header["alg"] == "HS256":
            raise AuthError({"code": "invalid_header",
                            "description":
                                "Invalid header. "
                                "Use an RS256 signed JWT Access Token"}, 401)
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
        if rsa_key:
            try:
                payload = jwt.decode(
                    token,
                    rsa_key,
                    algorithms=ALGORITHMS,
                    audience='https://ARLO-AQ/api',
                    issuer="https://arlo-aq-api.auth0.com/"
                )
            except jwt.ExpiredSignatureError:
                raise AuthError({"code": "token_expired",
                                "description": "token is expired"}, 401)
            except jwt.JWTClaimsError:
                raise AuthError({"code": "invalid_claims",
                                "description":
                                    "incorrect claims,"
                                    " please check the audience and issuer"}, 401)
            except Exception:
                raise AuthError({"code": "invalid_header",
                                "description":
                                    "Unable to parse authentication"
                                    " token."}, 401)

            
            return f(*args, **kwargs)
        raise AuthError({"code": "invalid_header",
                        "description": "Unable to find appropriate key"}, 401)
    return decorated

# This function executes when /reading endpoint is called.
# This Post request by passing json payload and return specified data in json format.
@app.route("/readings", methods=['POST'])
@token_required
def records_test():

    data = request.get_json()

    output = []
    start = data['Start_date']
    end = data['End_date']
    deviceId = data['device_id']
    boolTemp = data['Temperature']
    boolHum = data['Humidity']
    boolTVOC = data['TVOC']
    boolCO2 = data['CO2']


    date_time_Start = datetime.datetime.strptime(start, '%Y-%m-%d %H:%M') + timedelta(hours=7)
    date_time_End = datetime.datetime.strptime(end, '%Y-%m-%d %H:%M') + timedelta(hours=7)

    recordsDataFilter= db.session.query(Records).filter(Records.device_id == deviceId).filter( Records.timestamp.between( date_time_Start, date_time_End)).order_by(Records.timestamp.asc()).all()
    
    for i in recordsDataFilter:
        records_test_data = {}
        records_test_data['record_id'] = i.record_id
        records_test_data['device_id'] = i.device_id
        if boolTemp :
            records_test_data['temp'] = i.temp
        if boolHum :
            records_test_data['humidity'] = i.humidity
        if boolCO2 :
            records_test_data['co2'] = i.co2
        if boolTVOC :
            records_test_data['tvoc'] = i.tvoc

        pacific_time_date = i.timestamp.astimezone(timezone('US/Pacific')) #convert to PDT timezone
        convert_date_format =datetime.datetime.strftime(pacific_time_date, '%Y-%m-%d %H:%M %Z')
        records_test_data['timestamp'] = convert_date_format

        output.append(records_test_data)
    return jsonify({'records_test_data' : output})

#This function gets the lastest recorded data for a specified device id
@app.route("/readings/device", methods=['POST'])
@token_required
def records_latest():
    data = request.get_json()

    output = []
    deviceId = data['id']
    recordsDataFilter = db.session.query(Records).filter(Records.device_id == deviceId).order_by(Records.record_id.desc()).first()
 
    records_test_data = {}
    records_test_data['record_id'] = recordsDataFilter.record_id
    records_test_data['device_id'] = recordsDataFilter.device_id
    records_test_data['temp'] = recordsDataFilter.temp
    records_test_data['humidity'] = recordsDataFilter.humidity
    records_test_data['co2'] = recordsDataFilter.co2
    records_test_data['tvoc'] = recordsDataFilter.tvoc
    pacific_time_date = recordsDataFilter.timestamp.astimezone(timezone('US/Pacific'))
    convert_date_format =datetime.datetime.strftime(pacific_time_date, '%Y-%m-%d %H:%M %Z')
    records_test_data['timestamp'] = convert_date_format
    output.append(records_test_data)
    return jsonify({'records_data' : output})

#This function gets devices information list
@app.route("/devices", methods=['POST'])
@token_required
def device_info():
    deviceInfoData = Device_Info.query.order_by(Device_Info.device_id.asc()).all()
    output = []

    for i in deviceInfoData:
        device_info_data = {}
        device_info_data['device_id'] = i.device_id
        device_info_data['device_name'] = i.device_name
        device_info_data['location_name'] = i.location_name
        device_info_data['active'] = i.active
        output.append(device_info_data)
    return jsonify({'device_info_data' : output})

@app.route('/token', methods=['POST'])
def token():
    auth = request.get_json()

    if not auth or not auth['username'] or not auth['password'] :
        return make_response('Could not verify', 401, {'WWW-Authenticate' : 'Basic realm="Login required!"'})
    
    user_query = db.session.query(User_Info).filter(User_Info.email == auth['username']).filter(User_Info.password == auth['password']).first()

    if user_query is None:
        return make_response('User not found', 404)
    
    token_expiry = datetime.datetime.strptime(user_query.token_expires,"%d-%b-%Y")
    current_date = datetime.datetime.now()

    expired = token_expiry < current_date

    if not expired:
        return jsonify({"access_token" : user_query.access_token})
    else:
        return token_refresh(auth['username'])

def token_refresh(username):
    user_query = db.session.query(User_Info).filter(User_Info.email == username).first()

    payload = {
        'grant_type' : 'client_credentials',
        'client_id' :  'i6Gsz4wzT4YKOzSHFdfQpaOFIPpxn4Qm',
        'client_secret' : 'ivaOrWXeEe4Wg-MLSYy_-Axo5g9Kj6ykUQcVlQ1Gfqkxmug4ysjJSUl8iAD4gY_s',
        'audience' : 'https://ARLO-AQ/api'
    }
    res = requests.post('https://arlo-aq-api.auth0.com/oauth/token', data = payload)
    token = res.json()
    date = datetime.datetime.now() + datetime.timedelta(30)
    timestampStr = date.strftime("%d-%b-%Y")

    user_query.access_token = token['access_token']
    user_query.token_expires = timestampStr
    db.session.commit()

    return jsonify({"access_token": token['access_token']})


#This function validates the username and password. Once validated, a username and time to live is encoded using JWT.
# JWT token will be jsonify and return back to client.
@app.route('/login', methods=['POST'])
@cross_origin()
def login():
    auth = request.get_json()

    if not auth or not auth['username'] or not auth['password'] :
        return make_response('Could not verify', 401, {'WWW-Authenticate' : 'Basic realm="Login required!"'})
    
    user_query = db.session.query(User_Info).filter(User_Info.email == auth['username']).filter(User_Info.password == auth['password']).first()

    if user_query is not None:
        return make_response('User is valid', 200)
    
    return make_response('Could not verify', 401)

@app.route('/signup',methods=['POST'])
@cross_origin()
def signup():
    user_signup_info = request.get_json()
    
    user_query = db.session.query(User_Info).filter(User_Info.email == user_signup_info['email']).first()

    if user_query is not None:
        return make_response('User Already Exists', 409)

    #Temporary Hide the id and secret
    payload = {
        'grant_type' : 'client_credentials',
        'client_id' :  'i6Gsz4wzT4YKOzSHFdfQpaOFIPpxn4Qm',
        'client_secret' : 'ivaOrWXeEe4Wg-MLSYy_-Axo5g9Kj6ykUQcVlQ1Gfqkxmug4ysjJSUl8iAD4gY_s',
        'audience' : 'https://ARLO-AQ/api'
    }
    res = requests.post('https://arlo-aq-api.auth0.com/oauth/token', data = payload)
    token = res.json()
    date = datetime.datetime.now() + datetime.timedelta(30)
    timestampStr = date.strftime("%d-%b-%Y")

    user = User_Info()
    user.email = user_signup_info['email']
    user.first_name = user_signup_info['first_name']
    user.last_name = user_signup_info['last_name']
    user.password = user_signup_info['password']
    user.student_number = user_signup_info['student_number']
    user.access_token = token['access_token']
    user.token_expires = timestampStr
    db.session.add(user)
    db.session.commit()
    
    return make_response('User Created',200)


@app.route('/profile',methods=['POST'])
def profile():
    user_req = request.get_json()
    
    user_query = db.session.query(User_Info).filter(User_Info.email == user_req['username']).first()

    if user_query is None:
        return make_response('Unauthorized',401)
    
    return jsonify({
        "firstname" : user_query.first_name, 
        "lastname"  : user_query.last_name,
        "email"     : user_query.email,
        "token"     : user_query.access_token})
    









if __name__ == '__main__':
    app.run(host='0.0.0.0')

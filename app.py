from flask import Flask, jsonify, make_response,request, session
from flask_swagger_ui import get_swaggerui_blueprint
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Date, cast, DateTime, Time, extract
from flask_cors import CORS, cross_origin
import jwt
import time
import datetime
from pytz import timezone
from datetime import date, timedelta
from functools import wraps
from flask_session import Session
import pytz

SESSION_TYPE = 'filesystem'
app = Flask(__name__)
app.config['SECRET_KEY'] = 'thisissecret'
#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:admin@localhost/postgres'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Zh6Q6C97@database-issp-air-quality-instance.cmamvcvbojfv.us-west-2.rds.amazonaws.com/airQualityApiDb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['CORS_HEADERS'] = 'Content-Type'
db = SQLAlchemy(app)

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

#Create Device_test object
class Device_Info(db.Model):
    __tablename__ = 'device_info'
    device_id = db.Column(db.Integer, primary_key=True)
    device_name = db.Column(db.String(100))
    location_name = db.Column(db.String(100))
    device_lng = db.Column(db.Float)
    device_lat = db.Column(db.Float)

# Create records_test object
class Records(db.Model):
    __tablename__ = 'records'
    record_id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100))
    temp = db.Column(db.Float)
    humidity = db.Column(db.Float)
    co2 = db.Column(db.Float)
    tvoc = db.Column(db.Float)
    timestamp = db.Column(db.DateTime(timezone=True))


##setup flask jwt token
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.args.get('token') #http://127.0.0.1:5000/route?token=<token key>
        if not token:
            return jsonify({'message' : 'Token is missing!'}), 401
        try:
            data = jwt.decode(token,app.config['SECRET_KEY'])
        except:
            return jsonify({'message' : 'Token is invalid!'}), 401
        return f(*args, **kwargs)
    return decorated

#Post request by passing json payload and return specified data 
@app.route("/readings", methods=['POST'])
@token_required
@cross_origin()
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

    recordsDataFilter= db.session.query(Records).filter(Records.device_id == deviceId).filter( Records.timestamp.between( date_time_Start, date_time_End)).all()

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

        pacific_time_date = i.timestamp.astimezone(timezone('US/Pacific'))
        convert_date_format =datetime.datetime.strftime(pacific_time_date, '%Y-%m-%d %H:%M %Z')
        records_test_data['timestamp'] = convert_date_format

        output.append(records_test_data)
    return jsonify({'records_test_data' : output})

#get the lastest recorded data for a specified device id
@app.route("/readings/device", methods=['GET'])
@token_required
def records_latest():
    output = []
    deviceId = request.args.get('id')
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

#get devices information
@app.route("/devices", methods=['GET'])
def device_test():
    deviceTestData = Device_Info.query.all()
    output = []

    for i in deviceTestData:
        device_test_data = {}
        device_test_data['device_id'] = i.device_id
        device_test_data['device_name'] = i.device_name
        device_test_data['location_name'] = i.location_name
        device_test_data['device_lng'] = i.device_lng
        device_test_data['device_lat'] = i.device_lat
        output.append(device_test_data)
    return jsonify({'device_test_data' : output})

@app.route('/login', methods=['POST'])
@cross_origin()
def login():
    auth = request.get_json()

    if not auth or not auth['username'] or not auth['password'] :
        return make_response('Could not verify', 401, {'WWW-Authenticate' : 'Basic realm="Login required!"'})
   
    if auth and auth['password'] == 'bcitairquality' and auth['username'] == 'bcitarlo':
        token = jwt.encode({'user': auth['username'], 'exp': datetime.datetime.utcnow()+ datetime.timedelta(minutes=120)},app.config['SECRET_KEY'])
        return jsonify({'token' : token.decode('UTF-8')})

    return make_response('Could not verify', 401)

if __name__ == '__main__':
    app.run(host='0.0.0.0')

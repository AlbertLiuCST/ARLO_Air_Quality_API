
/*==========================================================================
 *  Connects arduino uno wifi rev2 to mosquitto server hosted on AWS. 
 *  By default it will send a message once every 900 seconds (15 minutes). To update this
 *  a message can be sent to the topic "update_arduino" in the format of <deviceid>-<seconds>.
 *  The client that accepts this will publish to the topic "update_arduino_accepted" 
 *  For example, the message "3-60" published to "update_arduino" will update device arduino3 to 
 *  send once every 60 seconds.
 *  arduino3 will then publish "Accepted by arduino3" to the "update_arduino_accepted" topic
 *  IMPORTANT STEPS:
 *    - replace SECRET_SSID, SECRET_PASS
 *    - replace CLIENT_ID with the arduino device number
 *    - include library PubSubClient and WiFiNINA. if using arduino ide
 *      go to Sketch -> Include Library -> Manage Libraries -> enter name in search bar
 *    - open PubSubClient source files (in Libraries directory, this should be in the parent folder where your sketch)
 *      with any other code editor like VS Code. Open PubSubClient.h and:
 *        - change line 26 MQTT_MAX_PACKET_SIZE to 360
 *        - change line 31 MQTT_KEEPALIVE value to 60
 *    - Save updated PubSubClient.h and upload this sketch to board
 *  
 */
#include <PubSubClient.h>
#include <WiFiNINA.h>
#include <sensirion_ess.h>

#define SECRET_SSID "<ssid>" //Replace with your Wifi SSID
#define SECRET_PASS "<password>" //Replace with your WPA2 password
#define CLIENT_ID 0  //Replace with your device number (1 - 8)
#define MSG_SIZE 120
#define MILLISECONDS 1000
#define LOOP_SECONDS 10 //mqtt loop every 10 seconds to check for updates
#define AWS_MSG_FORMAT       \
   "{\"state\":{"                  \
     "\"reported\":{"             \
     "\"arduino_id\":\"%d\","  \
     "\"temp\":\"%s\","  \
     "\"humidity\":\"%s\","        \
     "\"tvoc\":\"%s\","        \
     "\"CO2\":\"%s\""            \
   "}}}"

char client_name[10];
char ssid[] = SECRET_SSID;        // your network SSID (name)
char pass[] = SECRET_PASS;    // your network password (use for WPA, or use as key for WEP)
int status = WL_IDLE_STATUS;     // the Wifi radio's status
byte server[] = {34,216,131,235}; //Replace with the IP of mosquitto server
int port = 1883; //the port of the MQTT broker
char updateShadowTopic[64];
char updateTopic[] = "update_arduino";
char updateAcceptedTopic[] = "update_arduino_accepted";
int intervalSeconds = 900; //default value - send message every 15 minutes

   
// Handles messages arrived on subscribed topic(s)
// payload is in format <device_id>-<seconds interval>
void callback(char* topic, byte* payload, unsigned int length) {
  Serial.println("Message arrived!");
  char message[length+1];
  memset(message, 0, length+1);
  for (int i = 0; i < length; i++) {
    message[i] = (char)payload[i];
  }
  message[length] = '\n';

  char delimiter[2] = "-";
  char* recipientId = strtok(message, delimiter);
  char* interval = strtok(NULL, delimiter);
  //char* intervals = strtok(message, delimiter);
  if (atoi(recipientId) == CLIENT_ID) {
    intervalSeconds = atoi(interval);
    Serial.print("New interval set for: ");
    Serial.print(intervalSeconds);
    Serial.print(" seconds");
    Serial.println("");
    char acceptMsg[24];
    sprintf(acceptMsg, "Accepted by arduino%d", CLIENT_ID);
    publishToAWS(updateAcceptedTopic, acceptMsg);
  } 
  Serial.println("");
}

void printWifiData() {
  // print your board's IP address:
  IPAddress ip = WiFi.localIP();
  Serial.print("IP Address: ");
  Serial.println(ip);
  Serial.println(ip);

  // print your MAC address:
  byte mac[6];
  WiFi.macAddress(mac);
  Serial.print("MAC address: ");
  printMacAddress(mac);
}

void printCurrentNet() {
  // print the SSID of the network you're attached to:
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());

  // print the MAC address of the router you're attached to:
  byte bssid[6];
  WiFi.BSSID(bssid);
  Serial.print("BSSID: ");
  printMacAddress(bssid);

  // print the received signal strength:
  long rssi = WiFi.RSSI();
  Serial.print("signal strength (RSSI):");
  Serial.println(rssi);

  // print the encryption type:
  byte encryption = WiFi.encryptionType();
  Serial.print("Encryption Type:");
  Serial.println(encryption, HEX);
  Serial.println();
}

void printMacAddress(byte mac[]) {
  for (int i = 5; i >= 0; i--) {
    if (mac[i] < 16) {
      Serial.print("0");
    }
    Serial.print(mac[i], HEX);
    if (i > 0) {
      Serial.print(":");
    }
  }
  Serial.println();
}
WiFiClient wifiClient;
PubSubClient mqttClient(server, port, callback, wifiClient);//Local Mosquitto Connection
SensirionESS ess; //  Create an instance of SensirionESS

void subscribeToUpdates() {
  Serial.println("Subscribing to update_arduino topic...");
  int rc = mqttClient.subscribe(updateTopic);
  if (rc < 1) {
    Serial.println("Failed");
  } else {
    Serial.println("Success");
  }
}
void reconnect() {
  // Loop until we're reconnected
  while (!mqttClient.connected()) {
    Serial.print("Attempting to reconnect MQTT connection...");
    // Attempt to connect
    if (mqttClient.connect(client_name)) {
      Serial.println("Connected");
      subscribeToUpdates();
    } else {
      Serial.print("Could not connect: ");
      Serial.print(mqttClient.state());
      Serial.println(" try again in 5 seconds");
      // Wait 5 seconds before retrying
      delay(5000);
    }
  }
}

void publishToAWS(char* topic, char* message) {
  boolean rc = mqttClient.publish(topic, message);
  if (rc == 0) {
    Serial.println("Fail to publish message:");
    Serial.println(rc);
    Serial.print("Connection failed. MQTT client state is: ");
    Serial.println(mqttClient.state());
    //do not continue
    reconnect();
  }
  Serial.println(message);
  Serial.print("Published to ");
  Serial.print(topic);
  Serial.println("");
}
void setup() {
  
  //Initialize serial and wait for port to open:
  Serial.begin(9600);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }
  sprintf(client_name, "arduino%d", CLIENT_ID);
  sprintf(updateShadowTopic, "$aws/things/%s/shadow/update", client_name);
  // Initialize the sensors; this should only fail if
  // the board is defect, or the connection isn't working. Since there's nothing
  // we can do if this fails, the code will loop forever if an error is detected
  if (ess.initSensors() != 0) {
      Serial.print("Error while initializing sensors: ");
      Serial.print(ess.getError());
      Serial.print("\n");
      while (1) { // loop forever
        delay(1000);
      }
  }
  
  // The SGP sensor has product type information and feature set stored
  // the following code reads it out, and prints it to the serial console.
  // This is purely to demo the function calls, and is not necessary to operate
  // the sensor
  int type = ess.getProductType();
  int fsVersion = ess.getFeatureSetVersion();

  Serial.print((type == SensirionESS::PRODUCT_TYPE_SGP30) ? "SGP30" : "SGPC3");
  Serial.print(" detected, running feature set version ");
  Serial.println(fsVersion);
  
  //WiFi Connection -- Start
  // check for the WiFi module:
  int status = WiFi.status();
  if (WiFi.status() == WL_NO_SHIELD) {
    Serial.println("Communication with WiFi module failed!");
    // don't continue
    while (true);
  } 

  String fv = WiFi.firmwareVersion();
  if (fv < "1.0.0") {
    Serial.println("Please upgrade the firmware");
  }

  // attempt to connect to Wifi network:
  while (status != WL_CONNECTED) {
    Serial.print("Attempting to connect to WPA SSID: ");
    Serial.println(ssid);
    // Connect to WPA/WPA2 network:
    status = WiFi.begin(ssid, pass);

    // wait 10 seconds for connection:
    delay(10000);
  }

  // you're connected now, so print out the data:
  Serial.print("You're connected to the network");
  printCurrentNet();
  printWifiData();
  //WiFi Connection -- End
  
  //Local Mosquitto Connection -- Start
  if (mqttClient.connect(client_name)) {
    subscribeToUpdates();
  } else {
      // connection failed
      // mqttClient.state() will provide more information
      // on why it failed.
      Serial.print("Connection failed. MQTT client state is: ");
      Serial.println(mqttClient.state());
      reconnect();
   }
}

void loop() {
  float temp, rh, tvoc, eco2 = -1;
  char str_temp[7];
  char str_rh[7];
  char str_tvoc[7];
  char str_eco2[7];
  // we'll start by triggering a measurement of the VOC/CO2 sensor;
  // it's important to do this first to make sure sleep timing is
  // correct. If the command succeeds, the local variables will
  // be set to the values we just read; if it fails, they'll be -1
  if (ess.measureIAQ() != 0) {
    Serial.print("Error while measuring IAQ: ");
    Serial.print(ess.getError());
    Serial.print("\n");
  } else {
    tvoc = ess.getTVOC();
    eco2 = ess.getECO2(); // SGP30 only
  }
  //trigger the humidity and temperature measurement
  if (ess.measureRHT() != 0) {
    Serial.print("Error while measuring RHT: ");
    Serial.print(ess.getError());
    Serial.print("\n");
  } else {
    temp = ess.getTemperature();
    rh = ess.getHumidity();
  }

  Serial.print("\n");
  Serial.println("Publishing...");
  dtostrf(temp, 4, 2, str_temp);
  dtostrf(rh, 4, 2, str_rh);
  dtostrf(tvoc, 4, 2, str_tvoc);
  dtostrf(eco2, 4, 2, str_eco2);
  char message[MSG_SIZE];
  sprintf(message, AWS_MSG_FORMAT, CLIENT_ID, str_temp, str_rh, str_tvoc, str_eco2);
  publishToAWS(updateShadowTopic, message);
  int currentInterval = intervalSeconds;
  int timesToLoop = currentInterval / LOOP_SECONDS;
  int remainder = currentInterval % LOOP_SECONDS;
  for(int i = 0; i < timesToLoop; i++) {
    if (currentInterval != intervalSeconds) {
      //interval has been updated, break
      break;
    }
    mqttClient.loop(); // check the network connection at least once every 10 seconds:
    delay(10000);
  }
  delay(remainder * MILLISECONDS);
}
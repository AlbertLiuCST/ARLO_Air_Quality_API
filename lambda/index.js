
var { Client } = require("pg");


exports.handler = function(event, context) {
var { arduino_id, temp, humidity, tvoc, CO2 } = event.state.reported;

console.log("event: " + JSON.stringify(event));
const client = new Client({
    user: 'postgres',
    host: 'database-issp-air-quality-instance.cmamvcvbojfv.us-west-2.rds.amazonaws.com',
    database: 'airQualityApiDb',
    password:'Zh6Q6C97',
    port: 5432,
})

client.connect();

const text = 'INSERT INTO records_test(device_id, temp, humidity, co2, tvoc, timestamp) VALUES($1, $2, $3, $4, $5, CURRENT_TIMESTAMP) RETURNING *'
const values = [arduino_id, temp, humidity, CO2, tvoc];
// callback
client.query(text, values, (err, res) => {
  if (err) {
    console.log(err.stack)
  } else {
    console.log(res.rows[0])
  }
  client.end();
})
};
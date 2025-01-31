int ledPin = 11;


void setup() {
  Serial.begin(9600);
  pinMode(ledPin, OUTPUT);
}


void loop() {
 digitalWrite(11, HIGH);


 if (Serial.available()) {
    char data = Serial.read();
    if (data == '1') {
      digitalWrite(ledPin, HIGH);
      delay(5000);
      digitalWrite(ledPin, LOW);
    }
  }
}

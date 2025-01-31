import socket
import sys
import threading
import time
import json

class P2PClient:
    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port
        self.username = None
        self.password = None
        self.role = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect_to_server(self):
        try:
            self.sock.connect((self.server_ip, self.server_port))
            print(f"Connected to server at {self.server_ip}:{self.server_port}")
        except Exception as e:
            print(f"Error connecting to server: {e}")
            sys.exit(1)

    def authenticate(self):
        self.username = input("Enter your username: ")
        self.password = input("Enter your password: ")
        
        auth_message = {
            'type': 'AUTH',
            'username': self.username,
            'password': self.password
        }
        self.sock.sendall(json.dumps(auth_message).encode())
        response = self.sock.recv(1024).decode()
        # Parse the JSON response
        response_data = json.loads(response)
        # Check the status field in the parsed JSON
        if response_data.get("status") == "AUTH_SUCCESS":
            print("Authentication successful.")
            return True
        else:
            print("Authentication failed. Exiting.")
            return False
    def buyer_led(self):
        LED_PIN = 18  # Adjust this if your LED is connected to a different pin
        GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
        GPIO.setup(LED_PIN, GPIO.OUT)  # Set the pin as an output
        print("Receving energy")
        for i in range(5): # Blink the LED 5 times
            GPIO.output(LED_PIN, GPIO.HIGH)  # Turn the LED on
            time.sleep(1)  # Wait for 1 second
            GPIO.output(LED_PIN, GPIO.LOW)  # Turn the LED off
            time.sleep(1)  # Wait for 1 second
        GPIO.cleanup()
        
    def seller_led(self):
        LED_PIN = 18  # Adjust this if your LED is connected to a different pin
        GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
        GPIO.setup(LED_PIN, GPIO.OUT)  # Set the pin as an output
        print("Tranferring energy")
        for i in range(5): # Blink the LED 5 times
            GPIO.output(LED_PIN, GPIO.HIGH)  # Turn the LED on
            time.sleep(2)  # Wait for 1 second
        GPIO.cleanup()

    def user_interaction_loop(self):
        while True:
            print("\nThank you for choosing P2P Energy Trading, leading to clean and greener energy.")
            choice = input("Do you want to be a seller, buyer, or exit?\n(For seller press 1, buyer press 2, exit press 3): ")
            
            if choice == '1':
                self.register_seller()
            elif choice == '2':
                self.buyer_menu()
            elif choice == '3':
                print("Exiting. Thank you for using P2P Energy Trading.")
                self.sock.close()
                break
            else:
                print("Invalid selection, please enter the required input again.")

    def register_seller(self):
        energy_type = input("Type of energy (e.g., solar, wind): ")
        energy_amount = float(input("Amount of energy available (in kWh): "))
        price = float(input("Price per kWh: "))

        seller_message = {
            'type': 'SELLER_REGISTER',
            'username': self.username,
            'energy_type': energy_type,
            'energy_amount': energy_amount,
            'price': price
        }
        self.sock.sendall(json.dumps(seller_message).encode())

        print("You are now registered as a seller.")
        self.seller_continue()

    def seller_continue(self):
        """
        Provides options for the seller to manage their registration.
        """
        while True:
            print("\nDo you want to:")
            print("1. Change price")
            print("2. Change amount of energy")
            print("3. Wait")
            print("4. Exit")
            seller_choice = input("Enter your choice: ")

            if seller_choice == '1':
                while True:
                  try:
                    new_price = float(input("Enter new price per kWh: "))
                    break
                  except ValueError:
                      print("Invalid input, please enter a number.")            
                update_message = {
                    'type': 'SELLER_UPDATE',
                    'username': self.username,
                    'field': 'price',
                    'value': new_price
                }
                self.sock.sendall(json.dumps(update_message).encode())
                print("Price updated successfully.")

            elif seller_choice == '2':
                while True:
                  try:
                    new_amount = float(input("Enter new amount of energy available (in kWh): "))
                    break
                  except ValueError:
                      print("Invalid input, please enter a number.")            
                update_message = {
                    'type': 'SELLER_UPDATE',
                    'username': self.username,
                    'field': 'energy_amount',
                    'value': new_amount
                }
                self.sock.sendall(json.dumps(update_message).encode())
                print("Energy amount updated successfully.")

            elif seller_choice == '3':
                print("Waiting... Press Enter to continue.")
                input()

            elif seller_choice == '4':
                print("Exiting seller menu.")
                exit_message = {
                    'type': 'SELLER_EXIT',
                    'username': self.username
                }
                self.sock.sendall(json.dumps(exit_message).encode())
                print("You have been removed from the seller list.")
                break

            else:
                print("Invalid selection, please try again.")
    def buyer_menu(self):
        needed_energy = float(input("How much electricity (in kWh) do you need? "))

        buyer_message = {
            'type': 'BUYER_REQUEST',
            'username': self.username,
            'needed_energy': needed_energy
        }
        self.sock.sendall(json.dumps(buyer_message).encode())

        response = self.sock.recv(4096).decode()
        sellers = eval(response)

        if not sellers:
            print("No sellers available with sufficient energy.")
            return

        print("\nAvailable Sellers:")
        for idx, seller in enumerate(sellers, start=1):
            print(f"{idx}. {seller['username']} - {seller['energy_type']}, {seller['price']} per kWh, {seller['energy_amount']} kWh available")

        choice = int(input("Select a seller by number (or 0 to cancel): "))
        if choice == 0:
            print("Transaction canceled.")
            return

        selected_seller = sellers[choice - 1]
        transaction_message = {
            'type': 'TRANSACTION',
            'buyer': self.username,
            'seller': selected_seller['username'],
            'energy_amount': needed_energy
        }
        self.sock.sendall(json.dumps(transaction_message).encode())

        print(f"Transaction completed with {selected_seller['username']}.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python client.py <server_ip> <server_port>")
        sys.exit(1)

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])

    client = P2PClient(server_ip, server_port)
    client.connect_to_server()

    if client.authenticate():
        client.user_interaction_loop()

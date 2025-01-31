import socket
import threading
import json
import time
import serial
import logging

# Set up logging
logging.basicConfig(level=logging.WARNING)  # Set to WARNING to suppress info messages
logger = logging.getLogger(__name__)

class Peer:
    def __init__(self, host, port, peers, user_id_start):
        self.host = host
        self.port = port
        self.peers = peers  # List of tuples: [(host, port), ...]
        self.sellers = {}  # Keyed by user_id
        self.lock = threading.Lock()
        self.user_id = user_id_start  # Assign unique user ID per peer

        # Initialize serial communication with Arduino
        arduino_port = 'COM4'  # Replace with your Arduino's port
        baud_rate = 9600
        try:
            self.ser = serial.Serial(arduino_port, baud_rate, timeout=1)
            time.sleep(2)  # Wait for serial connection to initialize
            print("Connected to Arduino")
        except Exception as e:
            print(f"Failed to connect to Arduino: {e}")
            self.ser = None


    def start(self):
        # Start server thread
        threading.Thread(target=self.server_loop, daemon=True).start()
        # Start user interaction loop
        threading.Thread(target=self.user_interaction_loop, daemon=True).start()
        # Start peer synchronization loop
        threading.Thread(target=self.peer_synchronization_loop, daemon=True).start()

    def server_loop(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind((self.host, self.port))
        server_sock.listen()
        logger.info(f"Listening on {self.host}:{self.port}")
        while True:
            client_sock, addr = server_sock.accept()
            threading.Thread(target=self.handle_connection, args=(client_sock, addr), daemon=True).start()

    def handle_connection(self, client_sock, addr):
        try:
            data = client_sock.recv(4096)
            if not data:
                client_sock.close()
                return
            message = json.loads(data.decode())
            self.process_message(message)
            client_sock.close()
        except Exception as e:
            logger.error(f"Error handling connection from {addr}: {e}")
            client_sock.close()

    def process_message(self, message):
        msg_type = message.get('type')
        if msg_type == 'SELLER_REGISTER':
            seller_info = message['seller_info']
            with self.lock:
                self.sellers[seller_info['user_id']] = seller_info
            logger.info(f"New seller registered: User{seller_info['user_id']} - {seller_info['energy_type']} at {seller_info['price']} per kWh")
        elif msg_type == 'SELLER_UPDATE':
            seller_info = message['seller_info']
            with self.lock:
                self.sellers[seller_info['user_id']] = seller_info
            logger.info(f"Seller User{seller_info['user_id']} updated their offering.")
        elif msg_type == 'SELLER_EXIT':
            seller_id = message['seller_id']
            with self.lock:
                if seller_id in self.sellers:
                    del self.sellers[seller_id]
            logger.info(f"Seller User{seller_id} has exited and been removed.")
        elif msg_type == 'TRANSACTION':
            seller_id = message['seller_id']
            energy_sold = message['energy_sold']
            buyer_id = message['buyer_id']
            with self.lock:
                if seller_id in self.sellers:
                    self.sellers[seller_id]['energy_amount'] -= energy_sold
                    if self.sellers[seller_id]['energy_amount'] <= 0:
                        del self.sellers[seller_id]
            print(f"Transaction occurred with Seller User{seller_id}.")

            # Notify the seller if they are on this peer
            if seller_id == self.user_id:
                print(f"\nYour energy has been sold. Remaining energy: {self.sellers.get(seller_id, {}).get('energy_amount', 0)} kWh")
                if seller_id not in self.sellers:
                    print("You have sold all your energy.")
                    self.post_sale_options()
                # Signal seller's Arduino
                self.signal_arduino()

            # Notify the buyer if they are on this peer
            if buyer_id == self.user_id:
                print("\nYou have successfully purchased energy.")
                # Signal buyer's Arduino
                self.signal_arduino()

        elif msg_type == 'SYNC_REQUEST':
            response = {
                'type': 'SYNC_RESPONSE',
                'sellers': self.sellers
            }
            self.send_message(message['from_host'], message['from_port'], response)
        elif msg_type == 'SYNC_RESPONSE':
            with self.lock:
                self.sellers.update(message['sellers'])
        else:
            logger.warning(f"Unknown message type: {msg_type}")

    def send_message(self, peer_host, peer_port, message):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((peer_host, peer_port))
            sock.send(json.dumps(message).encode())
            sock.close()
        except Exception as e:
            logger.debug(f"Failed to send message to {peer_host}:{peer_port} - {e}")

    def broadcast_message(self, message):
        for (peer_host, peer_port) in self.peers:
            self.send_message(peer_host, peer_port, message)

    def peer_synchronization_loop(self):
        # Periodically synchronize with peers
        while True:
            time.sleep(5)
            sync_request = {
                'type': 'SYNC_REQUEST',
                'from_host': self.host,
                'from_port': self.port
            }
            self.broadcast_message(sync_request)

    def user_interaction_loop(self):
        while True:
            print("\nThank you for choosing P2P Energy Trading, leading to clean and greener energy.")
            while True:
                choice = input("Do you want to be a seller, buyer, or nothing?\n(For seller press 1, buyer press 2, nothing press 3): ")
                if choice in ['1', '2', '3']:
                    break
                else:
                    print("Invalid selection, please enter the required input again.")

            if choice == '1':
                self.register_seller()
            elif choice == '2':
                self.buyer_menu()
            elif choice == '3':
                print("Thank you for using P2P Energy Trading.")
                break

    def register_seller(self):
        name = input("Enter your name: ")
        energy_type = input("Type of energy (e.g., solar, wind): ")
        while True:
            try:
                energy_amount = float(input("Amount of energy available (in kWh): "))
                break
            except ValueError:
                print("Invalid input, please enter a number.")
        while True:
            try:
                price = float(input("Price per kWh: "))
                break
            except ValueError:
                print("Invalid input, please enter a number.")

        user_id = self.user_id  # Use self.user_id assigned in __init__

        self.seller_id = user_id  # Keep track of seller's own ID

        seller_info = {
            'user_id': user_id,
            'name': name,
            'energy_type': energy_type,
            'energy_amount': energy_amount,
            'price': price,
            'host': self.host,
            'port': self.port
        }
        with self.lock:
            self.sellers[user_id] = seller_info
        print(f"Assigned User ID: {user_id}")
        print(f"Welcome, {name}! You are now a seller.")

        # Broadcast seller registration to peers
        message = {
            'type': 'SELLER_REGISTER',
            'seller_info': seller_info,
        }
        self.broadcast_message(message)

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
                with self.lock:
                    self.sellers[user_id]['price'] = new_price
                print("Price updated.")
                # Broadcast update
                message = {
                    'type': 'SELLER_UPDATE',
                    'seller_info': self.sellers[user_id],
                }
                self.broadcast_message(message)
            elif seller_choice == '2':
                while True:
                    try:
                        new_amount = float(input("Enter new amount of energy available (in kWh): "))
                        break
                    except ValueError:
                        print("Invalid input, please enter a number.")
                with self.lock:
                    self.sellers[user_id]['energy_amount'] = new_amount
                print("Amount of energy updated.")
                # Broadcast update
                message = {
                    'type': 'SELLER_UPDATE',
                    'seller_info': self.sellers[user_id],
                }
                self.broadcast_message(message)
            elif seller_choice == '3':
                print("Waiting...")
                input("Press Enter to continue...")
            elif seller_choice == '4':
                print("Exiting seller menu.")
                # Broadcast seller exit
                message = {
                    'type': 'SELLER_EXIT',
                    'seller_id': user_id
                }
                self.broadcast_message(message)
                with self.lock:
                    if user_id in self.sellers:
                        del self.sellers[user_id]

                break
            else:
                print("Invalid selection, please enter the required input again.")

    def post_sale_options(self):
        while True:
            print("\nDo you want to:")
            print("1. Add more energy to sell")
            print("2. Become a buyer")
            print("3. Exit")
            choice = input("Enter your choice: ")
            if choice == '1':
                self.register_seller()
                break
            elif choice == '2':
                self.buyer_menu()
                break
            elif choice == '3':
                print("Exiting.")
                break
            else:
                print("Invalid selection, please enter the required input again.")

    def buyer_menu(self):
        while True:
            try:
                needed_energy = float(input("How much electricity (in kWh) do you need? "))
                break
            except ValueError:
                print("Invalid input, please enter a number.")

        while True:
            available_sellers = []
            with self.lock:
                sellers_copy = self.sellers.copy()
            for idx, seller in enumerate(sellers_copy.values(), start=1):
                if seller['energy_amount'] >= needed_energy:
                    available_sellers.append((idx, seller))

            if available_sellers:
                print("\nAvailable Sellers:")
                for num, seller in available_sellers:
                    print(f"{num}. User{seller['user_id']} - Type: {seller['energy_type']}, Price: {seller['price']} per kWh")
                print(f"{len(available_sellers) + 1}. Do not buy now")
                buyer_choice = input("Press the seller's number to buy or press the last number to not buy: ")
                if buyer_choice.isdigit():
                    buyer_choice = int(buyer_choice)
                    if 1 <= buyer_choice <= len(available_sellers) + 1:
                        if buyer_choice == len(available_sellers) + 1:
                            print("You chose not to buy now.")
                            while True:
                                print("\nDo you want to:")
                                print("1. Reduce required energy amount")
                                print("2. Wait for new sellers or existing sellers to change price")
                                print("3. Exit")
                                wait_choice = input("Enter your choice: ")
                                if wait_choice == '1':
                                    while True:
                                        try:
                                            needed_energy = float(input("Enter new required energy amount (in kWh): "))
                                            break
                                        except ValueError:
                                            print("Invalid input, please enter a number.")
                                    break  # Go back to check available sellers
                                elif wait_choice == '2':
                                    print("Waiting for new sellers or existing sellers to change price...")
                                    input("Press Enter to refresh seller list...")
                                    break  # Go back to check available sellers
                                elif wait_choice == '3':
                                    print("Exiting buyer menu.")
                                    return
                                else:
                                    print("Invalid selection, please enter the required input again.")
                        else:
                            selected_seller = available_sellers[buyer_choice - 1][1]
                            seller_id = selected_seller['user_id']
                            with self.lock:
                                if seller_id in self.sellers and self.sellers[seller_id]['energy_amount'] >= needed_energy:
                                    self.sellers[seller_id]['energy_amount'] -= needed_energy
                                    print(f"You have chosen to buy from User{seller_id}")
                                    print("Thank you for buying energy.")
                                    # Broadcast transaction
                                    message = {
                                        'type': 'TRANSACTION',
                                        'seller_id': seller_id,
                                        'energy_sold': needed_energy,
                                        'buyer_id': self.user_id  # Include buyer's user ID
                                    }
                                    self.broadcast_message(message)
                                    # Signal buyer's Arduino
                                    self.signal_arduino()

                                    # Break after successful transaction
                                    break
                                else:
                                    print("Seller does not have enough energy or is no longer available. Please choose another seller.")
                            # Go back to check available sellers
                    else:
                        print("Invalid selection, please enter the required input again.")
                else:
                    print("Invalid selection, please enter the required input again.")
            else:
                print("No sellers have enough energy available.")
                while True:
                    print("\nDo you want to:")
                    print("1. Reduce required energy amount")
                    print("2. Wait for new sellers or existing sellers to change price")
                    print("3. Exit")
                    wait_choice = input("Enter your choice: ")
                    if wait_choice == '1':
                        while True:
                            try:
                                needed_energy = float(input("Enter new required energy amount (in kWh): "))
                                break
                            except ValueError:
                                print("Invalid input, please enter a number.")
                        break  # Go back to check available sellers
                    elif wait_choice == '2':
                        print("Waiting for new sellers or existing sellers to change price...")
                        input("Press Enter to refresh seller list...")
                        break  # Go back to check available sellers
                    elif wait_choice == '3':
                        print("Exiting buyer menu.")
                        return
                    else:
                        print("Invalid selection, please enter the required input again.")

    def signal_arduino(self):
        if self.ser:
            try:
                self.ser.write(b'1')
                print("Signaled Arduino")
            except Exception as e:
                print(f"Failed to signal Arduino: {e}")
        else:
            print("Arduino serial connection not established.")

# Configuration for hardcoded IPs
# Replace with actual IPs and ports
# For each peer, set the LOCAL_HOST, LOCAL_PORT, PEERS, and USER_ID_START accordingly
# Example for Peer 1
LOCAL_HOST = '192.xxx.xxx.xxx'  # Replace with actual IP
LOCAL_PORT = 5000
PEERS = [
    ('192.xxx.xxx.xxx', 5000),
    ('192.yyy.yyy.yyy', 5000),
    ('192.zzz.zzz.zzz', 5000)
]
USER_ID_START = 100  # Peer 1's user_id

# Remove own IP from PEERS
PEERS = [(host, port) for (host, port) in PEERS if host != LOCAL_HOST]

peer = Peer(LOCAL_HOST, LOCAL_PORT, PEERS, USER_ID_START)

peer.start()
# Keep the main thread alive
while True:
    time.sleep(1)
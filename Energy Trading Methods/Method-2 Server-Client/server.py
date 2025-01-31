import socket
import threading
import json
import pandas as pd
from datetime import datetime

class Server:
    def __init__(self, host='172.20.19.66', port=65432, db_file='excell.xlsx'):
        self.host = host
        self.port = port
        self.db_file = db_file
        self.clients = {}
        self.sellers = {}
        self.load_database()
        self.database['Username'] = self.database['Username'].astype(str)
        self.database['Password'] = self.database['Password'].astype(str)
        self.database['Registration Time'] = self.database['Registration Time'].astype(str)
        self.database['Seller/Buyer'] = self.database['Seller/Buyer'].astype(str)
        #self.database['Energy Quantity (kWh)'] = self.database['Energy Quantity (kWh)'].astype(float)
        #self.database['Price per Unit'] = self.database['Price per Unit'].astype(float)
        #self.transactions['Seller/Buyer'] = self.transactions['Seller/Buyer Time'].astype(str)
        self.transactions['Username'] = self.transactions['Username'].astype(str)
        self.transactions['Transaction Time'] = self.transactions['Transaction Time']
        self.transactions['Seller/Buyer'] = self.transactions['Seller/Buyer'].astype(str)

        #self.transactions['Energy Quantity (kWh)'] = self.transactions['Energy Quantity (kWh)'].astype(float)
        #self.transactions['Price per Unit'] = self.transactions['Price per Unit'].astype(float)

        
    def load_database(self):
        try:
            self.database = pd.read_excel(self.db_file, sheet_name='Sheet1')
            self.transactions = pd.read_excel(self.db_file, sheet_name='Sheet2')
        except FileNotFoundError:
            # Create new sheets if file does not exist
            self.database = pd.DataFrame(columns=['Username', 'Password', 'Time', 'Seller/Buyer', 'Energy Quantity (kWh)', 'Price per Unit'])
            self.transactions = pd.DataFrame(columns=['Username', 'Transaction Time', 'Seller/Buyer', 'Energy Quantity (kWh)', 'Price per Unit'])
            self.save_database()


    def save_database(self):
        # Save both sheets to the Excel file
        with pd.ExcelWriter(self.db_file) as writer:
            self.database.to_excel(writer, sheet_name='Sheet1', index=False)
            self.transactions.to_excel(writer, sheet_name='Sheet2', index=False)


    def authenticate_user(self, username, password):
        # Loop through both 'Username' and 'Password' lists simultaneously
        for i, (user, pwd) in enumerate(zip(self.database['Username'], self.database['Password'])):
            # Compare the username and password
            if username == user and int(password) == int(pwd):
                return True  # Authentication successful

        return False  # Authentication failed

    def update_user_info(self, username, role, energy_quantity, price_per_unit):
        # Update Sheet1 with the user's role (Seller/Buyer) and energy details
        idx = self.database[self.database['Username'] == username].index[0]
        self.database.at[idx, 'Seller/Buyer'] = role
        self.database.at[idx, 'Energy Quantity (kWh)'] = energy_quantity
        self.database.at[idx, 'Price per Unit'] = price_per_unit
        self.database.at[idx, 'Registration Time'] = datetime.now()
        self.save_database()

    def remove_user_info (self, username):
        # Update Sheet1 with the user's role (Seller/Buyer) and energy details
        idx = self.database[self.database['Username'] == username].index[0]
        self.database.at[idx, 'Seller/Buyer'] = 'nan'
        self.database.at[idx, 'Energy Quantity (kWh)'] = 'nan'
        self.database.at[idx, 'Price per Unit'] = 'nan'
        self.database.at[idx, 'Registration Time'] = 'nan'
        self.save_database()

    def update_transaction(self, username, transaction_type, energy_quantity, price_per_unit):
        # Add transaction details to Sheet2
        new_transaction = {
            'Username': username,
            'Transaction Time': datetime.now().isoformat(),
            'Seller/Buyer': transaction_type,
            'Energy Quantity (kWh)': energy_quantity,
            'Price per Unit': price_per_unit
        }
        new_transaction_df = pd.DataFrame([new_transaction])
    
        # Concatenate the new transaction with the existing transactions DataFrame
        self.transactions = pd.concat([self.transactions, new_transaction_df], ignore_index=True)
        #self.transactions = self.transactions.append(new_transaction, ignore_index=True)
        self.save_database()

    def handle_client(self, conn, addr):
        print(f"Connected by {addr}")
        try:
            while True:
                data = conn.recv(1024).decode()
                if not data:
                    break
                #print(f"Raw data received: {data}")  # Debug: Print raw data
                try:
                    message = json.loads(data)
                    #print(f"Decoded JSON: {message}")  # Debug: Print decoded JSON
                    response = self.process_message(message)
                    conn.sendall(json.dumps(response).encode())
                except json.JSONDecodeError as e:
                    print(f"JSON Decode Error: {e}")
                    conn.sendall(json.dumps({'status': 'invalid_format'}).encode())
        except Exception as e:
            print(f"Error: {e}")


    def process_message(self, message):
        #print(f"Processing message: {message}")
        if message['type'] == 'AUTH':
            username = message['username']
            password = message['password']
            if self.authenticate_user(username, password):
                return {'status': 'AUTH_SUCCESS'}
            else:
                return {'status': 'AUTH_FAILED'}
            '''if self.authenticate_user(username, password):
                self.clients[username] = {'role': 'prosumer'}
                return {'status': 'authenticated', 'role': 'prosumer'}
            else:
                return {'status': 'authentication_failed'}'''

        elif message['type'] == 'SELLER_notworkingREGISTER':
            username = message['username']
            energy_type = message['energy_type']
            energy_amount = message['energy_amount']
            price = message['price']
            print("2")
            self.sellers[username] = {
                'energy_type': energy_type,
                'energy_amount': energy_amount,
                'price': price,
                'timestamp': datetime.now().isoformat()
            }
            self.update_transaction(username, f"Registered as seller with {energy_amount} kWh of {energy_type} at {price} per unit.")
            return {'status': 'seller_registered'}
        elif message['type'] == 'SELLER_REGISTER':
            username = message['username']
            energy_amount = message['energy_amount']
            price = message['price']
            self.sellers[username] = {'energy_amount': energy_amount, 'price': price, 'timestamp': datetime.now().isoformat()}
            self.update_user_info(username, 'Seller', energy_amount, price)
            #self.update_transaction(username, 'Registration', energy_amount, price)
            return {'status': 'seller_registered'}

        elif message['type'] == 'BUYER_REQUEST':
            needed_energy = message['needed_energy']
            available_sellers = [
                {'seller': seller, **info}
                for seller, info in self.sellers.items()
                if info['energy_amount'] >= needed_energy
            ]
            return {'available_sellers': available_sellers}

        elif message['type'] == 'TRANSACTION':
            buyer = message['buyer']
            seller = message['seller']
            energy_sold = message['energy_sold']
            if seller in self.sellers and self.sellers[seller]['energy_amount'] >= energy_sold:
                self.sellers[seller]['energy_amount'] -= energy_sold
                self.update_transaction(buyer, f"Bought {energy_sold} kWh from {seller}.")
                self.update_transaction(seller, f"Sold {energy_sold} kWh to {buyer}.")
                return {'status': 'transaction_success'}
            else:
                return {'status': 'transaction_failed'}
        
        elif message['type'] == 'SELLER_UPDATE':
            username = message['username']
            field = message['field']
            value = message['value']
            if username in self.sellers:
                    self.sellers[username][field] = value
                    print(f"Seller {username} updated {field} to {value}")
                    return {'status': 'updated', 'message': f'{field} updated successfully.'}
            else:
                return {'status': 'error', 'message': 'Seller not found.'}
            
        elif message['type'] == 'SELLER_EXIT':
            username = message['username']
            self.remove_user_info(username)
            if username in self.sellers:
                del self.sellers[username]
                print(f"Seller {username} removed.")
                return {'status': 'removed', 'message': 'Seller removed successfully.'}
            else:
                return {'status': 'error', 'message': 'Seller not found.'}

        else:
            return {'status': 'unknown_command', 'message': 'Command not recognized.'}
            

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            print(f"Server started on {self.host}:{self.port}")
            while True:
                conn, addr = server_socket.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr)).start()

if __name__ == "__main__":
    server = Server()
    server.start()

import socket
import threading
import json
import pandas as pd
from datetime import datetime
import os
import time
import numpy as np
from datetime import datetime, timedelta
import uuid
class Server:
    def __init__(self, host='192.168.166.7', port=65432, db_file='excell.xlsx'):
        self.auto_sellers = []  # List to hold auto mode seller orders.
        self.auto_buyers = []   # List to hold auto mode buyer orders.
        self.buyers = {}
        self.sellers = {}
        self.host = host
        self.port = port
        self.db_file = db_file
        self.clients = {}   # Maps authenticated username to connection
        self.sellers = {}   # Maps seller_id to seller info (including connection)
        # For now we assume only three users; we map each to a fixed sheet name.
        self.user_to_sheet = {
            "Madhav": "Sheet2",
            "Aarush": "Sheet3",
            "Tanmay": "Sheet4"
        }
        self.load_database()
        self.ensure_columns()
        threading.Thread(target=self.cleanup_disconnected_clients, daemon=True).start()
    '''def ensure_columns(self):
        """Ensure that the required columns exist in the summary DataFrame and in each transaction sheet."""
        # For the summary sheet (Sheet1)
        required_user_cols = ['Username', 'Password', 'Registration Time', 'Seller/Buyer',
                              'Energy Quantity (kWh)', 'Price per Unit', 'Last Transaction Time']
        for col in required_user_cols:
            if col not in self.database.columns:
                self.database[col] = np.nan
        # For each user’s transaction sheet, ensure the required columns exist.
        required_trans_cols = ['Transaction Time', 'Seller/Buyer', 'Energy Quantity (kWh)', 'Price per Unit']
        for user in self.user_to_sheet:
            if user not in self.transactions:
                self.transactions[user] = pd.DataFrame(columns=required_trans_cols)
            else:
                for col in required_trans_cols:
                    if col not in self.transactions[user].columns:
                        self.transactions[user][col] = np.nan'''
    def cleanup_disconnected_clients(self):
        """
        Periodically check for disconnected clients and remove their orders from sellers,
        auto_sellers, and auto_buyers.
        """
        while True:
            time.sleep(30)  # Check every 30 seconds (adjust as needed)
            active_conns = set(self.clients.values())
            # Clean up sellers.
            stale_seller_ids = [sid for sid, info in self.sellers.items() if info.get('conn') not in active_conns]
            for sid in stale_seller_ids:
                print(f"Periodic cleanup: Removing stale seller entry {sid}")
                del self.sellers[sid]
            # Clean up auto_sellers and auto_buyers.
            self.auto_sellers = [order for order in self.auto_sellers if order.get('conn') in active_conns]
            self.auto_buyers = [order for order in self.auto_buyers if order.get('conn') in active_conns]

    def ensure_columns(self):
        """Ensure that the required columns exist in the summary DataFrame and in each transaction sheet."""
        # For the summary sheet (Sheet1)
        required_user_cols = [
            'Username', 'Password', 'Registration Time', 'Seller/Buyer',
            'Energy Quantity (kWh)', 'Price per Unit', 'Last Transaction Time',
            'Amount of Duration', 'Date'
        ]
        for col in required_user_cols:
            if col not in self.database.columns:
                self.database[col] = np.nan
        # For each user’s transaction sheet, ensure the required columns exist.
        required_trans_cols = [
            'Transaction Time', 'Seller/Buyer', 'Energy Quantity (kWh)',
            'Price per Unit', 'Amount of Duration', 'Date'
        ]
        for user in self.user_to_sheet:
            if user not in self.transactions:
                self.transactions[user] = pd.DataFrame(columns=required_trans_cols)
            else:
                for col in required_trans_cols:
                    if col not in self.transactions[user].columns:
                        self.transactions[user][col] = np.nan


    def load_database(self):
        """Load the Excel file with all sheets. Sheet1 is the summary; additional sheets hold per-user transactions."""
        if os.path.exists(self.db_file):
            try:
                sheets = pd.read_excel(self.db_file, sheet_name=None)
                self.database = sheets.get('Sheet1', pd.DataFrame(columns=[
                    'Username', 'Password', 'Registration Time', 'Seller/Buyer',
                    'Energy Quantity (kWh)', 'Price per Unit', 'Last Transaction Time'
                ]))
                #self.database = pd.read_excel(self.db_file, sheet_name='Sheet1')

                # For each user defined in our mapping, load (or create) a transaction sheet.
                self.transactions = {}
                for user, sheet_name in self.user_to_sheet.items():
                    if sheet_name in sheets:
                        self.transactions[user] = sheets[sheet_name]
                    else:
                        self.transactions[user] = pd.DataFrame(columns=[
                            'Transaction Time', 'Seller/Buyer', 'Energy Quantity (kWh)', 'Price per Unit'
                        ])
            except Exception as e:
                print("Error loading Excel file:", e)
                self.create_empty_database()
        else:
            self.create_empty_database()

    def create_empty_database(self):
        self.database = pd.DataFrame(columns=[
            'Username', 'Password', 'Registration Time', 'Seller/Buyer',
            'Energy Quantity (kWh)', 'Price per Unit', 'Last Transaction Time',
            'Amount of Duration', 'Date'
        ])

        self.transactions = {}
        for user in self.user_to_sheet.keys():
            self.transactions[user] = pd.DataFrame(columns=[
                'Transaction Time', 'Seller/Buyer', 'Energy Quantity (kWh)', 'Price per Unit'
            ])
        self.save_database()

    def save_database(self):
        """Save the summary and all transaction sheets to the Excel file."""
        with pd.ExcelWriter(self.db_file) as writer:
            self.database.to_excel(writer, sheet_name='Sheet1', index=False)
            for user, sheet_name in self.user_to_sheet.items():
                self.transactions[user].to_excel(writer, sheet_name=sheet_name, index=False)

    def authenticate_user(self, username, password):
        """
        Check if the provided username and password match any record in the summary sheet.
        If the user does not exist yet, add them.
        """
        if username not in self.database['Username'].values:
            print("User not found ,exiting")
            return False
        else:
            # Existing user: check the password.
            record = self.database[self.database['Username'] == username]
            if not record.empty and str(record.iloc[0]['Password']) == str(password):
                # Optionally update the registration time on login.
                idx = self.database[self.database['Username'] == username].index[0]
                self.database.at[idx, 'Registration Time'] = datetime.now().isoformat()
                self.save_database()
                return True
            return False

    def update_user_info(self, username, role, energy_quantity, price_per_unit):
        """Update the summary sheet for the given user (used when a seller registers)."""
        try:
            idx = self.database[self.database['Username'] == username].index[0]
        except IndexError:
            print(f"Username {username} not found in database; skipping update.")
            return
        self.database.at[idx, 'Seller/Buyer'] = role
        self.database.at[idx, 'Energy Quantity (kWh)'] = energy_quantity
        self.database.at[idx, 'Price per Unit'] = price_per_unit
        # Update registration time as well.
        
        self.database.at[idx, 'Registration Time'] = datetime.now().isoformat()
        print(datetime.now())
        print(f"Price per unit at index {idx}: {self.database.at[idx, 'Price per Unit']}")
        self.save_database()

    def remove_user_info(self, username):
        """Clear seller-specific info from the user's record in the summary sheet."""
        try:
            idx = self.database[self.database['Username'] == username].index[0]
        except IndexError:
            print(f"Username {username} not found in database; skipping removal.")
            return
        self.database.at[idx, 'Seller/Buyer'] = np.nan
        self.database.at[idx, 'Energy Quantity (kWh)'] = np.nan
        self.database.at[idx, 'Price per Unit'] = np.nan
        self.database.at[idx, 'Registration Time'] = np.nan
        self.save_database()

    def update_transaction(self, username, transaction_type, energy_quantity, price_per_unit):
        """
        Append a new transaction record for the given user and update their last transaction time
        in the summary sheet.
        """
        new_transaction = {
            'Transaction Time': datetime.now().isoformat(),
            'Seller/Buyer': transaction_type,
            'Energy Quantity (kWh)': energy_quantity,
            'Price per Unit': price_per_unit
        }
        # Append the new transaction to the appropriate transaction sheet.
        if username not in self.transactions:
            # If a new user appears, create a new transaction DataFrame for them.
            self.transactions[username] = pd.DataFrame(columns=[
                'Transaction Time', 'Seller/Buyer', 'Energy Quantity (kWh)', 'Price per Unit'
            ])
        new_transaction_df = pd.DataFrame([new_transaction])
        # Ensure the "Transaction Time" column is of type string in both DataFrames.
        new_transaction_df['Transaction Time'] = new_transaction_df['Transaction Time'].astype(str)
        self.transactions[username]['Transaction Time'] = self.transactions[username]['Transaction Time'].astype(str)
        
        self.transactions[username] = pd.concat([self.transactions[username], new_transaction_df], ignore_index=True)
        
        # Update the summary sheet with the last transaction time.
        if username in self.database['Username'].values:
            idx = self.database[self.database['Username'] == username].index[0]
            self.database.at[idx, 'Last Transaction Time'] = datetime.now().isoformat()
        
        self.save_database()


    def handle_client(self, conn, addr):
        print(f"Connected by {addr}")
        username = None  # Will be set upon successful authentication
        try:
            while True:
                data = conn.recv(1024).decode()
                if not data:
                    break
                try:
                    message = json.loads(data)
                except json.JSONDecodeError as e:
                    print(f"JSON decode error from {addr}: {e}")
                    conn.sendall(json.dumps({'status': 'invalid_format'}).encode())
                    continue

                # Handle authentication.
                if message['type'] == 'AUTH':
                    username = message['username']
                    if self.authenticate_user(username, message['password']):
                        self.clients[username] = conn
                        response = {'status': 'AUTH_SUCCESS'}
                        print(f"User '{username}' authenticated.")
                    else:
                        response = {'status': 'AUTH_FAILED'}
                        print(f"Authentication failed for user '{username}'.")
                    conn.sendall(json.dumps(response).encode())
                else:
                    # For other messages, ensure the client is authenticated.
                    if username is None:
                        conn.sendall(json.dumps({'status': 'error', 'message': 'Not authenticated'}).encode())
                        continue
                    response = self.process_message(message, username)
                    conn.sendall(json.dumps(response).encode())
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            conn.close()
            if username:
                # Remove this user from the client mapping and clean up stale orders.
                if username in self.clients:
                    del self.clients[username]
                self.remove_user_from_all_lists(username)
            print(f"Connection closed for {addr}.")
    def remove_user_from_all_lists(self, username):
        # Remove from sellers as before.
        stale_seller_ids = [sid for sid, info in self.sellers.items() if info.get('conn') not in self.clients.values()]
        for sid in stale_seller_ids:
            print(f"Removing stale seller entry: {sid}")
            del self.sellers[sid]

        # Remove auto mode orders associated with the user.
        self.auto_sellers = [order for order in self.auto_sellers if order.get('conn') in self.clients.values()]
        self.auto_buyers = [order for order in self.auto_buyers if order.get('conn') in self.clients.values()]

        # Also remove stale auto buyer entries from the global buyers dictionary.
        stale_buyer_ids = [bid for bid, order in self.buyers.items() if order.get('conn') not in self.clients.values()]
        for bid in stale_buyer_ids:
            print(f"Removing stale buyer entry: {bid}")
            del self.buyers[bid]


    def attempt_auto_match(self):
        # Loop through a copy of the buyer orders (so that we can remove orders when matched)
        for buyer in self.auto_buyers[:]:
            for seller in self.auto_sellers[:]:
                if seller['energy_amount'] >= buyer['needed_energy'] and seller['min_price'] <= buyer['max_price']:
                    # Match found!
                    transaction_energy = buyer['needed_energy']
                    # Reduce seller's available energy
                    seller['energy_amount'] -= transaction_energy
                    # Remove seller order if completely filled:
                    if seller['energy_amount'] <= 0:
                        self.auto_sellers.remove(seller)
                    self.auto_buyers.remove(buyer)
                    # Update transactions in your Excel/logging system:
                    #self.update_transaction(buyer['buyer_name'], f"Bought {transaction_energy} kWh from auto seller {seller['seller_name']}.", transaction_energy, seller['min_price'])
                    #self.update_transaction(seller['seller_name'], f"Sold {transaction_energy} kWh to auto buyer {buyer['buyer_name']}.", transaction_energy, seller['min_price'])
                    self.update_transaction(buyer['buyer_name'], 'Buyer', transaction_energy, seller['min_price'])
                    self.update_transaction(seller['seller_name'], 'Seller', transaction_energy, seller['min_price'])
                    print(f"Auto-match: Buyer '{buyer['buyer_name']}' purchased {transaction_energy} kWh from seller '{seller['seller_name']}'.")
                    # Send notifications (similar to your TRANSACTION_NOTIFICATION)
                    notification = {
                        'type': 'TRANSACTION_NOTIFICATION',
                        'buyer_name': buyer['buyer_name'],
                        'energy_amount': transaction_energy,
                        'duration': seller['duration'],  # or buyer['duration'], as appropriate
                        'price': seller['min_price'],
                        'automode': True
                    }
                    # Notify seller:
                    try:
                        if seller['conn']:
                            seller['conn'].sendall(json.dumps(notification).encode())
                    except Exception as e:
                        print("Error sending auto transaction notification to seller:", e)
                    # Notify buyer:
                    try:
                        if buyer['conn']:
                            buyer['conn'].sendall(json.dumps(notification).encode())
                    except Exception as e:
                        print("Error sending auto transaction notification to buyer:", e)
                    # Break out to move to the next buyer.
                    break
    def is_time_window_match(self, seller_tw, buyer_tw, required_duration):
        """
        Check if the seller's time window fully contains the buyer's time window,
        and that the buyer's window length is at least required_duration (in seconds).
        Both seller_tw and buyer_tw are dictionaries with 'start' and 'end' keys.
        The times are expected in "HH:MM" or "HH:MM:SS" format.
        """
        from datetime import datetime
        dummy_date = datetime(1900, 1, 1)
        # Parse seller start and end
        try:
            seller_start = datetime.strptime(seller_tw['start'], "%H:%M:%S").time()
        except ValueError:
            seller_start = datetime.strptime(seller_tw['start'], "%H:%M").time()
        try:
            seller_end = datetime.strptime(seller_tw['end'], "%H:%M:%S").time()
        except ValueError:
            seller_end = datetime.strptime(seller_tw['end'], "%H:%M").time()
        seller_start_dt = datetime.combine(dummy_date, seller_start)
        seller_end_dt = datetime.combine(dummy_date, seller_end)
        
        # Parse buyer start and end
        try:
            buyer_start = datetime.strptime(buyer_tw['start'], "%H:%M:%S").time()
        except ValueError:
            buyer_start = datetime.strptime(buyer_tw['start'], "%H:%M").time()
        try:
            buyer_end = datetime.strptime(buyer_tw['end'], "%H:%M:%S").time()
        except ValueError:
            buyer_end = datetime.strptime(buyer_tw['end'], "%H:%M").time()
        buyer_start_dt = datetime.combine(dummy_date, buyer_start)
        buyer_end_dt = datetime.combine(dummy_date, buyer_end)
        
        # Check that buyer's window is completely within seller's window.
        if buyer_start_dt >= seller_start_dt and buyer_end_dt <= seller_end_dt:
            # Compute the buyer's window duration in seconds.
            buyer_window_duration = (buyer_end_dt - buyer_start_dt).total_seconds()
            if buyer_window_duration >= required_duration:
                return True
        return False

    def process_message(self, message, username):
        """Process messages other than authentication."""
        if message['type'] == 'AUTO_SELLER':
            # Expected keys: seller_id, seller_name, energy_amount, min_price, duration, time_window.
            auto_seller_order = {
                'seller_id': message['seller_id'],
                'seller_name': message['seller_name'],
                'energy_amount': message['energy_amount'],
                'min_price': message['min_price'],
                'duration': message['duration'],
                'time_window': message.get('time_window', None),
                'conn': self.clients[username]
            }
            # Add to the auto seller list
            self.auto_sellers.append(auto_seller_order)
            # Also add to the main sellers dictionary so buyers can see this auto-seller:
            self.sellers[message['seller_id']] = {
                'seller_name': message['seller_name'],
                'energy_type': "AUTO",  # or use a proper energy type if available
                'energy_amount': message['energy_amount'],
                'duration': message['duration'],
                'price': message['min_price'],  # using min_price as the set price
                'time_window': message.get('time_window', None),
                'timestamp': datetime.now().isoformat(),
                'conn': self.clients[username]
            }
            self.attempt_auto_match()
            return {'status': 'auto_seller_registered'}


        elif message['type'] == 'AUTO_BUYER':
            # Generate a unique buyer ID.
            buyer_id = str(uuid.uuid4())
            auto_buyer_order = {
                'buyer_id': buyer_id,
                'buyer_name': message['buyer_name'],
                'needed_energy': message['needed_energy'],
                'max_price': message['max_price'],
                'duration': message['duration'],
                'time_window': message.get('time_window', None),
                'conn': self.clients[username]
            }
            # Add the order to the auto_buyers list.
            self.auto_buyers.append(auto_buyer_order)
            # Also add the order to the global buyers dictionary.
            self.buyers[buyer_id] = auto_buyer_order
            self.attempt_auto_match()
            return {'status': 'auto_buyer_registered'}


        elif message['type'] == 'SELLER_REGISTER':
            # Expected keys: seller_id, seller_name, energy_type, energy_amount, duration, price, time_window.
            seller_id = message['seller_id']
            if 'time_window' not in message:
                return {'status': 'error', 'message': 'Time window required for seller registration.'}
            tw = message['time_window']
            if 'start' not in tw or 'end' not in tw:
                return {'status': 'error', 'message': 'Time window must include both start and end times.'}
            # Enforce that the trading window is for the day-ahead market.
            try:
                # Assume that the provided time strings (HH:MM or HH:MM:SS) are for the next day.
                tomorrow = datetime.now() + timedelta(days=1)
                # Parse the start time:
                try:
                    start_time_obj = datetime.strptime(tw['start'], "%H:%M:%S").time()
                except ValueError:
                    start_time_obj = datetime.strptime(tw['start'], "%H:%M").time()
                start_datetime = datetime.combine(tomorrow.date(), start_time_obj)
                # Require that the trading window start is at least 12 hours ahead.
                '''if start_datetime < datetime.now() + timedelta(hours=12):
                    return {'status': 'error', 'message': 'Trading window start must be at least 12 hours ahead.'}'''
            except Exception as e:
                return {'status': 'error', 'message': 'Invalid time window format.'}
            
            seller_name = message['seller_name']
            energy_type = message['energy_type']
            energy_amount = message['energy_amount']
            duration = message['duration']
            price = message['price']
            # Save the time window as provided.
            self.sellers[seller_id] = {
                'seller_name': seller_name,
                'energy_type': energy_type,
                'energy_amount': energy_amount,
                'duration': duration,
                'price': price,
                'time_window': tw,  # Store the provided window.
                'timestamp': datetime.now().isoformat(),
                'conn': self.clients[username]
            }
            self.update_user_info(username, 'Seller', energy_amount, price)
            print(f"Seller registered: {seller_name} (ID: {seller_id}), Time Window: {tw}")
            return {'status': 'seller_registered'}

        elif message['type'] == 'SELLER_UPDATE':
            # Expected keys: seller_id, field, value.
            seller_id = message['seller_id']
            field = message['field']
            value = message['value']
            if seller_id in self.sellers:
                self.sellers[seller_id][field] = value
                print(f"Seller {seller_id} updated {field} to {value}.")
                return {'status': 'updated', 'message': f'{field} updated successfully.'}
            else:
                return {'status': 'error', 'message': 'Seller not found.'}

        elif message['type'] == 'SELLER_EXIT':
            # Expected key: seller_id.
            seller_id = message['seller_id']
            if seller_id in self.sellers:
                seller_name = self.sellers[seller_id]['seller_name']
                del self.sellers[seller_id]
                self.remove_user_info(username)
                print(f"Seller {seller_name} (ID: {seller_id}) removed.")
                return {'status': 'removed', 'message': 'Seller removed successfully.'}
            else:
                return {'status': 'error', 'message': 'Seller not found.'}

        elif message['type'] == 'BUYER_REQUEST':
            # Expected keys: buyer_name, needed_energy, duration, time_window.
            if 'time_window' not in message:
                return {'status': 'error', 'message': 'Time window required for buyer request.'}
            tw = message['time_window']
            if 'start' not in tw or 'end' not in tw:
                return {'status': 'error', 'message': 'Time window must include both start and end times.'}
            try:
                tomorrow = datetime.now() + timedelta(days=1)
                try:
                    start_time_obj = datetime.strptime(tw['start'], "%H:%M:%S").time()
                except ValueError:
                    start_time_obj = datetime.strptime(tw['start'], "%H:%M").time()
                start_datetime = datetime.combine(tomorrow.date(), start_time_obj)
                """if start_datetime < datetime.now() + timedelta(hours=12):
                    return {'status': 'error', 'message': 'Trading window start must be at least 12 hours ahead.'}"""
            except Exception as e:
                return {'status': 'error', 'message': 'Invalid time window format.'}
            
            needed_energy = message['needed_energy']
            duration = message['duration']
            # Instead of checking a transaction date, we use the provided time_window.
            available_sellers = []
            for sid, info in self.sellers.items():
                # (Optionally, you can add a check that the seller's time window
                # matches or overlaps with the buyer's time window.)
                seller_tw = info.get('time_window', {})
                if info['energy_amount'] >= needed_energy:
                    # For example, you might check that the seller's start time equals the buyer's start time.
                    #if seller_tw.get('start') == tw.get('start'):
                    if info['energy_amount'] >= needed_energy and self.is_time_window_match(seller_tw, tw, duration):
                        seller_info = {
                            'seller_id': sid,
                            'seller_name': info['seller_name'],
                            'energy_type': info['energy_type'],
                            'energy_amount': info['energy_amount'],
                            'duration': info['duration'],
                            'price': info['price'],
                            'time_window': seller_tw
                        }
                        available_sellers.append(seller_info)
            print(f"Buyer request from '{message.get('buyer_name', username)}' for {needed_energy} kWh; {len(available_sellers)} seller(s) available with matching time window.")
            return {'available_sellers': available_sellers}

        elif message['type'] == 'TRANSACTION':
            # Expected keys: buyer_name, seller_id, energy_amount, duration, price, time_window.
            buyer_name = message['buyer_name']
            seller_id = message['seller_id']
            energy_amount = message['energy_amount']
            duration = message['duration']
            price = message['price']
            tw = message.get('time_window')
            # Optionally, verify that the time window in the transaction matches the seller's.
            if seller_id in self.sellers and self.sellers[seller_id]['energy_amount'] >= energy_amount:
                seller_tw = self.sellers[seller_id].get('time_window', {})
                buyer_tw = message.get('time_window', {})
                # For example, require that the seller and buyer have the same trading window start time.
                '''if buyer_tw.get('start') != seller_tw.get('start'):
                    return {'status': 'transaction_failed', 'message': 'Trading time window mismatch.'}'''
                if self.is_time_window_match(seller_tw, tw, duration):
                    self.sellers[seller_id]['energy_amount'] -= energy_amount
                    # Update the transaction history for both buyer and seller.
                    self.update_transaction(buyer_name,
                                            f"Bought {energy_amount} kWh from seller {self.sellers[seller_id]['seller_name']}.",
                                            energy_amount, price)
                    self.update_transaction(self.sellers[seller_id]['seller_name'],
                                            f"Sold {energy_amount} kWh to buyer {buyer_name}.",
                                            energy_amount, price)
                    print(f"Transaction: Buyer '{buyer_name}' purchased {energy_amount} kWh from seller '{self.sellers[seller_id]['seller_name']}' (ID: {seller_id}).")
                    # Send transaction notifications to both sides.
                    notification = {
                        'type': 'TRANSACTION_NOTIFICATION',
                        'buyer_name': buyer_name,
                        'energy_amount': energy_amount,
                        'duration': duration,
                        'price': price,
                        'seller_id': seller_id,
                        'seller_name': self.sellers[seller_id]['seller_name']
                    }
                    try:
                        seller_conn = self.sellers[seller_id].get('conn')
                        if seller_conn:
                            seller_conn.sendall(json.dumps(notification).encode())
                    except Exception as e:
                        print("Error sending transaction notification to seller:", e)
                    try:
                        buyer_conn = self.clients[username]
                        if buyer_conn:
                            buyer_conn.sendall(json.dumps(notification).encode())
                    except Exception as e:
                        print("Error sending transaction notification to buyer:", e)
                    return {'status': 'transaction_success'}
                else:
                    return {'status': 'transaction_failed', 'message': 'Seller not found or insufficient energy.'}

            else:
                return {'status': 'unknown_command', 'message': 'Command not recognized.'}


    def start(self):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.bind((self.host, self.port))
                server_socket.listen()
                print(f"Server started on {self.host}:{self.port}")
                while True:
                    conn, addr = server_socket.accept()
                    threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    server = Server()
    server.start()

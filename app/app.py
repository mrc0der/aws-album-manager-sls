import streamlit as st
import boto3
from boto3.dynamodb.conditions import Key

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')

def list_clients():
    table = dynamodb.Table('Clients')
    response = table.scan()
    return response['Items']

def list_orders():
    table = dynamodb.Table('PayPalOrders')  # Replace with your actual table name
    response = table.scan()
    return response['Items']

def list_albums():
    table = dynamodb.Table('Albums')  # Replace with your actual table name
    response = table.scan()
    return response['Items']

def insert_client(client_name, email):
    table = dynamodb.Table('Clients')
    response = table.put_item(
        Item={
            'clientID': 'unique-id',  # Generate or specify unique ID
            'clientName': client_name,
            'email': email,
            # Add other attributes as necessary
        }
    )
    return response

def insert_album(client_id, album_name):
    table = dynamodb.Table('Albums')
    response = table.put_item(
        Item={
            'albumID': 'unique-id',  # Generate or specify unique ID
            'clientID': client_id,
            'albumName': album_name,
            # Add other attributes as necessary
        }
    )
    return response

def main():
    st.title("DynamoDB Management Dashboard")

    tab1, tab2, tab3 = st.tabs(["Clients", "PayPal Orders", "Albums"])

    with tab1:
        st.header("Clients")
        clients = list_clients()
        for client in clients:
            st.write(client)  # Customize based on how you want to display client info
        
        with st.form("Insert Client"):
            client_name = st.text_input("Client Name")
            email = st.text_input("Email")
            submit_button = st.form_submit_button("Insert")
            if submit_button:
                insert_client(client_name, email)
                st.success("Client inserted successfully!")

    with tab2:
        st.header("PayPal Orders")
        orders = list_orders()
        for order in orders:
            st.write(order)  # Customize based on how you want to display order info

    with tab3:
        st.header("Albums")
        albums = list_albums()
        for album in albums:
            st.write(album)  # Customize based on how you want to display album info

        with st.form("Insert Album"):
            client_id = st.text_input("Client ID")
            album_name = st.text_input("Album Name")
            submit_button = st.form_submit_button("Insert")
            if submit_button:
                insert_album(client_id, album_name)
                st.success("Album inserted successfully!")

if __name__ == "__main__":
    main()

import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv, find_dotenv

def get_env_key():
    # Load existing .env file or create a new one
    load_dotenv(find_dotenv(), override=True)

    # Check if the key already exists
    if os.getenv('ENCRYPTION_KEY'):
        print("Encryption key already exists.")
        return os.getenv('ENCRYPTION_KEY')

    # Generate a new key
    key = Fernet.generate_key()

    # Store the key in the .env file
    with open('.env', 'a') as f:
        f.write(f'\nENCRYPTION_KEY={key.decode()}')

    print("Encryption key generated and stored in .env file.")
    return key.decode()  # Return the key

get_env_key()
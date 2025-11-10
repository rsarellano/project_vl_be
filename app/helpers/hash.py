import bcrypt

def hash_pass(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()

def verify_pass(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())
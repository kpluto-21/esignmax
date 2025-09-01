# generate_keys.py
from ecdsa import SigningKey, NIST256p

# buat private key
private_key = SigningKey.generate(curve=NIST256p)
with open("keys/private.pem", "wb") as f:
    f.write(private_key.to_pem())

# buat public key dari private key
public_key = private_key.get_verifying_key()
with open("keys/public.pem", "wb") as f:
    f.write(public_key.to_pem())

print("Kunci ECDSA berhasil dibuat di folder 'keys/'")
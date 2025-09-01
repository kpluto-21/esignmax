from ecdsa import SigningKey, NIST256p
import os
os.makedirs("keys", exist_ok=True)
sk = SigningKey.generate(curve=NIST256p)
with open("keys/private.pem", "wb") as f:
    f.write(sk.to_pem())
with open("keys/public.pem", "wb") as f:
    f.write(sk.get_verifying_key().to_pem())
print("✅ Kunci berhasil dibuat.")

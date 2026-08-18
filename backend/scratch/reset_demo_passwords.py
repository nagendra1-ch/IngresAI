import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models import User
from app.utils.auth import get_password_hash, verify_password

db = SessionLocal()

admin = db.query(User).filter_by(email='admin@ingres.gov.in').first()
user  = db.query(User).filter_by(email='user@ingres.gov.in').first()

print("Current password check:")
print("  admin/adminpassword:", verify_password("adminpassword", admin.password_hash))
print("  user/userpassword:", verify_password("userpassword", user.password_hash))

# Reset to demo credentials
admin.password_hash = get_password_hash("adminpassword")
user.password_hash  = get_password_hash("userpassword")
db.commit()

print("Passwords reset. Verifying...")
db.refresh(admin)
db.refresh(user)
print("  admin/adminpassword:", verify_password("adminpassword", admin.password_hash))
print("  user/userpassword:", verify_password("userpassword", user.password_hash))

db.close()
print("Done.")

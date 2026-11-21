"""Run once locally or in a secure Render shell. Do not commit credentials."""
import os,getpass
from sqlalchemy import select
from main import SessionLocal,Admin,ctx
username=input('Admin username: ').strip()
password=getpass.getpass('Admin password (12+ characters): ')
if len(password)<12: raise SystemExit('Password must be at least 12 characters')
with SessionLocal() as s:
    if s.scalar(select(Admin).where(Admin.username==username)): raise SystemExit('Username already exists')
    s.add(Admin(username=username,password_hash=ctx.hash(password)));s.commit()
print('Admin created.')
